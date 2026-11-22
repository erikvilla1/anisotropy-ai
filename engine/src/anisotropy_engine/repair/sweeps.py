"""One quantity of a stepped patch repair varied over a range, the repair worked by hand at every value (ADR-0136).

`sweep_repair` takes a repair file and a `RepairSweep`: the quantity (the step length, the bondline's thickness, the cover
plies' overlap, the patch's overlap, or the number of steps the same plies are grouped in), optionally its range, and
optionally a load. Every value is a whole repair file, written by `change_repair`, read by the engine's own rules and worked
by the hand calculation (ADR-0130, ADR-0131): a row holds the value, the repair's width, the largest bondline shear and where,
and the load at the adhesive's elastic limit, or the reader's refusal of that value.

With a load named, each row says whether the adhesive is still elastic at it (its limit load is at or above the load), and the
pick is the smallest repair that is: the narrowest, then the nearest to the repair as it stands. That is all the pick is. The
limit load is where the adhesive starts to yield, not the repair's strength (ADR-0130), and the hand calculation holds no peel
stress, so a pick is the model's answer and not a design. The answer also says from which value the limit load stays within
1 % of its value at the end of the range, that is, where the quantity stops mattering.

The values are round ones: the multiples of a round increment inside the range (at most 25 of them), with the repair as it
stands and a stated range's two ends among them. Left unsaid, the range runs from a fifth of the value as it stands to twice
it.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .changes import QUANTITIES, RepairChange, _steps, _system, change_repair, in_file_units, shown, summary, tidy
from .description import RepairError

INCREMENTS = 24  # a range is cut in at most this many round increments
FLAT_WITHIN = 0.01  # the limit load "no longer changes" where it stays within this fraction of its value at the end of the range
FLAT_SHARE = 0.25  # and only when that stretch is at least this share of the range worked
MESH_MARK = 0.02  # a solved slice's largest stresses may move this fraction with a finer mesh (ADR-0132's own mark); a pick this close to the load is not called
SWEPT_VALUES = ("step_length", "bondline", "cover_overlap", "patch_overlap")
ROUND = (1.0, 2.0, 2.5, 5.0)
FIRST = {"adhesive": "the adhesive reaches its elastic limit in shear", "peel": "the bondline's peel stress reaches the peel strength",
         "ply": "a ply reaches a strength"}  # what comes first in a solved slice, in the words of anisotropy_fea.repair_model.FIRST_WORDS
# What stands beside every sweep that gives a limit load (ADR-0130, ADR-0136): it is where the adhesive starts to yield, by a model with no peel stress
NOT_A_STRENGTH = "Not the repair's strength: the adhesive yields before it fails, and the hand calculation has no peel stress."
NOT_A_STEP_RULE = "A short step that keeps the adhesive elastic in this model is not a rule for choosing a step length."
PICKED = {"step_length": "a step length", "bondline": "a bondline", "cover_overlap": "a cover overlap", "patch_overlap": "a patch overlap"}


class RepairSweep(BaseModel):
    """One quantity varied. `start` and `end` are in `unit` (as the engineer wrote it) or the file's unit when none is given;
    both or neither. `load`, in `load_unit` or the file's, is the load the adhesive is to stay elastic at."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    quantity: Literal["step_length", "bondline", "cover_overlap", "patch_overlap", "steps"]
    start: float | None = Field(default=None, gt=0)
    end: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    load: float | None = Field(default=None, gt=0)
    load_unit: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _checked(self) -> "RepairSweep":
        if (self.start is None) != (self.end is None):
            raise ValueError("A range has a start and an end: give both, or neither")
        if self.start is not None and not self.start < self.end:
            raise ValueError(f"A range runs from its start up to its end; got {self.start:g} to {self.end:g}")
        if self.quantity == "steps" and (self.start is not None or self.unit is not None):
            raise ValueError("The number of steps is swept over every way the same plies can be grouped: it takes no range")
        if self.unit is not None and self.start is None:
            raise ValueError("A unit belongs to a range")
        if self.load_unit is not None and self.load is None:
            raise ValueError("A load's unit belongs to a load")
        return self


def round_increment(span: float, most: int = INCREMENTS) -> float:
    """The smallest round increment (1, 2, 2.5 or 5 times a power of ten) that cuts `span` in at most `most` parts."""
    power = 10.0 ** math.floor(math.log10(span / most))
    for scale in (power, 10 * power):
        for multiple in ROUND:
            if span / (multiple * scale) <= most * (1 + 1e-9):
                return multiple * scale
    return 100 * power


def round_values(start: float, end: float) -> list[float]:
    """The multiples of a round increment from `start` to `end`, both included when they are multiples."""
    increment = round_increment(end - start)
    first, last = math.ceil(start / increment - 1e-9), math.floor(end / increment + 1e-9)
    return [tidy(k * increment) for k in range(first, last + 1)]


def _merge(values: list[float]) -> list[float]:
    """Values in order, two that are one value kept once."""
    kept: list[float] = []
    for value in sorted(values):
        if not kept or not math.isclose(value, kept[-1], rel_tol=1e-9):
            kept.append(value)
    return kept


def _row(data: dict, change: RepairChange, value: float, current: bool) -> tuple[dict, dict | None]:
    """One value worked by hand: its row and the repair file it is, or the row of its refusal."""
    from .repair_file import repair_from_dict, repair_report

    try:
        changed = change_repair(data, change)
        repair, load = repair_from_dict(changed)
        found = summary(changed, repair_report(repair, changed["units"], load))
    except RepairError as error:
        return {"value": value, "current": current, "refused": str(error)}, None
    return {"value": value, "current": current, "refused": None, "repair_diameter": found["repair_diameter"], "steps": found["steps"],
            "plies_per_step": found["plies_per_step"], "peak_shear": found["peak_shear"], "elastic_limit_load": found["elastic_limit_load"]}, changed


def _flat_from(rows: list[dict]) -> dict | None:
    """From which value the limit load stays within FLAT_WITHIN of its value at the end of the range: the value, the limit
    load at the end, and whether that is every row worked. None when fewer than three rows have a limit load, or the stretch
    that near is under FLAT_SHARE of the range worked."""
    worked = [row for row in rows if row["refused"] is None and row.get("elastic_limit_load") is not None]
    if len(worked) < 3:
        return None
    end = worked[-1]["elastic_limit_load"]
    first = len(worked) - 1
    while first > 0 and abs(worked[first - 1]["elastic_limit_load"] - end) <= FLAT_WITHIN * abs(end):
        first -= 1
    if first == len(worked) - 1:
        return None
    if worked[-1]["value"] - worked[first]["value"] < FLAT_SHARE * (worked[-1]["value"] - worked[0]["value"]):
        return None  # near the end of a curve still rising, two close values are that near: not a flat stretch
    return {"value": worked[first]["value"], "elastic_limit_load": end, "every_row": first == 0}


def sweep_repair(data: dict, sweep: RepairSweep) -> dict:
    """The repair worked by hand at every value of one quantity: the rows, the pick when a load is named, where the limit
    load goes flat, and the answer in sentences with what it is not (`cautions`), all in the file's units. The repair given is never changed."""
    from .repair_file import repair_from_dict, repair_report

    system = _system(data)
    repair, load = repair_from_dict(data)
    base = repair_report(repair, data["units"], load)
    if load is None or load == 0:
        raise RepairError("A sweep needs a load per unit width that is not zero, stated on the Panel and load step: the bondline is worked under it")
    target = None if sweep.load is None else in_file_units(data, sweep.load, sweep.load_unit, "N")
    if target is not None and repair.adhesive.shear_strength_pa is None:
        raise RepairError("A sweep to a load needs the adhesive's shear strength, stated on the Adhesive step: without it no elastic limit load is worked")
    force, length = system["N"][1], system["length"][1]
    rows, files = [], []
    if sweep.quantity == "steps":
        steps, per = _steps(data)
        total = steps * per
        unit, name = "", "the number of steps"
        for plies in sorted((n for n in range(1, total + 1) if total % n == 0), reverse=True):  # fewest steps first
            row, changed = _row(data, RepairChange(action="regroup", count=plies), total // plies, plies == per)
            rows.append(row)
            files.append(changed)
    else:
        table, key, kind, name = QUANTITIES[sweep.quantity]
        unit = system[kind][1]
        stated = data.get(table)
        current = stated.get(key) if isinstance(stated, dict) else None
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise RepairError(f"The repair states no value for {name}, so it cannot be swept"
                              + (": a flush patch fills its cut." if sweep.quantity == "patch_overlap" else ": it has no cover plies." if sweep.quantity == "cover_overlap" else "."))
        if sweep.start is None:
            start, end = current / 5, 2 * current
        else:
            start, end = in_file_units(data, sweep.start, sweep.unit, kind), in_file_units(data, sweep.end, sweep.unit, kind)
        values = round_values(start, end)
        if sweep.start is not None:
            values += [start, end]
        if start <= current <= end:
            values.append(float(current))
        values = _merge(values)
        for value in values:
            row, changed = _row(data, RepairChange(action="set", quantity=sweep.quantity, value=value), value, math.isclose(value, current, rel_tol=1e-9))
            rows.append(row)
            files.append(changed)
    worked = [row for row in rows if row["refused"] is None]
    if not worked:
        raise RepairError(f"No value of the range could be worked. The first was refused: {rows[0]['refused']}")
    for row in rows:
        row["elastic"] = None if target is None or row["refused"] is not None or row.get("elastic_limit_load") is None else row["elastic_limit_load"] >= target
    pick = None
    if target is not None:
        now = next((row["value"] for row in rows if row["current"]), None)
        holding = [i for i, row in enumerate(rows) if row["elastic"]]
        if holding:
            pick = min(holding, key=lambda i: (rows[i]["repair_diameter"], abs(rows[i]["value"] - now) if now is not None else 0.0, rows[i]["value"]))
    flat = _flat_from(rows) if sweep.quantity != "steps" else None
    limits = [row for row in worked if row.get("elastic_limit_load") is not None]
    most = max(limits, key=lambda row: row["elastic_limit_load"]) if limits else None

    value_words = (lambda row: f"{row['steps']} {'step' if row['steps'] == 1 else 'steps'} of {row['plies_per_step']} {'ply' if row['plies_per_step'] == 1 else 'plies'}") \
        if sweep.quantity == "steps" else (lambda row: f"{PICKED[sweep.quantity]} of {shown(row['value'])} {unit}")
    refused = len(rows) - len(worked)
    if sweep.quantity == "steps":
        total = _steps(data)[0] * _steps(data)[1]
        words = [f"The same {total} plies grouped in {', '.join(str(row['value']) for row in rows[:-1])}{' and ' if len(rows) > 1 else ''}{rows[-1]['value']} "
                 f"{'step' if len(rows) == 1 and rows[-1]['value'] == 1 else 'steps'}, each worked by hand under {shown(base['lap']['load'])} {force}."]
    else:
        words = [f"{name[0].upper()}{name[1:]} from {shown(rows[0]['value'])} {unit} to {shown(rows[-1]['value'])} {unit}, {len(rows)} values, "
                 f"each worked by hand under {shown(base['lap']['load'])} {force}."]
    if refused:
        first = next(row for row in rows if row["refused"] is not None)
        words.append(f"{refused} of them could not be worked. At {shown(first['value'])}{' ' + unit if unit else ' steps'}: {first['refused']}.")
    answer: list[str] = []  # the sweep's answer in a sentence or two: what the page says first, the rest of `words` under it
    if target is not None:
        if pick is not None:
            row = rows[pick]
            same_size = all(math.isclose(other["repair_diameter"], row["repair_diameter"], rel_tol=1e-9) for other in worked)
            limit = f"Its adhesive reaches its elastic limit at {shown(row['elastic_limit_load'])} {force}."
            if same_size:  # the quantity does not change the repair's size: the pick is the nearest to the repair as it stands
                answer.append(f"The nearest of these to the repair as it stands whose adhesive is still elastic at {shown(target)} {force}: {value_words(row)}. {limit}")
            else:
                answer.append(f"The smallest of these whose adhesive is still elastic at {shown(target)} {force}: {value_words(row)}, the repair "
                              f"{shown(row['repair_diameter'])} {length} across. {limit}")
            if sweep.quantity != "steps" and row is worked[0] and not same_size:
                answer.append("It is the first value of the range: a smaller one was not tried.")
        elif most is not None:
            answer.append(f"None of these keeps the adhesive elastic at {shown(target)} {force}. The most is {shown(most['elastic_limit_load'])} {force}, with {value_words(most)}.")
        words.extend(answer)
    if flat is not None:
        words.append(f"From {shown(flat['value'])} {unit} up the elastic limit load stays within 1 % of {shown(flat['elastic_limit_load'])} {force}: "
                     f"{'over this whole range' if flat['every_row'] else 'past it'}, {name} no longer changes it.")
        if target is None:  # with no load named, where the curve goes flat is the sweep's answer
            answer.append(words[-1])
    cautions = [NOT_A_STRENGTH] if any(row.get("elastic_limit_load") is not None for row in worked) else []
    if sweep.quantity == "step_length" and (pick is not None or flat is not None):
        cautions.append(NOT_A_STEP_RULE)
    return {"sweep": sweep.model_dump(), "quantity": {"name": sweep.quantity, "words": name, "unit": unit}, "units": base["units"],
            "load": base["lap"]["load"], "target": target, "rows": rows, "pick": pick, "picked": None if pick is None else files[pick],
            "flat_from": flat, "most": None if most is None else {"value": most["value"], "elastic_limit_load": most["elastic_limit_load"]}, "words": words,
            "answer": answer, "cautions": cautions}


def pick_check(target: float, solved: dict) -> dict:
    """What a solved slice of a sweep's pick says of it (ADR-0132, ADR-0136). `solved` is the slice's report in the file's units,
    as `anisotropy_fea.repair_model` writes it; `target` is the load named, in the same units. The slice holds what the hand
    calculation does not, the peel stress and every ply's stresses, so what reaches its limit first there may not be the
    adhesive's shear: the pick is held when that first limit is at or above the load named. No number is worked here beyond
    that comparison. A first limit within `MESH_MARK` of the load named is neither held nor not: a finer mesh may move the slice's
    largest stresses by that much (ADR-0132), so the comparison would be the mesh's."""
    force, stress = solved["units"]["force"], solved["units"]["stress"]
    bond, first = solved["bond"], solved.get("first")
    close = first is not None and abs(first["load"] - target) <= MESH_MARK * target
    holds = None if first is None or close else first["load"] >= target
    words = [f"The pick solved as a slice under {shown(solved['load'])} {force}: largest bondline shear {shown(abs(bond['peak_shear']['value']))} {stress}, "
             f"largest peel stress {shown(bond['peak_peel']['value'])} {stress}."]
    if first is None:
        words.append("The repair states no strength the slice could be held to, so the pick is not checked by it.")
    else:
        came = FIRST[first["what"]]
        if first["what"] == "ply" and solved.get("first_ply"):
            came += f" ({solved['first_ply']['name']})"
        words.append(f"As the load grows, {came} first, at {shown(first['load'])} {force}.")
        words.append(f"That is within {MESH_MARK * 100:g} % of the {shown(target)} {force} named, as far as a finer mesh may move a slice's number: "
                     "too close to say whether the slice holds the pick." if close else
                     f"That is at or above the {shown(target)} {force} named: the slice holds the pick." if holds else
                     f"That is below the {shown(target)} {force} named: the slice does not hold the pick.")
    return {"state": "solved", "holds": holds, "close": close, "first": first, "elastic_limit_load": solved.get("elastic_limit_load"), "peel_limit_load": solved.get("peel_limit_load"),
            "peak_shear": bond["peak_shear"], "peak_peel": bond["peak_peel"],
            "first_ply": None if not solved.get("first_ply") else {"name": solved["first_ply"]["name"], "load": solved["first_ply"]["load"]},
            "words": words}
