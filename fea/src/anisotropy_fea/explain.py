"""The explanation the studio shows beside a result, written from the solve's summary by a template (ADR-0051).

Every number in a sentence is in the fact sheet first, and the sentence quotes it: the fact sheet is what a later assistant may
rephrase and what its guard checks against (ADR-0048, ADR-0052). The sheet holds each measured value at the precision the sentences
print, DIGITS significant figures, so a fact and its mention agree digit for digit and a writer that copies the sheet copies a
printable number (ADR-0052 amendment 1). The template never computes: it reads `fields.field_data`'s
summary and says, in the words the coupon document uses, what the coupon carries, where it moves most, which ply is stressed
most, and by each criterion whether the laminate exceeds it and which ply limits it, on which face when the coupon bends
(ADR-0053), where, and why.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .audit import CRITERION

NUMBER = re.compile(r"(?<![\w.\-+])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?(?![\w.])")  # a number on its own, not the digits of a name like Coupon-1.1068
MODE_WORDS = {  # the engine's governing modes, each with what it means for an engineer
    "longitudinal tension": "tension along the fibres (sigma_1 reaching F1t, a fibre-dominated mode)",
    "longitudinal compression": "compression along the fibres (sigma_1 reaching F1c, a fibre-dominated mode)",
    "transverse tension": "tension across the fibres (sigma_2 reaching F2t, a matrix-dominated mode)",
    "transverse compression": "compression across the fibres (sigma_2 reaching F2c, a matrix-dominated mode)",
    "in-plane shear": "in-plane shear (tau_12 reaching F6, a matrix-dominated mode)",
    "interactive": "the combined stresses (no single component governs)",
    "none": "no stress at all (the ply carries nothing there)",
}
AXIS_WORDS = {"x": "across the coupon", "y": "along the coupon", "z": "out of the plane (the deflection w)"}
# the ply stress components as the fields name them (the team's CAE names), said with their symbols: PrePoMax's S11 is another quantity (ADR-0066)
STRESS_WORDS = {"S11": "sigma_1 along the fibres", "S22": "sigma_2 across the fibres", "S12": "tau_12 in-plane shear"}
# an isotropic material is one layer whose axis 1 runs along the coupon (ADR-0075): no fibres to name
ISOTROPIC_WORDS = {"S11": "sigma_1 along the coupon", "S22": "sigma_2 across it", "S12": "tau_12 in-plane shear"}
DIGITS = 4


def number(value: float) -> str:
    return f"{value:.{DIGITS}g}"


def printed(value: float) -> float:
    """A measured value as the sheet keeps it: DIGITS significant figures, the same digits `number` prints (ADR-0052 amendment 1).
    Zero and a value that is not finite pass through."""
    if value == 0 or not math.isfinite(value):
        return value
    return float(f"{value:.{DIGITS - 1}e}")


def fact_sheet(summary: dict[str, Any], coupon: dict[str, Any], units: str, labels: dict[str, str]) -> dict[str, Any]:
    """Every number and word the sentences may use, flat, by name."""
    facts: dict[str, Any] = {
        "designation": coupon.get("designation") or "the coupon", "test": coupon.get("test") or "", "layup": coupon.get("layup") or "",
        "units": units, "length_unit": labels["length"], "force_unit": labels["force"], "stress_unit": labels["stress"],
        "control": summary["applied"]["control"], "applied": printed(abs(float(summary["applied"]["value"]))), "applied_unit": summary["applied"]["unit"],
        "applied_direction": summary["applied"].get("direction", "along the coupon"),
        "reaction": printed(abs(float(summary["reaction"]["value"]))), "sense": summary["reaction"]["sense"], "reaction_set": summary["reaction"].get("set", "the top grip"),
        "max_displacement": printed(float(summary["max_displacement"]["value"])), "max_displacement_node": summary["max_displacement"]["label"].rsplit(".", 1)[-1],
        "max_displacement_x": printed(float(summary["max_displacement"]["xy"][0])), "max_displacement_y": printed(float(summary["max_displacement"]["xy"][1])),
        "max_displacement_axis": summary["max_displacement"].get("axis", "y"),
        "isotropic": bool(summary.get("isotropic", False)),
    }
    for name, m in summary["max_ply"].items():
        if name == "mises":
            continue  # a ply's von Mises is not a laminate quantity (ADR-0066): the sheet leaves it out, so no sentence can quote it
        facts[f"max_{name}"] = printed(float(m["value"]))
        facts[f"max_{name}_ply"] = int(m["ply"])
        facts[f"max_{name}_angle"] = printed(float(m["angle"]))
        facts[f"max_{name}_element"] = m["label"].rsplit(".", 1)[-1]
        facts[f"max_{name}_face"] = m.get("face")
    facts["criteria"] = list(summary["fpf"])
    facts["earliest"] = summary.get("earliest")
    for criterion, f in summary["fpf"].items():
        facts[f"{criterion}_factor"] = printed(float(f["factor"]))
        facts[f"{criterion}_index"] = printed(float(f["index"]))
        facts[f"{criterion}_ply"] = int(f["ply"])
        facts[f"{criterion}_angle"] = printed(float(f["angle"]))
        facts[f"{criterion}_face"] = f.get("face")
        facts[f"{criterion}_element"] = f["label"].rsplit(".", 1)[-1]
        facts[f"{criterion}_mode"] = f["mode"]
        facts[f"{criterion}_place"] = f["place"]
        facts[f"{criterion}_tied"] = [int(p) for p in f["tied_plies"] if int(p) != int(f["ply"])]
        facts[f"{criterion}_touches_grip"] = bool(f["touches_grip"])
    method = summary.get("test_method")
    if method:  # the quantities of the test standard, as the standard computes them from a test (ADR-0072)
        u = method["units"]
        red = method["reduction"]
        facts.update(standard=method["designation"] or "", area_unit=u["area"], modulus_unit=u["modulus"],
                     tm_width=printed(method["width"]), tm_thickness=printed(method["thickness"]), tm_area=printed(method["area"]),
                     tm_force=printed(abs(method["force"])), tm_stress=printed(abs(method["stress"])), tm_area_name=red["area"],
                     tm_modulus_name=red["modulus"], tm_isotropic=bool(method.get("laminate_theory", {}).get("isotropic", False)))
        if method.get("hole"):
            h = method["hole"]
            facts.update(tm_net_area=printed(h["net_area"]), tm_net_stress=printed(abs(h["net_stress"])), tm_width_to_hole=printed(h["width_to_hole"]),
                         tm_hole_to_thickness=printed(h["hole_to_thickness"]))
        lt = method.get("laminate_theory") or {}
        if method.get("strain"):
            s = method["strain"]
            facts.update(tm_device=s["device"], tm_gauge_length=printed(s["modelled_length"]), tm_strain=printed(abs(s["value"]) * 1e6),
                         tm_chord_from=printed(s["chord"]["from"] * 1e6), tm_chord_to=printed(s["chord"]["to"] * 1e6),
                         tm_modulus=printed(s["chord"]["modulus"]), tm_modulus_theory=printed(lt.get("modulus", 0.0)))
            if s.get("poisson") is not None:
                facts.update(tm_poisson=printed(s["poisson"]), tm_poisson_theory=printed(lt.get("poisson", 0.0)))
        earliest = method.get("earliest")
        if earliest:
            first = method["fpf"][earliest]
            facts.update(tm_fpf_criterion=earliest, tm_fpf_basis=method["fpf_basis"], tm_fpf_stress=printed(abs(first["stress"])))
            if "net_stress" in first:
                facts["tm_fpf_net_stress"] = printed(abs(first["net_stress"]))
    return facts


def _face(face: str | None) -> str:
    return f" on its {face} face" if face else ""


def result_sentences(facts: dict[str, Any]) -> list[str]:
    """What the result says, one sentence at a time, every number quoted from the facts."""
    out = [f"{facts['designation']}, {facts['test']}, under a {facts['control']} of {number(facts['applied'])} {facts['applied_unit']} "
           f"{facts['applied_direction']}: {facts['reaction_set']} carries {number(facts['reaction'])} {facts['force_unit']}, {facts['sense']}.",
           f"The largest displacement is {number(facts['max_displacement'])} {facts['length_unit']} at node {facts['max_displacement_node']} "
           f"({number(facts['max_displacement_x'])}, {number(facts['max_displacement_y'])} {facts['length_unit']}), mostly "
           f"{AXIS_WORDS.get(facts['max_displacement_axis'], facts['max_displacement_axis'])}.",
           ply_stress_sentence(facts)]
    if facts["isotropic"]:
        out.append("The material is isotropic: its yield and failure are not modelled yet, so no failure is reported.")
        return out + method_sentences(facts)
    if not facts["criteria"]:
        out.append("No failure criterion was asked for, so first-ply failure is not reported.")
        return out + method_sentences(facts)
    ordered = sorted(facts["criteria"], key=lambda c: facts[f"{c}_factor"])
    for criterion in ordered:
        name = CRITERION.get(criterion, criterion)
        factor, ply, angle = facts[f"{criterion}_factor"], facts[f"{criterion}_ply"], facts[f"{criterion}_angle"]
        mode = MODE_WORDS.get(facts[f"{criterion}_mode"], facts[f"{criterion}_mode"])
        tied = facts[f"{criterion}_tied"]
        where = facts[f"{criterion}_place"]
        who = (f"ply {ply} ({number(angle)} degrees){_face(facts[f'{criterion}_face'])}"
               + (f", tied with {'ply' if len(tied) == 1 else 'plies'} {', '.join(str(p) for p in tied)}" if tied else ""))
        if factor >= 1.0:
            text = (f"The laminate does not exceed the {name} criterion at the applied loading: the first ply to fail would be {who}, at element "
                    f"{facts[f'{criterion}_element']}, {where}, by {mode}, at {number(factor)} times the applied loading "
                    f"(failure index {number(facts[f'{criterion}_index'])}).")
        else:
            text = (f"The laminate exceeds the {name} criterion at the applied loading: {who} fails first, at element {facts[f'{criterion}_element']}, "
                    f"{where}, by {mode}, at {number(factor)} of the applied loading (failure index {number(facts[f'{criterion}_index'])}); the stresses "
                    "shown are those of a linear model past that point.")
        if facts[f"{criterion}_touches_grip"]:
            text += " That element touches a gripped tab, where the stress is not expected to settle as the mesh is refined: read it as first damage at the grip."
        out.append(text)
    if len(ordered) > 1:
        out.append(f"The earliest of the criteria is {CRITERION.get(ordered[0], ordered[0])}.")
    return out + method_sentences(facts)


def ply_stress_sentence(facts: dict[str, Any]) -> str:
    """The largest stresses: each ply's in its own fibre axes, or an isotropic material's along and across the coupon (ADR-0075)."""
    if facts["isotropic"]:
        return ("The largest stresses, along and across the coupon, are "
                + ", ".join(f"{ISOTROPIC_WORDS[name]} = {number(facts[f'max_{name}'])} {facts['stress_unit']}{_face(facts[f'max_{name}_face'])} "
                            f"at element {facts[f'max_{name}_element']}" for name in ("S11", "S22", "S12"))
                + "; these are element centroids, not the nodal values a viewer such as PrePoMax shows.")
    return ("The largest ply stresses, each in its own ply's fibre axes, are "
            + ", ".join(f"{STRESS_WORDS[name]} = {number(facts[f'max_{name}'])} {facts['stress_unit']} in ply {facts[f'max_{name}_ply']} "
                        f"({number(facts[f'max_{name}_angle'])} degrees){_face(facts[f'max_{name}_face'])} at element {facts[f'max_{name}_element']}"
                        for name in ("S11", "S22", "S12"))
            + "; these are element centroids in the ply's axes, not the global-axis values a viewer such as PrePoMax shows.")


def method_sentences(facts: dict[str, Any]) -> list[str]:
    """The test standard's quantities, as the standard computes them from a test, every number from the facts (ADR-0072); none without them."""
    if "tm_area" not in facts:
        return []
    L, S = facts["length_unit"], facts["stress_unit"]
    out = [f"{'As ' + facts['standard'] + ' reduces a test' if facts['standard'] else 'As a test is reduced'}: the {facts['tm_area_name']} is {number(facts['tm_area'])} {facts['area_unit']} ({number(facts['tm_width'])} by "
           f"{number(facts['tm_thickness'])} {L}), so the force along the coupon, {number(facts['tm_force'])} {facts['force_unit']}, is a stress of "
           f"{number(facts['tm_stress'])} {S}."]
    if "tm_net_area" in facts:
        out.append(f"Through the hole the net area is {number(facts['tm_net_area'])} {facts['area_unit']}, a net stress of {number(facts['tm_net_stress'])} {S}; "
                   f"the width is {number(facts['tm_width_to_hole'])} hole diameters and the hole {number(facts['tm_hole_to_thickness'])} thicknesses.")
    if "tm_strain" in facts:
        theory = "the material's own value" if facts["tm_isotropic"] else "laminate theory"
        text = (f"The {facts['tm_device']} over {number(facts['tm_gauge_length'])} {L} reads {number(facts['tm_strain'])} microstrain, so the {facts['tm_modulus_name']} "
                f"between {number(facts['tm_chord_from'])} and {number(facts['tm_chord_to'])} microstrain is {number(facts['tm_modulus'])} {facts['modulus_unit']} "
                f"({theory} gives {number(facts['tm_modulus_theory'])} {facts['modulus_unit']})")
        if "tm_poisson" in facts:
            text += f", and Poisson's ratio is {number(facts['tm_poisson'])} ({theory}: {number(facts['tm_poisson_theory'])})"
        out.append(text + "; a linear model gives the same slope over any range.")
    if "tm_fpf_stress" in facts:
        net = f" ({number(facts['tm_fpf_net_stress'])} {S} on the net area)" if "tm_fpf_net_stress" in facts else ""
        out.append(f"By {CRITERION.get(facts['tm_fpf_criterion'], facts['tm_fpf_criterion'])} in {facts['tm_fpf_basis']}, the first ply fails at a "
                   f"{'gross stress' if facts['tm_area_name'] == 'gross area' else 'stress on the ' + facts['tm_area_name']} "
                   f"of {number(facts['tm_fpf_stress'])} {S}{net}: a first-ply-failure stress, not the ultimate strength the standard takes at the "
                   "maximum force of a test, which a linear model cannot give.")
    return out


def setup_sentences(checklist: dict[str, Any]) -> list[str]:
    """What the setup check says, one sentence per item that has been judged."""
    items = checklist["items"]
    blocked = [item for item in items if item["state"] in ("fail", "missing")]
    warned = [item for item in items if item["state"] == "warn"]
    if blocked:
        head = (f"The setup is blocked: {len(blocked)} item{'s' if len(blocked) != 1 else ''} need{'s' if len(blocked) == 1 else ''} input "
                f"({', '.join(item['label'].lower() for item in blocked)}).")
    else:
        head = "The setup is ready to solve" + (f", with {len(warned)} warning{'s' if len(warned) != 1 else ''}." if warned else ".")
    out = [head]
    for item in items:
        if item["state"] == "pending":
            continue
        if item["state"] in ("fail", "missing"):
            out.append(f"{item['label']} needs attention: {item['message']}" + (f" (rows: {', '.join(item['rows'])})." if item["rows"] else "."))
        elif item["state"] == "warn":
            out.append(f"Warning, {item['label'].lower()}: {item['message']}.")
        else:
            out.append(f"{item['label']}: {item['message']}.")
    return out


def numbers_in(text: str) -> list[str]:
    """Every number token in a text, as written: what a guard checks against the facts."""
    return NUMBER.findall(text)


def explanation(summary: dict[str, Any], coupon: dict[str, Any], units: str, labels: dict[str, str], checklist: dict[str, Any] | None = None) -> dict[str, Any]:
    """The template's explanation of a result: the facts, the sentences, and the setup's sentences when the checklist is given."""
    facts = fact_sheet(summary, coupon, units, labels)
    return {"writer": "template", "facts": facts, "sentences": result_sentences(facts),
            "setup_sentences": setup_sentences(checklist) if checklist is not None else []}
