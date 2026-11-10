"""Abaqus's numbers beside ours for the validation table (ADR-0066 amendment 1): the run's `.dat` of our own deck, read at the places
the table compares, in the fields' units.

The deck prints, at each probe element, the section forces and strains (`SF`, `SE`) and every layer's middle section point of the
stresses and strains (`S`, `E`; the middle of layer k is point 3k - 1 at three Simpson points per layer, `write_abaqus.SECTION_POINTS`),
and the reaction at the moving grip's reference node (`*Node Print ... totals=YES`, `RF`). The deck's `*Orientation` puts a layer's
axis 1 along the coupon (global +y) and axis 2 along -x, so a layer's `S11, S22, S12` are the ply's σ₁, σ₂, τ₁₂ as we define them, and
the section strains read `SE1 = ε_y`, `SE2 = ε_x`, `SE3 = -γ_xy` (a quarter turn flips the sign of the engineering shear). Our side is
the kernel on the same deck, at the same gauge element, through `report.laminate_check`. Agreement is the CalculiX record's rule
(`compare`): within `tolerance` of Abaqus's value, or of `floor` times the group's largest magnitude for a small component. Nothing is
read off a legend or a contour: every number is a printed one (ADR-0002); a `.dat` that prints the faces instead of the middles, an
older deck, is refused with what it printed (ADR-0003).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np

from .abaqus_dat import AbaqusDat, AbaqusDatError, parse_abaqus_dat
from .abaqus_reader import parse_deck
from .kernel import solve_deck
from .model import to_si
from .report import laminate_check
from .units import deck_units_of, from_si
from .units import to_si as scalar_to_si
from .write_abaqus import SECTION_POINTS

TOLERANCE, FLOOR = 0.03, 0.02  # the CalculiX record's (tools/run_coupon.py)
REACTION_PRINT = re.compile(r"^\*Node Print\s*,\s*nset\s*=\s*([^,\s]+)\s*,\s*totals\s*=\s*YES", re.IGNORECASE | re.MULTILINE)
MIDDLE = (SECTION_POINTS + 1) // 2  # the middle point's rank within a layer, 1-based


def signed(reference: float, ours: float) -> str:
    return f"{100 * (ours - reference) / abs(reference):+.2f} %" if reference else "--"


def agrees(reference: float, ours: float, scale: float, tolerance: float, floor: float) -> bool:
    return abs(ours - reference) <= tolerance * max(abs(reference), floor * scale)


def layer_of(point: int) -> int | None:
    """The layer whose middle section point this is, 1-based; None for a face point."""
    layer, rank = divmod(point - 1, SECTION_POINTS)
    return layer + 1 if rank + 1 == MIDDLE else None


def abaqus_beside(deck_path: Path | str, dat_text: str, units: str, dat_name: str = "run.dat", tolerance: float = TOLERANCE,
                  floor: float = FLOOR) -> dict:
    """`summary.abaqus` for a fields file in `units`: the reaction, the gauge strain and every ply's σ₁ σ₂ τ₁₂ at the gauge element,
    Abaqus's and ours, each marked as agreeing or not. Raises AbaqusDatError for a `.dat` that does not hold them."""
    deck_path = Path(deck_path)
    deck_text = deck_path.read_text(encoding="utf-8")
    deck_units = deck_units_of(units)
    deck = to_si(parse_deck(deck_text, source_path=deck_path.name), deck_units)
    solution = solve_deck(deck)
    check = laminate_check(deck, solution)
    dat = parse_abaqus_dat(dat_text)
    if not dat.tables:
        raise AbaqusDatError("the .dat prints no table: it is not the output of our deck, whose step asks for *El Print and *Node Print")
    label = int(check.gauge.name.split(".")[-1])
    to_fields = lambda value, kind: from_si(scalar_to_si(np.asarray(value), kind, deck_units), kind, units)  # deck units -> SI -> the fields' units
    kernel = lambda value, kind: from_si(np.asarray(value), kind, units)

    # the reaction: the TOTAL of the moving grip's reference set, dof 2 along the pull
    match = REACTION_PRINT.search(deck_text)
    if not match:
        raise AbaqusDatError("the deck asks for no *Node Print with totals=YES, so the .dat has no reaction to read")
    reaction_set = match[1]
    rf = dat.find("node", reaction_set, "RF2")
    total = rf.total if rf.total is not None else tuple(sum(row.values[i] for row in rf.rows) for i in range(len(rf.columns)))
    abaqus_reaction = float(to_fields(total[rf.column("RF2")], "force"))
    ours_reaction = float(kernel(check.kernel_reaction_N, "force"))
    reaction = {"abaqus": abaqus_reaction, "ours": ours_reaction, "difference": signed(abaqus_reaction, ours_reaction),
                "agrees": agrees(abaqus_reaction, ours_reaction, abs(abaqus_reaction), tolerance, floor)}

    # the ply stresses: the S table that holds the gauge element, one row per layer middle
    tables = dat.element_tables_with("S11", label)
    if not tables:
        raise AbaqusDatError(f"the .dat prints no S11 table with a row for element {label}, the gauge-centre element; it prints "
                             + (", ".join(f"{t.set_name} ({len(t.rows)} rows)" for t in dat.tables if t.kind == "element") or "no element table"))
    stress = tables[-1]
    columns = [stress.column(name) for name in ("S11", "S22", "S12")]
    plies = len(check.angles_deg)
    by_layer: dict[int, tuple[float, ...]] = {}
    faces = []
    for row in stress.of(label):
        layer = layer_of(row.point) if row.point is not None else None
        if layer is None:
            faces.append(row.point)
            continue
        by_layer[layer] = tuple(row.values[c] for c in columns)
    missing = [k for k in range(1, plies + 1) if k not in by_layer]
    if missing:
        raise AbaqusDatError(f"the .dat prints section points {sorted(faces)} at element {label}, not the middle of every layer "
                             f"(points {', '.join(str(SECTION_POINTS * (k - 1) + MIDDLE) for k in range(1, plies + 1))}): layers {missing} are missing; "
                             "the deck predates the section-point list, so download it again and rerun")
    ours_stress = kernel(check.kernel_ply_stress_12, "stress")  # (plies, 3)
    abaqus_stress = np.array([to_fields(by_layer[k], "stress") for k in range(1, plies + 1)])
    scale = float(np.max(np.abs(abaqus_stress)))
    gauge = []
    for k in range(plies):
        gauge.append({"ply": k + 1, "angle": float(check.angles_deg[k]), "abaqus": [float(v) for v in abaqus_stress[k]], "ours": [float(v) for v in ours_stress[k]],
                      "agrees": [agrees(float(abaqus_stress[k, i]), float(ours_stress[k, i]), scale, tolerance, floor) for i in range(3)]})

    # the gauge strain: the section strains of the same element, turned from the layup's axes to the coupon's
    section = dat.element_tables_with("SE1", label)
    strain = None
    if section:
        row = section[-1].of(label)[-1]
        se = [row.values[section[-1].column(name)] for name in ("SE1", "SE2", "SE3")]
        abaqus_strain = [se[1], se[0], -se[2]]
        ours_strain = [float(v) for v in check.kernel_strain]
        strain_scale = max(abs(v) for v in abaqus_strain)
        strain = {"abaqus": abaqus_strain, "ours": ours_strain,
                  "agrees": [agrees(abaqus_strain[i], ours_strain[i], strain_scale, tolerance, floor) for i in range(3)]}

    marks = [reaction["agrees"]] + [m for g in gauge for m in g["agrees"]] + (strain["agrees"] if strain else [])
    return {"solver": dat.version or "Abaqus", "dat": dat_name, "dat_sha256": hashlib.sha256(dat_text.encode("utf-8")).hexdigest(),
            "deck": deck_path.name, "deck_sha256": hashlib.sha256(deck_text.encode("utf-8")).hexdigest(), "units": units,
            "tolerance": tolerance, "floor": floor, "agree": f"{sum(marks)} of {len(marks)}", "reaction": reaction, "reaction_set": reaction_set,
            "gauge_element": check.gauge.name, "gauge": gauge, "gauge_strain": strain,
            "note": "the run's .dat of our deck: centroid values at each layer's middle section point, in the ply's axes; the section strains turned to the coupon's axes; "
                    "the reaction as the TOTAL of the moving grip's reference node"}
