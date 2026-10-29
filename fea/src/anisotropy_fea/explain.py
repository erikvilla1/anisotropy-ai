"""The explanation the studio shows beside a result, written from the solve's summary by a template (ADR-0051).

Every number in a sentence is in the fact sheet first, and the sentence quotes it: the fact sheet is what a later assistant may
rephrase and what its guard checks against (ADR-0048, ADR-0052). The template never computes: it reads `fields.field_data`'s
summary and says, in the words the coupon document uses, what the coupon carries, where it moves most, which ply is stressed
most, and by each criterion whether the laminate exceeds it and which ply limits it, on which face when the coupon bends
(ADR-0053), where, and why.
"""

from __future__ import annotations

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
DIGITS = 4


def number(value: float) -> str:
    return f"{value:.{DIGITS}g}"


def fact_sheet(summary: dict[str, Any], coupon: dict[str, Any], units: str, labels: dict[str, str]) -> dict[str, Any]:
    """Every number and word the sentences may use, flat, by name."""
    facts: dict[str, Any] = {
        "designation": coupon.get("designation") or "the coupon", "test": coupon.get("test") or "", "layup": coupon.get("layup") or "",
        "units": units, "length_unit": labels["length"], "force_unit": labels["force"], "stress_unit": labels["stress"],
        "control": summary["applied"]["control"], "applied": abs(float(summary["applied"]["value"])), "applied_unit": summary["applied"]["unit"],
        "applied_direction": summary["applied"].get("direction", "along the coupon"),
        "reaction": abs(float(summary["reaction"]["value"])), "sense": summary["reaction"]["sense"], "reaction_set": summary["reaction"].get("set", "the top grip"),
        "max_displacement": float(summary["max_displacement"]["value"]), "max_displacement_node": summary["max_displacement"]["label"].rsplit(".", 1)[-1],
        "max_displacement_x": float(summary["max_displacement"]["xy"][0]), "max_displacement_y": float(summary["max_displacement"]["xy"][1]),
        "max_displacement_axis": summary["max_displacement"].get("axis", "y"),
    }
    for name, m in summary["max_ply"].items():
        facts[f"max_{name}"] = float(m["value"])
        facts[f"max_{name}_ply"] = int(m["ply"])
        facts[f"max_{name}_angle"] = float(m["angle"])
        facts[f"max_{name}_element"] = m["label"].rsplit(".", 1)[-1]
        facts[f"max_{name}_face"] = m.get("face")
    facts["criteria"] = list(summary["fpf"])
    facts["earliest"] = summary.get("earliest")
    for criterion, f in summary["fpf"].items():
        facts[f"{criterion}_factor"] = float(f["factor"])
        facts[f"{criterion}_index"] = float(f["index"])
        facts[f"{criterion}_ply"] = int(f["ply"])
        facts[f"{criterion}_angle"] = float(f["angle"])
        facts[f"{criterion}_face"] = f.get("face")
        facts[f"{criterion}_element"] = f["label"].rsplit(".", 1)[-1]
        facts[f"{criterion}_mode"] = f["mode"]
        facts[f"{criterion}_place"] = f["place"]
        facts[f"{criterion}_tied"] = [int(p) for p in f["tied_plies"] if int(p) != int(f["ply"])]
        facts[f"{criterion}_touches_grip"] = bool(f["touches_grip"])
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
           "The largest ply stresses in material axes are "
           + ", ".join(f"{name} = {number(facts[f'max_{name}'])} {facts['stress_unit']} in ply {facts[f'max_{name}_ply']} "
                       f"({number(facts[f'max_{name}_angle'])} degrees){_face(facts[f'max_{name}_face'])} at element {facts[f'max_{name}_element']}"
                       for name in ("S11", "S22", "S12"))
           + f"; the largest ply von Mises stress is {number(facts['max_mises'])} {facts['stress_unit']} in ply {facts['max_mises_ply']} "
           f"({number(facts['max_mises_angle'])} degrees){_face(facts['max_mises_face'])} at element {facts['max_mises_element']}."]
    if not facts["criteria"]:
        out.append("No failure criterion was asked for, so first-ply failure is not reported.")
        return out
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
