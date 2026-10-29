"""Comparison records: the numbers an independent solver produced for one of our models, with provenance, checked
against our kernel (ADR-0030, ADR-0007).

A record is a TOML file among a test folder's records (`fea/checks/<test>/records/`, or a coupon's local `.local/fea/<coupon>/ours/verification/`, ADR-0036, ADR-0042, ADR-0040 amendment 3):

    title = "..."
    units = "mm-MPa"
    spec = "../specs/unnotched-im7-8552-nodal.toml"
    deck_kernel = "../decks/unnotched-im7-8552-nodal-abaqus.inp"         # read by our reader; order 1
    deck_reference = "../decks/unnotched-im7-8552-nodal-ccx.inp"          # what the reference solver ran; order 2
    deck_kernel_sha256 = "..."                                                   # both digests are checked before comparing
    deck_reference_sha256 = "..."

    [solver]
    name = "calculix"              # calculix | abaqus
    version = "2.22"
    element_type = "S8R"
    run_by = "..."
    run_date = "2026-10-15"
    machine = "..."
    source = "dat"                 # dat | rpt | csv (an Abaqus/CAE field report, abaqus_report.py)
    conventions = "_calculix-conventions.toml"
    notes = "..."

    [known_differences]
    kernel = "..."
    reference = "..."

    [expected]                     # the cases.py grammar; the numbers are the reference solver's, in the deck's units
    tolerance = 0.03               # relative to |expected| ...
    floor = 0.02                   # ... but never tighter than tolerance x floor x the group's largest magnitude
    [expected.rf] ...

The kernel passes the record when every number agrees within `tolerance` of the reference value, or within
`tolerance * floor * scale` for components that are small against their group (a 1 MPa shear stress beside a
1000 MPa axial stress is judged against the group, not against itself). `record_from_dat` builds the `[expected]`
tables from a CalculiX `.dat` using the detected conventions, and `record_from_report` from Abaqus/CAE field reports,
so a committed record is numbers plus provenance. A `nan` component was not reported by the solver and is skipped.
"""

from __future__ import annotations

import hashlib
import math
import tomllib
from pathlib import Path

import numpy as np

from anisotropy_engine.cases import Comparison
from anisotropy_engine.rotation import strain_transformation, stress_transformation

from .calculix import DatResults
from .cases import GROUPS, PLY_GROUPS, element_name, fe_results, validate_case
from .femodel import FEModel
from .units import unit_factors

SOLVER_FIELDS = ("name", "version", "element_type", "run_by", "run_date", "machine", "source")
RECORD_FIELDS = ("title", "units", "spec", "deck_kernel", "deck_reference", "deck_kernel_sha256", "deck_reference_sha256", "solver", "expected")
CONVENTION_FIELDS = ("calculix_version", "layer_order", "points_per_layer_thickness", "in_plane_points", "point_order", "stress_axes", "shear_strain", "detected_on", "detected_by",
                     "pressure_label", "pressure_direction", "shell_set_totals")


class RecordError(ValueError):
    """A record is incomplete or its decks are not the ones it was made from."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_record(path: Path | str) -> dict:
    path = Path(path)
    with path.open("rb") as handle:
        record = tomllib.load(handle)
    record["_dir"] = str(path.parent)
    validate_record(record)
    return record


def validate_record(record: dict) -> None:
    for field in RECORD_FIELDS:
        if field not in record:
            raise RecordError(f"record needs {field!r}")
    unknown = set(record) - set(RECORD_FIELDS) - {"known_differences", "_dir"}
    if unknown:
        raise RecordError(f"record has unknown keys {sorted(unknown)}")
    solver = record["solver"]
    for field in SOLVER_FIELDS:
        if not isinstance(solver.get(field), str) or not solver[field]:
            raise RecordError(f"[solver] needs {field!r} as text")
    if solver["name"] not in ("calculix", "abaqus"):
        raise RecordError("[solver] name must be calculix or abaqus")
    if solver["source"] not in ("dat", "rpt", "csv"):
        raise RecordError("[solver] source must be dat, rpt or csv")
    expected = record["expected"]
    floor = expected.get("floor", 0.0)
    if not isinstance(floor, (int, float)) or not 0.0 <= floor < 1.0:
        raise RecordError("[expected] floor must be a number in [0, 1)")
    probe = {"title": record["title"], "source": "record", "units": record["units"], "mesh": {"deck": record["deck_kernel"]},
             "expected": {k: v for k, v in expected.items() if k != "floor"}}
    validate_case(probe)
    base = Path(record["_dir"])
    for key in ("deck_kernel", "deck_reference"):
        deck = (base / record[key]).resolve()
        if not deck.is_file():
            raise RecordError(f"{key}: {deck} does not exist")
        digest = sha256_of(deck)
        if digest != record[f"{key}_sha256"]:
            raise RecordError(f"{key}: {deck.name} has sha256 {digest[:16]}..., the record was made from {record[f'{key}_sha256'][:16]}...; "
                              "regenerate the record or the deck")


def record_as_case(record: dict) -> dict:
    solver = record["solver"]
    source = (f"{solver['name']} {solver['version']} ({solver['element_type']}) run by {solver['run_by']} on {solver['run_date']} "
              f"at {solver['machine']}, read from its .{solver['source']}")
    return {"title": record["title"], "source": source, "units": record["units"], "mesh": {"deck": record["deck_kernel"]},
            "expected": {k: v for k, v in record["expected"].items() if k != "floor"}, "_dir": record["_dir"]}


def compare_record(record: dict) -> tuple[list[Comparison], list[str]]:
    """Every reference number next to the kernel's, with the floor rule for small components."""
    case = record_as_case(record)
    expected = record["expected"]
    tolerance, floor = float(expected["tolerance"]), float(expected.get("floor", 0.0))
    try:
        numbers, identities = fe_results(case)
    except ValueError as exc:
        return [], [str(exc)]
    comparisons: list[Comparison] = []
    problems: list[str] = []

    def add(label: str, want: list) -> None:
        if label not in numbers:
            problems.append(f"{label}: not a result the kernel produces for this record")
            return
        got, scale = numbers[label]
        for i, w in enumerate(want):
            if isinstance(w, float) and math.isnan(w):
                continue  # not reported by the reference solver
            allowed = tolerance * max(abs(w), floor * scale)
            comparisons.append(Comparison(f"{label}[{i}]", float(w), float(got[i]), float(allowed)))

    for group, rows in expected.items():
        if group in ("tolerance", "floor"):
            continue
        if group in GROUPS:
            for name, want in rows.items():
                for label in ([key for key in numbers if key.startswith(f"{group}[")] if name == "*" else [f"{group}[{name}]"]):
                    add(label, want)
        elif group in PLY_GROUPS:
            for name, plies in rows.items():
                for ply, want in plies.items():
                    add(f"{group}[{name}][{ply}]", want)
        elif group == "fpf":
            for criterion, fields in rows.items():
                add(f"fpf[{criterion}][ratio]", [fields["ratio"]])
    return comparisons, problems


def record_disagreements(record: dict) -> list[str]:
    comparisons, problems = compare_record(record)
    solver = record["solver"]["name"]
    return problems + [f"{c.key}: {solver} gives {c.expected:.6g}, kernel gives {c.engine:.6g} (allowed difference {c.allowed:.3g})"
                       for c in comparisons if not c.agrees]


# --- building a record from a CalculiX .dat -----------------------------------------------------


def load_conventions(path: Path | str) -> dict:
    with Path(path).open("rb") as handle:
        conventions = tomllib.load(handle)
    missing = [field for field in CONVENTION_FIELDS if field not in conventions]
    if missing:
        raise RecordError(f"conventions file lacks {missing}")
    if conventions["layer_order"] != "first-line-bottom":
        raise RecordError(f"layer order {conventions['layer_order']!r} is not implemented by the layer mapper")
    if conventions["stress_axes"] != "global":
        raise RecordError("the mapper expects stresses printed in global axes (*EL PRINT, GLOBAL=YES)")
    return conventions


def layer_values(block_values: np.ndarray, z: np.ndarray, plies: int, points_per_layer: int) -> list[np.ndarray]:
    """Mean of the integration-point rows of each ply, plies bottom-first, by the points' z coordinates."""
    levels = np.unique(np.round(z, 9))
    if levels.size != plies * points_per_layer:
        raise RecordError(f"expected {plies * points_per_layer} z levels for {plies} plies, found {levels.size}")
    out = []
    for k in range(plies):
        rows = np.flatnonzero(np.isin(np.round(z, 9), levels[k * points_per_layer:(k + 1) * points_per_layer]))
        out.append(block_values[rows].mean(axis=0))
    return out


def layer_face_values(block_values: np.ndarray, z: np.ndarray, plies: int, points_per_layer: int, interfaces: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """The value on the bottom and top face of each ply, plies bottom-first: a straight line in z through the ply's integration
    points (two levels per layer, each the mean of its in-plane points), extended to the ply's faces at the z of `interfaces` (plies + 1
    values from the bottom face up, in the .dat's length unit). Exact for a value that varies linearly through the ply, as a shell's
    in-plane stress does under bending (ADR-0053)."""
    levels = np.unique(np.round(z, 9))
    if levels.size != plies * points_per_layer:
        raise RecordError(f"expected {plies * points_per_layer} z levels for {plies} plies, found {levels.size}")
    if points_per_layer < 2:
        raise RecordError("a face value needs at least two integration levels per layer")
    out = []
    for k in range(plies):
        mine = levels[k * points_per_layer:(k + 1) * points_per_layer]
        means = np.array([block_values[np.flatnonzero(np.round(z, 9) == level)].mean(axis=0) for level in mine])
        slope, intercept = np.polyfit(mine, means, 1)  # one straight line per component
        bottom, top = interfaces[k], interfaces[k + 1]
        out.append((slope * bottom + intercept, slope * top + intercept))
    return out


def reference_quantities(model: FEModel, dat: DatResults, conventions: dict,
                         element_probes: list[str] | None = None, node_probes: list[str] | None = None, reactions: bool = True) -> dict:
    """The `[expected]` tables a CalculiX run gives for a model: reactions, the displacements of the node probes named (all by
    default), and for the element probes named (all by default) the mean strain, per-ply stresses and per-ply strains.
    Node and element keys carry the model's instance name, as the kernel deck written from the same model does."""
    instance = model.instance
    shear = 2.0 if conventions["shear_strain"] == "tensor" else 1.0
    per_layer = int(conventions["points_per_layer_thickness"])
    bending = model.bending  # a bending coupon's record holds RFz, w and both faces of every ply (ADR-0053)
    expected: dict = {}
    rf = {}
    for grip in model.support_sets if reactions else ():  # left out when a shell set's printed total is known to be incomplete (the conventions file)
        try:
            total = dat.total_force(grip)
        except KeyError:
            continue
        rf[grip] = [float(total[2])] if bending else [float(total[0]), float(total[1])]
    if rf:
        expected["rf_z" if bending else "rf"] = rf
    u = {}
    for name, index in model.probe_nodes.items():
        if node_probes is not None and name not in node_probes:
            continue
        block = dat.displacements(f"Probe-{name}")
        values = block.row(index + 1)
        u[f"{instance}.{index + 1}"] = [float(values[2])] if bending else [float(values[0]), float(values[1])]
    if u:
        expected["w" if bending else "u"] = u
    plies = model.section.plies
    angles = [p.angle_deg for p in plies]
    strain, stress_local, strain_local = {}, {}, {}
    for name, index in model.probe_elements.items():
        if element_probes is not None and name not in element_probes:
            continue
        label = element_name((instance, index + 1))
        S, E, C = dat.stresses(f"Probe-{name}"), dat.strains(f"Probe-{name}"), dat.coordinates(f"Probe-{name}")
        z = C.values[:, 2]
        if bending:
            thickness = sum(p.thickness_m for p in plies)
            unit = unit_factors(model.spec.units)["length"]
            interfaces = (np.concatenate([[-thickness / 2.0], -thickness / 2.0 + np.cumsum([p.thickness_m for p in plies])])) / unit
            stresses = layer_face_values(S.values[:, [0, 1, 3]], z, len(plies), per_layer, interfaces)
            strains = layer_face_values(E.values[:, [0, 1, 3]], z, len(plies), per_layer, interfaces)
            stress_local[label] = {f"{k + 1}:{face}": [float(v) for v in stress_transformation(angles[k]) @ s]
                                   for k, pair in enumerate(stresses) for face, s in zip(("bottom", "top"), pair)}
            strain_local[label] = {f"{k + 1}:{face}": [float(v) for v in strain_transformation(angles[k]) @ (e * np.array([1.0, 1.0, shear]))]
                                   for k, pair in enumerate(strains) for face, e in zip(("bottom", "top"), pair)}
            continue
        mean = E.values[:, [0, 1, 3]].mean(axis=0)
        strain[label] = [float(mean[0]), float(mean[1]), float(shear * mean[2])]
        stresses = layer_values(S.values[:, [0, 1, 3]], z, len(plies), per_layer)
        strains = layer_values(E.values[:, [0, 1, 3]], z, len(plies), per_layer)
        stress_local[label] = {str(k + 1): [float(v) for v in stress_transformation(angles[k]) @ s] for k, s in enumerate(stresses)}
        strain_local[label] = {str(k + 1): [float(v) for v in strain_transformation(angles[k]) @ (e * np.array([1.0, 1.0, shear]))]
                               for k, e in enumerate(strains)}
    if strain:
        expected["strain"] = strain
    if stress_local:
        expected["ply_stress_local"] = stress_local
        expected["ply_strain_local"] = strain_local
    return expected


def format_record(record: dict) -> str:
    """The record as TOML text (tomllib reads, it does not write)."""

    def value(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float) and math.isnan(v):
            return "nan"
        if isinstance(v, (int, float)):
            return repr(float(v)) if isinstance(v, float) else str(v)
        if isinstance(v, list):
            return "[" + ", ".join(value(x) for x in v) + "]"
        return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = [f"{key} = {value(record[key])}" for key in ("title", "units", "spec", "deck_kernel", "deck_reference", "deck_kernel_sha256", "deck_reference_sha256")]
    lines += ["", "[solver]"] + [f"{k} = {value(v)}" for k, v in record["solver"].items()]
    if record.get("known_differences"):
        lines += ["", "[known_differences]"] + [f"{k} = {value(v)}" for k, v in record["known_differences"].items()]
    expected = record["expected"]
    lines += ["", "[expected]", f"tolerance = {value(expected['tolerance'])}"]
    if "floor" in expected:
        lines.append(f"floor = {value(expected['floor'])}")
    for group, rows in expected.items():
        if group in ("tolerance", "floor"):
            continue
        if group in PLY_GROUPS:
            for name, plies in rows.items():
                # a ply number is a bare key; a face key such as 1:bottom must be quoted
                lines += ["", f'[expected.{group}."{name}"]'] + [f"{ply if str(ply).isdigit() else value(ply)} = {value(v)}" for ply, v in plies.items()]
        elif group == "fpf":
            for criterion, fields in rows.items():
                lines += ["", f"[expected.fpf.{criterion}]"] + [f"{k} = {value(v)}" for k, v in fields.items()]
        else:
            lines += ["", f"[expected.{group}]"] + [f'"{name}" = {value(v)}' for name, v in rows.items()]
    return "\n".join(lines) + "\n"
