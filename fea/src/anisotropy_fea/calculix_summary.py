"""CalculiX's own numbers beside ours, for the studio's Summary (ADR-0030 amendment 6).

The page used to show our engine's ply stresses alone, in the fibre axes at element centroids, and the engineer who opened the
CalculiX `.frd` in PrePoMax saw other numbers: global axes, nodes of the expanded bricks, a three-dimensional von Mises. Both peak
at the tab line, a clamped edge whose stress grows as the mesh is refined; in the gauge section the two solvers agree. So the page
now says three things, each from a file the run wrote: the reaction, ours and CalculiX's; the gauge section's ply stresses, ours and
CalculiX's in the fibre axes at the recorded probe (the comparison record, read from the `.dat`); and the peaks, ours at element
centroids and CalculiX's at nodes as PrePoMax shows them (the record's `[frd]` block). Every number here is read from those files
and converted once into the fields' unit system; none is computed here (ADR-0001)."""

from __future__ import annotations

from pathlib import Path

from .case_pages import record_rows, signed
from .units import from_si, to_si

GAUGE_GROUP = "ply_stress_local"
REACTION_SET = "Grip-Top"
FRD_STRESSES = ("mises_max", "sxx_max", "sxx_min", "syy_max", "syy_min", "sxy_max_abs", "gauge_mises_max", "gauge_syy_max", "gauge_sxx_max_abs")
FRD_LENGTHS = ("gauge_from", "gauge_to")


def convert(value, kind: str, from_units: str, to_units: str):
    if from_units == to_units or value is None:
        return value
    return from_si(to_si(value, kind, from_units), kind, to_units)


def calculix_summary(record_path: Path, units: str) -> dict:
    """The record's reaction, gauge ply stresses and `.frd` peaks next to ours, in `units` (the fields' system). The reaction and the
    gauge rows come from the comparison the record already holds; `frd` is the record's block or None for a record made before it."""
    _, rows, record = record_rows(record_path)
    record_units = record["units"]
    out: dict = {"record": record_path.name, "units": units, "tolerance": float(record["expected"]["tolerance"]),
                 "agree": f"{sum(r.agrees for r in rows)} of {len(rows)}", "reaction": None, "gauge_element": None, "gauge": [], "frd": None}
    reaction = [r for r in rows if r.group == "rf" and r.name == REACTION_SET and r.component == 1]
    if reaction:
        r = reaction[0]
        out["reaction"] = {"calculix": convert(r.reference, "force", record_units, units), "ours": convert(r.kernel, "force", record_units, units),
                           "difference": signed(r.reference, r.kernel), "agrees": r.agrees}
    gauge = [r for r in rows if r.group == GAUGE_GROUP]
    if gauge:
        element = gauge[0].name
        plies: dict[int, dict] = {}
        for r in gauge:
            if r.name != element or r.ply is None:
                continue
            entry = plies.setdefault(r.ply, {"ply": r.ply, "ours": [None, None, None], "calculix": [None, None, None], "agrees": [None, None, None]})
            entry["ours"][r.component] = convert(r.kernel, "stress", record_units, units)
            entry["calculix"][r.component] = convert(r.reference, "stress", record_units, units)
            entry["agrees"][r.component] = r.agrees
        out["gauge_element"] = element
        out["gauge"] = [plies[k] for k in sorted(plies)]
    frd = record.get("frd")
    if frd:
        converted = dict(frd)
        for key in FRD_STRESSES:
            if key in converted:
                converted[key] = convert(converted[key], "stress", record_units, units)
        for key in FRD_LENGTHS:
            if key in converted:
                converted[key] = convert(converted[key], "length", record_units, units)
        for key in list(converted):
            if key.endswith("_xyz"):
                converted[key] = [convert(v, "length", record_units, units) for v in converted[key]]
        out["frd"] = converted
    return out
