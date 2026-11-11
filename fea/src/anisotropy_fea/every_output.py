"""Every output Abaqus shows for a composite shell coupon, from our kernel, element by element and ply by ply, with the coupon's zones
(ADR-0066 amendment 2, ADR-0089). `tools/abaqus_compare.py` reads it beside an Abaqus run; the package writes it for the team's engineers,
who run `tools/compare_every_output.py` on it beside their own Abaqus run (ADR-0089 amendment 3).

The values are the kernel's own at each element's centroid, one per ply (the membrane state is the same through a ply), in the deck's
units: S11, S22, S12 in the ply's material axes, Mises, Tresca, the pressure and the three principal stresses as Abaqus orders them, and
the strains E11, E22, E12 (E12 the engineering shear strain, as Abaqus prints it). The zones are the comparison's: the gauge (the
extensometer's length at mid-length), the free length beyond one coupon width from a tab line, the band within that width, the elements
on a tab line (the clamped edge: reported, not judged, ADR-0066), and the gripped tabs.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from anisotropy_fea.recovery import element_ply_states, ply_invariants, ply_mises
from anisotropy_fea.units import UNIT_LABEL, from_si

QUANTITIES = ("S11", "S22", "S12", "Mises", "Tresca", "Pressure", "Max. Principal", "Mid. Principal", "Min. Principal", "E11", "E22", "E12")
INVARIANT_OF = {"Tresca": "tresca", "Pressure": "pressure", "Max. Principal": "max_principal", "Mid. Principal": "mid_principal",
                "Min. Principal": "min_principal"}
ZONES = ("gauge", "free length", "band", "tab line", "gripped")
FLOOR = 0.02  # a small value is judged against 2 % of its quantity's largest magnitude in the gauge (ADR-0066's records)
# ADR-0089's acceptance: the reaction and every gauge value within 1 %, every free-length value within 3 %; the rest reported
ACCEPTANCE = {"reaction": 0.01, "gauge": 0.01, "free length": 0.03}
REPORTED = ("band", "tab line", "gripped")
# the columns of `tools/abaqus_every_output.py`'s CSV, in its order, then the zone: the two files line up column by column
COLUMNS = ("Element", "Layer", "Section Point", "X", "Y", *QUANTITIES, "Zone")
ZONE_WORDS = {"gauge": "the extensometer's length at mid-length",
              "free length": "between the grips, beyond one coupon width from a tab line",
              "band": "within one coupon width of a tab line",
              "tab line": "the elements touching a tab line, the clamped edge",
              "gripped": "inside the tabs, held by the grips"}


def ours_by_element(solution, units: str) -> dict[int, dict[str, np.ndarray]]:
    """Our kernel's values per element label: each quantity as an array over the plies, bottom ply first, in the deck's units."""
    field = element_ply_states(solution)
    mises = ply_mises(field)
    invariants = ply_invariants(field)
    stress = lambda v: from_si(np.asarray(v, dtype=float), "stress", units)  # noqa: E731
    out = {}
    for e, key in enumerate(solution.mesh.element_keys):
        s = field.stress_12[e]
        values = {"S11": stress(s[:, 0]), "S22": stress(s[:, 1]), "S12": stress(s[:, 2]), "Mises": stress(mises[e][:, 0])}
        for name, inner in INVARIANT_OF.items():
            values[name] = stress(invariants[inner][e])
        strain = field.strain_12[e]
        values.update(E11=strain[:, 0], E22=strain[:, 1], E12=strain[:, 2])
        out[int(key[1])] = values
    return out


def zone_bounds(spec, units: str) -> dict[str, float]:
    """The lines the zones are drawn by, along the coupon's length, in the deck's units."""
    length = lambda v: float(from_si(v, "length", units))  # noqa: E731
    g = spec.geometry
    L, W, tab = length(g.length), length(g.width), length(g.tab_length or 0.0)
    half = length(spec.strain.gauge_length) / 2 if spec.strain is not None else W / 2
    return {"length": L, "width": W, "tab_length": tab, "gauge_from": L / 2 - half, "gauge_to": L / 2 + half}


def zones_of(spec, mesh, units: str) -> dict[int, str]:
    """Each element's zone, by element label, from its corner nodes on the kernel's mesh, in the deck's units."""
    b = zone_bounds(spec, units)
    L, W, tab = b["length"], b["width"], b["tab_length"]
    corners = np.asarray(mesh.connectivity)[:, :4]
    out = {}
    for e, key in enumerate(mesh.element_keys):
        ys = [float(from_si(mesh.xy[n][1], "length", units)) for n in corners[e]]
        y = sum(ys) / len(ys)
        on_line = any(abs(v - tab) < 1e-6 or abs(v - (L - tab)) < 1e-6 for v in ys)
        if y < tab or y > L - tab:
            zone = "gripped"
        elif on_line:
            zone = "tab line"
        elif y < tab + W or y > L - tab - W:
            zone = "band"
        elif b["gauge_from"] <= y <= b["gauge_to"]:
            zone = "gauge"
        else:
            zone = "free length"
        out[int(key[1])] = zone
    return out


def centroids_of(mesh, units: str) -> dict[int, tuple[float, float]]:
    """Each element's centroid, the mean of its corner nodes, as Abaqus's exporter takes it, by element label, in the deck's units."""
    corners = np.asarray(mesh.connectivity)[:, :4]
    out = {}
    for e, key in enumerate(mesh.element_keys):
        x, y = from_si(mesh.xy[corners[e]].mean(axis=0), "length", units)
        out[int(key[1])] = (float(x), float(y))
    return out


def top_reaction(solution, spec, units: str) -> tuple[int, float]:
    """The pull's reaction along the coupon: the kernel's reaction summed over the nodes of the top grip (at or above the top tab line),
    and how many nodes that is; Abaqus's RF2 over the same nodes is its counterpart."""
    top = zone_bounds(spec, units)["length"] - zone_bounds(spec, units)["tab_length"]
    ys = from_si(np.asarray(solution.mesh.xy)[:, 1], "length", units)
    nodes = np.flatnonzero(ys >= top - 1e-6)
    return int(nodes.size), float(from_si(float(np.sum(np.asarray(solution.reaction)[nodes, 1])), "force", units))


def number(value: float) -> str:
    return f"{float(value):.9g}"


def write_ours(csv_path: Path, json_path: Path, spec, solution, units: str, coupon: str, element: str, version: str) -> int:
    """Our every-output file for the team: one row per element and ply in `tools/abaqus_every_output.py`'s columns, then the zone; and
    beside it the JSON the comparison reads (the zones' lines, our reaction, the floor and the acceptance). Returns the rows written."""
    ours = ours_by_element(solution, units)
    zones = zones_of(spec, solution.mesh, units)
    centroids = centroids_of(solution.mesh, units)
    rows = 0
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for label in sorted(ours):
            values = ours[label]
            x, y = centroids[label]
            for k in range(len(values["S11"])):
                writer.writerow([label, k + 1, f"middle of layer {k + 1}", number(x), number(y),
                                 *(number(values[q][k]) for q in QUANTITIES), zones[label]])
                rows += 1
    nodes, reaction = top_reaction(solution, spec, units)
    b = zone_bounds(spec, units)
    label = UNIT_LABEL[units]
    meta = {"coupon": coupon, "units": units, "length_unit": label["length"], "stress_unit": label["stress"], "force_unit": label["force"],
            "element": element,
            "elements": len(ours), "layers": len(next(iter(ours.values()))["S11"]), "rows": rows, "quantities": list(QUANTITIES),
            "zones": {zone: ZONE_WORDS[zone] for zone in ZONES}, "lines": b,
            "reaction": {"along": "Y", "top_from": b["length"] - b["tab_length"], "nodes": nodes, "ours": reaction},
            "floor": FLOOR, "acceptance": ACCEPTANCE, "reported": list(REPORTED), "written_by": f"anisotropy-fea {version}"}
    json_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8", newline="\n")
    return rows
