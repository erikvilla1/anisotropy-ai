"""Abaqus/CAE field reports saved as CSV (Report > Field Output), read into the numbers a comparison record needs (ADR-0030, amendment 2).

The file Abaqus/CAE writes has one row per element and section point:

    ODB Name,Step,Frame,Part Instance Name, Element Label, IntPt,X,Y,Z,Section Name,Material Name,Section Point, S-S22
    C:/.../model.odb,Step-1,Increment 1: Step Time = 1.000,"PART-1", 3, 1, 2.5, 7.5, 0.,"...","MATERIAL-1","shell < composite > < elset = ... > : SNEG, (fraction = -1.0), Layer = 1", 1234.5

A file may hold several report blocks, each starting with its own header line, and the same (element, section point) may
appear in more than one block; repeated rows must agree. `IntPt` must be 1 everywhere: a one-point shell (S4R) reports at
the element centroid, which is where the kernel evaluates; a multi-point report is refused rather than averaged silently.
The section point text names the face (`SNEG`, `SPOS`, or none at mid-layer) and the layer; Abaqus numbers layers from the
bottom, which the 2026-10-18 comparison confirmed (`SNEG, Layer = 1` is the bottom face of the bottom ply). Values are in the
report's own units, like a deck; the caller states them.

`read_field_report` reads one quantity; `report_quantities` maps several quantities for one model into the `[expected]`
tables of a record: S11, S22, S12 fill `ply_stress_local` (a component the team did not export is `nan`, which the
comparison skips) and Mises fills `ply_mises`. Anything else is refused by name.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

from .model import Deck

QUANTITIES = {"S11": ("ply_stress_local", 0), "S22": ("ply_stress_local", 1), "S12": ("ply_stress_local", 2), "Mises": ("ply_mises", 0)}
REQUIRED_COLUMNS = ("ODB Name", "Step", "Frame", "Part Instance Name", "Element Label", "IntPt", "X", "Y", "Section Point")
SECTION_POINT = re.compile(r"(?:(SNEG|SPOS|SMID)\s*,)?\s*(?:\(fraction\s*=\s*([-+0-9.eE]+)\)\s*,)?\s*Layer\s*=\s*(\d+)\s*$")


class ReportError(ValueError):
    """The report is not a single-point element field report we understand; the message names the line."""


@dataclass(frozen=True)
class FieldReport:
    path: str
    quantity: str  # S11, S22, S12, Mises, as the value column names it
    odb: str
    step: str
    frame: str
    instance: str  # as the report spells it (Abaqus/CAE upper-cases instance names)
    values: dict[tuple[int, int], float]  # (element label, layer from 1 at the bottom) -> value at the centroid
    faces: dict[tuple[int, int], str]  # (element, layer) -> SNEG | SPOS | SMID | ""
    centroids: dict[int, tuple[float, float]]  # element label -> (x, y) as reported
    blocks: int
    rows: int


def read_field_report(path: Path | str) -> FieldReport:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    header: list[str] | None = None
    value_column: str | None = None
    meta: dict[str, str] = {}
    values: dict[tuple[int, int], float] = {}
    faces: dict[tuple[int, int], str] = {}
    centroids: dict[int, tuple[float, float]] = {}
    blocks = rows = 0
    for number, line in enumerate(csv.reader(lines), start=1):
        if not line or not any(cell.strip() for cell in line):
            continue
        cells = [cell.strip() for cell in line]
        if cells[0] == "ODB Name":
            missing = [c for c in REQUIRED_COLUMNS if c not in cells]
            if missing:
                raise ReportError(f"{path.name} line {number}: header lacks {missing}")
            if header is not None and cells != header:
                raise ReportError(f"{path.name} line {number}: a second header differs from the first")
            header = cells
            value_column = cells[-1]
            if not value_column.startswith("S-") or value_column[2:] not in QUANTITIES:
                raise ReportError(f"{path.name} line {number}: value column {value_column!r} is not one of {['S-' + q for q in QUANTITIES]}")
            blocks += 1
            continue
        if header is None:
            raise ReportError(f"{path.name} line {number}: data before the first header line")
        if len(cells) != len(header):
            raise ReportError(f"{path.name} line {number}: {len(cells)} fields, the header has {len(header)}")
        row = dict(zip(header, cells))
        for key in ("ODB Name", "Step", "Frame", "Part Instance Name"):
            if key in meta and meta[key] != row[key]:
                raise ReportError(f"{path.name} line {number}: {key} changes from {meta[key]!r} to {row[key]!r}; one report, one model")
            meta[key] = row[key]
        try:
            element = int(row["Element Label"])
            point = int(row["IntPt"])
            x, y = float(row["X"]), float(row["Y"])
            value = float(row[value_column])
        except ValueError:
            raise ReportError(f"{path.name} line {number}: a number does not parse") from None
        if point != 1:
            raise ReportError(f"{path.name} line {number}: integration point {point}; only single-point (centroid) reports are read")
        match = SECTION_POINT.search(row["Section Point"])
        if match is None:
            raise ReportError(f"{path.name} line {number}: section point {row['Section Point']!r} names no layer")
        face, layer = match.group(1) or "", int(match.group(3))
        key = (element, layer)
        if key in values and (values[key] != value or faces[key] != face):
            raise ReportError(f"{path.name} line {number}: element {element} layer {layer} repeated with a different value or face")
        if element in centroids and centroids[element] != (x, y):
            raise ReportError(f"{path.name} line {number}: element {element} repeated with different coordinates")
        values[key], faces[key], centroids[element] = value, face, (x, y)
        rows += 1
    if header is None or not values:
        raise ReportError(f"{path.name}: no report block with data")
    return FieldReport(path=str(path), quantity=value_column[2:], odb=meta["ODB Name"], step=meta["Step"], frame=meta["Frame"],
                       instance=meta["Part Instance Name"], values=values, faces=faces, centroids=centroids, blocks=blocks, rows=rows)


FACE_FRACTION = {"SNEG": "-1.0", "SPOS": "1.0", "SMID": "0.0"}


def write_field_report(path: Path | str, quantity: str, rows: list[tuple[int, int, str, float, float, float]], odb: str, step: str, frame: str,
                       instance: str, section: str, material: str) -> None:
    """Values written in the layout of an Abaqus/CAE field report, so they open beside the team's own reports.

    One block with the columns `read_field_report` reads; `rows` are (element label, layer from 1 at the bottom, face SNEG,
    SPOS or SMID, centroid x, centroid y, value), one per element and section point, all at integration point 1 (the centroid).
    The section point text has the shape Abaqus writes: `shell < composite > < elset = ... > : SNEG, (fraction = -1.0), Layer = 1`.
    """
    if quantity not in QUANTITIES:
        raise ReportError(f"quantity {quantity!r} is not one of {list(QUANTITIES)}")
    header = ["ODB Name", "Step", "Frame", "Part Instance Name", "Element Label", "IntPt", "X", "Y", "Z", "Section Name", "Material Name",
              "Section Point", f"S-{quantity}"]
    lines = [header]
    for element, layer, face, x, y, value in rows:
        if face not in FACE_FRACTION:
            raise ReportError(f"element {element} layer {layer}: face {face!r} is not SNEG, SPOS or SMID")
        point = f"shell < composite > < elset = {section} > : {face}, (fraction = {FACE_FRACTION[face]}), Layer = {layer}"
        lines.append([odb, step, frame, instance, str(element), "1", f"{x:.9g}", f"{y:.9g}", "0.", section, material, point, f"{value:.9g}"])
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(lines)


def instance_in_deck(report: FieldReport, deck: Deck) -> str:
    """The deck's spelling of the report's instance (Abaqus/CAE upper-cases it in reports)."""
    for name in deck.instances:
        if name.upper() == report.instance.upper():
            return name
    raise ReportError(f"{Path(report.path).name}: instance {report.instance!r} is not in the deck ({', '.join(deck.instances)})")


def report_quantities(reports: list[FieldReport], deck: Deck, elements: list[int] | None = None) -> dict:
    """The `[expected]` tables several reports of one model give, for the element labels asked for (all reported by default):
    `ply_stress_local` rows `[S11, S22, S12]` with `nan` for a component no report carries, and `ply_mises`."""
    if not reports:
        raise ReportError("no reports")
    first = reports[0]
    for report in reports[1:]:
        for field in ("odb", "step", "frame", "instance"):
            if getattr(report, field) != getattr(first, field):
                raise ReportError(f"{Path(report.path).name}: {field} {getattr(report, field)!r} differs from {Path(first.path).name}'s {getattr(first, field)!r}")
    quantities = [r.quantity for r in reports]
    if len(set(quantities)) != len(quantities):
        raise ReportError(f"the same quantity is given twice: {quantities}")
    instance = instance_in_deck(first, deck)
    labels = sorted(first.centroids) if elements is None else list(elements)
    for element in labels:
        for report in reports:
            if element not in report.centroids:
                raise ReportError(f"element {element} is not in {Path(report.path).name}")
    expected: dict = {}
    for element in labels:
        name = f"{instance}.{element}"
        layers = sorted({layer for report in reports for (e, layer) in report.values if e == element})
        for layer in layers:
            for report in reports:
                group, component = QUANTITIES[report.quantity]
                length = 3 if group == "ply_stress_local" else 1
                row = expected.setdefault(group, {}).setdefault(name, {}).setdefault(str(layer), [math.nan] * length)
                if (element, layer) in report.values:
                    row[component] = report.values[(element, layer)]
    return expected
