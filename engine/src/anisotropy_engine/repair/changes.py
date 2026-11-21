"""One change to a stepped patch repair, made on a copy of its repair file and worked before and after (ADR-0136).

"Make each step 0.5 in" is one `RepairChange`: a quantity set to a value, in the unit the engineer wrote or the file's. "Add a
step" is another: steps added, removed or set to a number, or the same plies regrouped into more or fewer steps. `change_repair`
writes the repair file the change gives; the file given is never changed and nothing is analysed there. `preview_change` reads
both files by the engine's own rules, works both by hand (ADR-0130, ADR-0131) and returns both, with the change in one sentence:
what the engineer reads before applying it. Applying is the engineer's: no function here keeps a change.

A step is one group of plies. In a flush repair a new step cuts one group deeper into the laminate, and the patch takes the
angles of the plies removed unless the file lists the patch's own plies. A patch whose plies are listed (every patch bonded on
top, and a flush patch with its own layup) needs the angles of a new step's plies, and a change without them is refused: no
angle is guessed (ADR-0003). A new step of a patch bonded on top is its shortest, on top; of a flush patch with its own layup,
its deepest.
"""

from __future__ import annotations

import copy
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..units import UNIT_SYSTEMS, to_si
from .description import RepairError

# What a change may set: the table and key of the repair file, the kind of quantity (units.py) and its name in a sentence.
QUANTITIES: dict[str, tuple[str, str, str, str]] = {
    "step_length": ("steps", "length", "length", "the step length"),
    "bondline": ("adhesive", "thickness", "length", "the bondline's thickness"),
    "load": ("applied", "load", "N", "the load"),
    "damage": ("damage", "diameter", "length", "the damage's diameter"),
    "cover_overlap": ("cover", "overlap", "length", "the cover plies' overlap"),
    "patch_overlap": ("patch", "overlap", "length", "the patch's overlap past the hole's edge"),
}
Quantity = Literal["step_length", "bondline", "load", "damage", "cover_overlap", "patch_overlap"]
COUNT_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


class RepairChange(BaseModel):
    """One change. `set`: `quantity` to `value`, in `unit` (as the engineer wrote it) or the file's own when none is given.
    `add_steps`, `remove_steps`: `count` steps, with the `angles` of a new step's plies where the patch's plies are listed.
    `set_steps`: the number of steps is `count`. `regroup`: the same plies in steps of `count` plies each. `regroup_steps`: the
    same plies in `count` steps."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    action: Literal["set", "add_steps", "remove_steps", "set_steps", "regroup", "regroup_steps"]
    quantity: Quantity | None = None
    value: float | None = None
    unit: str | None = Field(default=None, max_length=20)
    count: int | None = Field(default=None, ge=1, le=40, strict=True)
    angles: tuple[float, ...] | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _checked(self) -> "RepairChange":
        if self.action == "set":
            if self.quantity is None or self.value is None:
                raise ValueError("A value is set by its quantity and its value")
            if self.count is not None or self.angles is not None:
                raise ValueError("A value that is set takes no count and no angles")
        else:
            if self.quantity is not None or self.value is not None or self.unit is not None:
                raise ValueError("A change of steps takes a count, and no quantity, value or unit")
            if self.count is None:
                raise ValueError("A change of steps needs a count")
            if self.angles is not None and self.action in ("remove_steps", "regroup", "regroup_steps"):
                raise ValueError("Only new steps take angles")
        for angle in self.angles or ():
            if not -90 <= angle <= 180:
                raise ValueError(f"{angle:g}° is not a ply angle: give one from -90° to 180°")
        return self


def shown(value: float) -> str:
    """A number as a sentence prints it, as the repair's page does (`shown` of lib/wing.ts): four significant figures, thousands
    apart by a comma, no exponent."""
    if value == 0 or not math.isfinite(value):
        return "0" if value == 0 else str(value)
    value = float(f"{value:.4g}")
    digits = max(0, 3 - math.floor(math.log10(abs(value))))
    text = f"{value:,.{digits}f}"
    return (text.rstrip("0").rstrip(".") if "." in text else text).replace("-", "−")


def tidy(value: float) -> float:
    """A converted value without the last bits of the conversion: 0.5 in is 12.7 mm, not 12.699999999999998."""
    return float(f"{value:.12g}")


def angle_words(angles) -> str:
    return "[" + "/".join(f"{angle:g}".replace("-", "−") for angle in angles) + "]"


def count_words(count: int) -> str:
    return COUNT_WORDS.get(count, str(count))


def _system(data: dict) -> dict:
    units = data.get("units") if isinstance(data, dict) else None
    if units not in UNIT_SYSTEMS:
        raise RepairError(f"units must be one of {', '.join(UNIT_SYSTEMS)}, got {units!r}")
    return UNIT_SYSTEMS[units]


def in_file_units(data: dict, value: float, unit: str | None, kind: str) -> float:
    """A value as the repair file states it: unchanged when it carries no unit, else converted from the unit it carries."""
    if unit is None:
        return value
    try:
        return tidy(to_si(value, unit, kind) / _system(data)[kind][0])
    except ValueError as error:
        words = str(error)
        if kind == "N":  # units.py names the kind by its key: say what it is
            words = words.replace("is not a N unit", "is not a unit of load per unit width").replace("for N;", "for a load per unit width;")
        raise RepairError(f"The unit as written: {words}") from error


def _steps(data: dict) -> tuple[int, int]:
    """The repair file's steps and plies in a step, as stated."""
    steps = data.get("steps")
    if not isinstance(steps, dict) or isinstance(steps.get("count"), bool) or not isinstance(steps.get("count"), int):
        raise RepairError("The repair needs [steps] with a whole number of steps")
    per = steps.get("plies", 1)
    if isinstance(per, bool) or not isinstance(per, int) or per < 1 or steps["count"] < 1:
        raise RepairError("The steps and the plies in a step are whole numbers, 1 or more")
    return steps["count"], per


def _listed(data: dict) -> list | None:
    """The patch's plies when the repair file lists them, else None (a flush patch that takes the angles of the plies removed)."""
    patch = data.get("patch")
    layup = patch.get("layup") if isinstance(patch, dict) else None
    return list(layup) if isinstance(layup, (list, tuple)) else None


def change_repair(data: dict, change: RepairChange) -> dict:
    """The repair file a change gives, as a new table. Whether the repair it states can be built is the reader's to say
    (`repair_from_dict`); what is refused here is a change that cannot be written."""
    system = _system(data)
    changed = copy.deepcopy(data)
    external = data.get("kind", "flush") == "external"
    if change.action == "set":
        table, key, kind, words = QUANTITIES[change.quantity]
        if change.quantity == "cover_overlap" and not isinstance(data.get("cover"), dict):
            raise RepairError("The repair has no cover plies" + (": a patch bonded on top has none." if external else ": add them on the Cover plies step first."))
        if change.quantity == "patch_overlap" and not external:
            raise RepairError("A patch's overlap belongs to a patch bonded on top: a flush patch fills its cut.")
        if not isinstance(changed.get(table), dict):
            if change.quantity != "load":
                raise RepairError(f"The repair has no [{table}] to set {words} in")
            changed[table] = {}
        value = in_file_units(data, change.value, change.unit, kind)
        if change.quantity != "load" and value <= 0:
            raise RepairError(f"{words[0].upper()}{words[1:]} must be more than zero, got {shown(value)} {system[kind][1]}")
        changed[table][key] = value
        return changed
    steps, per = _steps(data)
    listed = _listed(data)
    if change.action in ("regroup", "regroup_steps"):
        total = steps * per
        divide = ", ".join(str(n) for n in range(1, total + 1) if total % n == 0)
        if total % change.count:
            raise RepairError(f"{total} plies cannot be grouped in steps of {change.count}: steps of {divide} divide them" if change.action == "regroup" else
                              f"{total} plies cannot be cut in {change.count} equal steps: {divide} steps divide them")
        each = change.count if change.action == "regroup" else total // change.count
        changed["steps"]["count"] = total // each
        if each != 1 or "plies" in changed["steps"]:
            changed["steps"]["plies"] = each
        return changed
    target = change.count if change.action == "set_steps" else steps + change.count if change.action == "add_steps" else steps - change.count
    if target < 1:
        raise RepairError(f"The repair has {steps} {'step' if steps == 1 else 'steps'}: at least one must stay")
    added = target - steps
    if added > 0:
        needed = added * per
        if listed is None:
            if change.angles is not None:
                raise RepairError("This patch takes the angles of the plies its steps remove: a new step's plies are not stated")
        else:
            if change.angles is None or len(change.angles) != needed:
                raise RepairError(f"{'One new step needs' if added == 1 else f'{added} new steps need'} the {'angle of its ply' if needed == 1 else f'angles of {needed} plies'}: "
                                  f"the patch's plies are listed, {'from the laminate upward' if external else 'deepest first'}, and no angle is guessed")
            angles = list(change.angles)
            changed["patch"]["layup"] = listed + angles if external else angles + listed
    elif added < 0:
        if change.angles is not None:
            raise RepairError("Only new steps take angles")
        if listed is not None:
            gone = -added * per
            changed["patch"]["layup"] = listed[:len(listed) - gone] if external else listed[gone:]
    changed["steps"]["count"] = target
    return changed


def summary(data: dict, report: dict) -> dict:
    """What a change is judged by, in the report's units: the repair's steps and width, the largest bondline shear and
    where, and the load at the adhesive's elastic limit. The stress and the limit load are there when a load is stated."""
    lap, sizes = report["lap"], report["sizes"]
    answer = lap.get("answer")
    peak = None
    if answer:
        step = lap["steps"][answer["peak_shear"]["step"] - 1]
        peak = {"value": abs(answer["peak_shear"]["value"]), "name": step["name"], "end": answer["peak_shear"]["end"]}
    steps, per = _steps(data)
    return {"kind": report["kind"], "steps": steps, "plies_per_step": per, "plies_removed": sizes["plies_removed"], "plies_left": sizes["plies_left"],
            "patch_plies": len(report["patch_layup"]), "patch_diameter": sizes["patch_diameter"], "repair_diameter": sizes["repair_diameter"],
            "load": lap.get("load"), "peak_shear": peak, "elastic_limit_load": (answer or {}).get("elastic_limit_load")}


def change_words(data: dict, changed: dict, change: RepairChange, after: dict) -> str:
    """The change in one plain sentence, in the file's units: what the engineer ticks."""
    system = _system(data)
    if change.action == "set":
        table, key, kind, words = QUANTITIES[change.quantity]
        unit = system[kind][1]
        new = changed[table][key]
        old = data.get(table, {}).get(key) if isinstance(data.get(table), dict) else None
        written = f" ({shown(change.value)} {change.unit} as written)" if change.unit is not None and change.unit != unit else ""
        if isinstance(old, bool) or not isinstance(old, (int, float)):
            return f"{words[0].upper()}{words[1:]} is set to {shown(new)} {unit}{written}."
        return f"{words[0].upper()}{words[1:]} goes from {shown(old)} {unit} to {shown(new)} {unit}{written}."
    before_steps, before_per = _steps(data)
    steps, per = _steps(changed)
    external = data.get("kind", "flush") == "external"
    plies = lambda n: f"{count_words(n)} {'ply' if n == 1 else 'plies'}"  # noqa: E731
    stepped = lambda n: f"{count_words(n)} {'step' if n == 1 else 'steps'}"  # noqa: E731
    if change.action in ("regroup", "regroup_steps"):
        return (f"The same {plies(steps * per)} in {stepped(steps)} of {plies(per)} each, in place of {stepped(before_steps)} of {plies(before_per)}.")
    start = f"{stepped(steps)[0].upper()}{stepped(steps)[1:]} in place of {count_words(before_steps)}"
    if external:
        detail = f"the patch has {plies(after['patch_plies'])}"
        if steps > before_steps:
            detail += f", the new {'ply' if len(change.angles) == 1 else 'plies'} {angle_words(change.angles)} its shortest, on top"
        return f"{start}: {detail}."
    left = after["plies_left"]
    detail = f"the cut goes {plies(after['plies_removed'])} deep, " + (f"and {plies(left)} of the laminate's {count_words(left + after['plies_removed'])} "
                                                                     f"{'is' if left == 1 else 'are'} left under the patch" if left else "through every ply of the laminate")
    listed = _listed(changed)
    if steps > before_steps:
        detail += (f"; the new {'ply' if len(change.angles) == 1 else 'plies'} {angle_words(change.angles)} {'is' if len(change.angles) == 1 else 'are'} the patch's deepest"
                   if listed is not None and change.angles else "; the patch takes the angles of the plies removed")
    return f"{start}: {detail}."


def preview_change(data: dict, change: RepairChange) -> dict:
    """The repair as it is and as changed, each read by the engine's own rules and worked by hand: the changed repair file,
    the change in one sentence and both summaries. A change the repair cannot take is refused in the reader's words.
    Nothing is kept: the engineer applies the change, or not."""
    from .repair_file import repair_from_dict, repair_report

    changed = change_repair(data, change)
    reports = []
    for stated in (data, changed):
        repair, load = repair_from_dict(stated)
        reports.append(repair_report(repair, stated["units"], load))
    before, after = summary(data, reports[0]), summary(changed, reports[1])
    return {"change": change.model_dump(), "words": change_words(data, changed, change, after), "repair": changed,
            "before": before, "after": after, "units": reports[1]["units"]}
