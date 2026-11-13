"""CalculiX's own numbers beside ours, for the studio's Summary (ADR-0030 amendment 6).

The page used to show our engine's ply stresses alone, in the fibre axes at element centroids, and the engineer who opened the
CalculiX `.frd` in PrePoMax saw other numbers: global axes, nodes of the expanded bricks, a three-dimensional von Mises. Both peak
at the tab line, a clamped edge whose stress grows as the mesh is refined; in the gauge section the two solvers agree. So the page
now says three things, each from a file the run wrote: the reaction, ours and CalculiX's; the gauge section's ply stresses, ours and
CalculiX's in the fibre axes at the recorded probe (the comparison record, read from the `.dat`); and the peaks, ours at element
centroids and CalculiX's at nodes as PrePoMax shows them (the record's `[frd]` block). Every number here is read from those files
and converted once into the fields' unit system; none is computed here (ADR-0001), but for a coupon that names a test standard, whose
chord modulus from CalculiX's reaction and its displacements at the strain measurement's ends goes through the same functions as ours
(`test_quantities`, ADR-0072)."""

from __future__ import annotations

from pathlib import Path

from .case_pages import record_rows, signed
from .femodel import build_model
from .test_quantities import STRAIN_PROBES, chord_modulus, engineering_stress, extensometer_strain, gross_area, method_inputs
from .units import from_si, to_si

GAUGE_GROUP = "ply_stress_local"
REACTION_SET = "Grip-Top"
FRD_STRESSES = ("mises_max", "sxx_max", "sxx_min", "syy_max", "syy_min", "sxy_max_abs", "gauge_mises_max", "gauge_syy_max", "gauge_sxx_max_abs")
FRD_LENGTHS = ("gauge_from", "gauge_to")
PLY_STRESSES = ("s1_max", "s2_max", "t12_max_abs", "s1_max_abs", "s2_max_abs", "gauge_s1_max")


def convert(value, kind: str, from_units: str, to_units: str):
    if from_units == to_units or value is None:
        return value
    return from_si(to_si(value, kind, from_units), kind, to_units)


def extensometer_of(twin_spec) -> tuple[tuple[str, str], tuple[float, float], float] | None:
    """The CalculiX twin's probe nodes at the strain measurement's ends (their labels and their y in SI) and the coupon's gross area, for
    CalculiX's chord modulus beside ours (ADR-0072); None for a coupon without a strain measurement. The spec must be in SI."""
    inputs = method_inputs(twin_spec)
    if inputs is None or not all(name in twin_spec.probes.nodes for name in STRAIN_PROBES):
        return None
    model = build_model(twin_spec)
    index = [model.probe_nodes[name] for name in STRAIN_PROBES]
    return (tuple(f"{model.instance}.{i + 1}" for i in index), tuple(float(model.mesh.xy[i, 1]) for i in index),
            gross_area(inputs.width, inputs.thickness))


def calculix_test_method(rows, record_units: str, units: str, nodes: tuple[str, str], positions: tuple[float, float], area: float) -> dict | None:
    """CalculiX's strain at the strain measurement and its chord modulus (ADR-0072), from the record's reaction at the moving grip and its
    displacements along the coupon at the two probe nodes (`nodes`, the twin's labels; `positions`, their y in SI); `area` in SI. None when
    the record does not hold them."""
    reaction = [r for r in rows if r.group == "rf" and r.name == REACTION_SET and r.component == 1]
    moved = {r.name: r for r in rows if r.group == "u" and r.name in nodes and r.component == 1}
    if not reaction or len(moved) != 2:
        return None
    out = {}
    for who, pick in (("calculix", lambda r: r.reference), ("ours", lambda r: r.kernel)):
        force = to_si(pick(reaction[0]), "force", record_units)
        v_bottom, v_top = (to_si(pick(moved[name]), "length", record_units) for name in nodes)
        strain = extensometer_strain(v_bottom, v_top, *positions)
        modulus = chord_modulus(engineering_stress(force, area), strain)[2]
        out[who] = {"strain": float(strain), "modulus": float(from_si(modulus, "modulus", units))}
    out["agrees"] = all(moved[name].agrees for name in nodes) and reaction[0].agrees
    out["difference"] = signed(out["calculix"]["modulus"], out["ours"]["modulus"])
    out["nodes"] = list(nodes)
    return out


def calculix_summary(record_path: Path, units: str, extensometer: tuple[tuple[str, str], tuple[float, float], float] | None = None) -> dict:
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
        strain = [r for r in rows if r.group == "strain" and r.name == element]
        if strain:  # the gauge element's mean strain, ours and CalculiX's, a unitless row of the validation table (ADR-0066)
            entry = {"ours": [None, None, None], "calculix": [None, None, None], "agrees": [None, None, None]}
            for r in strain:
                entry["ours"][r.component], entry["calculix"][r.component], entry["agrees"][r.component] = r.kernel, r.reference, r.agrees
            out["gauge_strain"] = entry
    if extensometer is not None:  # the twin's probe nodes at the strain measurement's ends, their y and the area (ADR-0072)
        out["test_method"] = calculix_test_method(rows, record_units, units, *extensometer)
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
        if converted.get("plies"):  # each ply's peaks in its fibre axes (ADR-0066): the stresses and the positions convert, the nodes and angles do not
            converted["plies"] = [{k: ([convert(v, "length", record_units, units) for v in x] if k.endswith("_xyz") else
                                       convert(x, "stress", record_units, units) if k in PLY_STRESSES else x) for k, x in ply.items()}
                                  for ply in converted["plies"]]
        out["frd"] = converted
    return out
