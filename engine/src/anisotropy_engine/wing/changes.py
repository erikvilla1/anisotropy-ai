"""A change of plies to a wing, made on a copy of its wing file and worked before and after (ADR-0128).

"Add 2 0° plies to the spar caps from the root to 40 % span" is one `PlyChange`: plies of one angle added to (or taken from) one
part over a stretch of the half span. `change_wing` writes the wing file the change gives: the part's half stack where the change
covers the whole span, and zones (ADR-0125) where it covers a stretch, split and joined so that every stretch holds its own stack and
no zone repeats the stack outside the zones. Nothing is analysed there, and the wing given is never changed.

`preview_change` works the wing as it is and as changed with the hand calculation and returns both, with the design rules of the part
changed: what the engineer reads before applying it. Applying is the engineer's: no function here keeps a change.

A laminate here is symmetric, written by its outer half (the other half mirrors it; a sandwich's half is one face). So plies are added
and taken in pairs, one on each side of the middle, or one on each face of a sandwich; an odd count is refused with the reason.
"""

from __future__ import annotations

import copy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PARTS: dict[str, str] = {"skin": "the skin", "spar": "the spar webs", "spar_caps": "the spar caps"}
PLACEMENTS = ("beside", "middle")  # beside the plies of the same angle nearest the outside, or at the middle of the laminate
EDGE = 1e-9  # two fractions of the span closer than this are one place
ANGLE = 1e-6


class PlyChange(BaseModel):
    """Plies of one angle added to or taken from one part, over a stretch of the half span (fractions from the root). `count` is the
    plies of the whole laminate, both halves: 2 is one ply each side of the middle, or one on each face of a sandwich."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    action: Literal["add_plies", "remove_plies"]
    part: Literal["skin", "spar", "spar_caps"]
    angle: float = Field(ge=-90, le=180)
    count: int = Field(ge=1, le=40, strict=True)
    start: float = Field(default=0.0, ge=0, lt=1)
    end: float = Field(default=1.0, gt=0, le=1)
    placement: Literal["beside", "middle"] = "beside"

    @model_validator(mode="after")
    def _checked(self) -> "PlyChange":
        if not self.start < self.end:
            raise ValueError(f"A change runs from its start to its end along the half span, start before end; got {self.start:g} to {self.end:g}")
        if self.count % 2:
            raise ValueError(f"{self.count} plies cannot keep the laminate symmetric: plies go in pairs, one on each side of its middle "
                             "(one on each face of a sandwich). Ask for an even number")
        return self


def _same(a: float, b: float) -> bool:
    """Two ply angles are one direction when they differ by a whole number of half turns: 135° is −45°, −90° is 90°."""
    return abs((a - b + 90.0) % 180.0 - 90.0) < ANGLE


def _angle_words(angle: float) -> str:
    folded = (angle + 90.0) % 180.0 - 90.0
    folded = 90.0 if abs(folded + 90.0) < ANGLE else folded
    return f"{'+' if folded > 0 and folded != 90 else ''}{folded:g}°".replace("-", "−")


def stack_words(half: tuple[float, ...] | list[float]) -> str:
    """A half stack as the page writes a symmetric laminate: [0/0/45/-45/0]s."""
    return "[" + "/".join(f"{a:g}" for a in half) + "]s"


def _span_words(start: float, end: float) -> str:
    def at(f: float) -> str:
        return "the root" if f < EDGE else "the tip" if f > 1 - EDGE else f"{100 * f:g} %"
    if start < EDGE and end > 1 - EDGE:
        return "along the whole span"
    return f"from {at(start)} to {at(end)} of the half span"


def _changed(half: tuple[float, ...], change: PlyChange) -> tuple[float, ...]:
    """The half stack with the change made: added beside the first run of plies of its angle (at the middle when there is none, or when
    asked), or taken from the plies of its angle nearest the middle, so the outside plies run on over the drop."""
    per_half = change.count // 2
    plies = list(half)
    if change.action == "add_plies":
        runs = [k for k, a in enumerate(plies) if _same(a, change.angle)]
        if change.placement == "middle" or not runs:
            at = len(plies)
        else:
            at = runs[0]
            while at < len(plies) and _same(plies[at], change.angle):
                at += 1  # after the first run of that angle
        return tuple(plies[:at] + [float(change.angle)] * per_half + plies[at:])
    held = [k for k, a in enumerate(plies) if _same(a, change.angle)]
    if len(held) < per_half:
        raise ValueError(f"{stack_words(half)} has {2 * len(held)} plies at {_angle_words(change.angle)}: {change.count} cannot be taken out.")
    for k in reversed(held[-per_half:]):
        del plies[k]
    if not plies:
        raise ValueError(f"Taking {change.count} plies out of {stack_words(half)} would leave no plies.")
    return tuple(plies)


def _stretches(table: dict) -> list[tuple[float, float, tuple[float, ...]]]:
    """A part's stacks from root to tip, as the wing file holds them: its zones, and its half stack between and around them."""
    base = tuple(float(a) for a in table["half_stack"])
    zones = sorted(table.get("zones", []), key=lambda z: z["start"])
    found, here = [], 0.0
    for zone in zones:
        if zone["start"] > here + EDGE:
            found.append((here, float(zone["start"]), base))
        found.append((float(zone["start"]), float(zone["end"]), tuple(float(a) for a in zone["half_stack"])))
        here = float(zone["end"])
    if here < 1 - EDGE:
        found.append((here, 1.0, base))
    return found


def change_wing(data: dict, change: PlyChange) -> dict:
    """A copy of the wing file with the change made, the part's zones rewritten so that each stretch holds its stack once."""
    if change.part not in data:
        raise ValueError("The wing has no spar caps: add them on the Layup step first." if change.part == "spar_caps"
                         else f"The wing file has no [{change.part}].")
    changed = copy.deepcopy(data)
    table = changed[change.part]
    base = tuple(float(a) for a in table["half_stack"])
    whole = change.start < EDGE and change.end > 1 - EDGE
    cuts = sorted({0.0, 1.0, change.start, change.end, *(e for s, t, _ in _stretches(table) for e in (s, t))})
    pieces = []
    for start, end in zip(cuts, cuts[1:]):
        if end - start < EDGE:
            continue
        stack = next(h for s, t, h in _stretches(table) if s - EDGE <= start and end <= t + EDGE)
        inside = change.start - EDGE <= start and end <= change.end + EDGE
        pieces.append((start, end, _changed(stack, change) if inside else stack))
    new_base = _changed(base, change) if whole else base
    if len({stack for _, _, stack in pieces}) == 1:
        new_base = pieces[0][2]  # one stack from root to tip: the part's own, no zone
    zones: list[dict] = []
    for start, end, stack in pieces:
        if stack == new_base:
            continue
        if zones and abs(zones[-1]["end"] - start) < EDGE and tuple(zones[-1]["half_stack"]) == stack:
            zones[-1]["end"] = end  # the same stack on both sides of a cut: one zone
        else:
            zones.append({"start": round(start, 12), "end": round(end, 12), "half_stack": list(stack)})
    table["half_stack"] = list(new_base)
    if zones:
        table["zones"] = zones
    else:
        table.pop("zones", None)
    return changed


def change_words(data: dict, change: PlyChange) -> str:
    """The change in one plain sentence, with the stacks it gives there: what the engineer ticks."""
    count = {2: "Two", 4: "Four", 6: "Six", 8: "Eight", 10: "Ten", 12: "Twelve"}.get(change.count, str(change.count))
    angle = _angle_words(change.angle)
    inside = [h for s, e, h in _stretches(data[change.part]) if e > change.start + EDGE and s < change.end - EDGE]
    sandwich = bool(data[change.part].get("core_thickness") or data[change.part].get("core"))
    if change.action == "remove_plies":
        verb, where = "taken from", "the ones nearest the middle"
    else:
        verb = "added to"
        beside = change.placement == "beside" and all(any(_same(a, change.angle) for a in h) for h in inside)
        where = f"beside the {angle} plies" if beside else "on the inside of each face" if sandwich else "one each side of the middle"
    after = change_wing(data, change)[change.part]
    stacks = sorted({stack_words(h) for s, e, h in _stretches(after) if e > change.start + EDGE and s < change.end - EDGE})
    return f"{count} {angle} plies {verb} {PARTS[change.part]} {_span_words(change.start, change.end)}, {where}: {' and '.join(stacks)} there."


def _summary(report: dict) -> dict:
    """What a change is judged by: the lowest margin and where, each check's lowest margin, the mass, the largest tip deflection and the
    first bending frequency, in the report's units, and the basis of the strengths the margins use (ADR-0126)."""
    lowest: dict[str, float] = {}
    for case in report["cases"]:
        for name, check in case["checks"].items():
            if check is not None and check.get("margin_ultimate") is not None:
                lowest[name] = min(lowest.get(name, float("inf")), check["margin_ultimate"])
    design = report["design"]
    return {"passes": report["passes"], "governing": report["governing"], "lowest": lowest, "mass": design["mass"],
            "tip_deflection": max(abs(case["tip_deflection"]) for case in report["cases"]),
            "first_bending_frequency": design["first_bending_frequency"],
            "strength_basis": (report.get("material") or {}).get("strength_basis")}


def preview_change(data: dict, change: PlyChange) -> dict:
    """The wing as it is and as changed, worked by the hand calculation: the changed wing file, the sentence, both summaries and the design
    rules of the part changed. Nothing is kept: the engineer applies the change, or not."""
    from .analysis import analyze_wing
    from .wing_file import wing_from_dict, wing_report

    changed = change_wing(data, change)
    reports = []
    for wing_data in (data, changed):
        wing, envelope = wing_from_dict(wing_data)
        reports.append(wing_report(analyze_wing(wing, envelope), wing_data.get("units", "SI"),
                                   wing_data.get("envelope", {}).get("speed_unit", "m/s")))
    member = "cap" if change.part == "spar_caps" else change.part
    return {"change": change.model_dump(), "words": change_words(data, change), "wing": changed,
            "before": _summary(reports[0]), "after": _summary(reports[1]), "units": reports[1]["units"],
            "rules": [rule for rule in reports[1]["rules"] if rule["part"] == member]}
