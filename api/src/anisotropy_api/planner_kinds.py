"""The workspace's planner for a wing and a repair (ADR-0144, build step 5): the same one call to the model, the same checks before a plan
is kept, and the same one approval, on a wing's description (a kept `wing` project, ADR-0122) or a repair's (which the page holds,
ADR-0135, so a repair's plan names no project). Nothing here computes a result (ADR-0001) and nothing here calls the model itself:
every change is the engine's own (`PlyChange`, ADR-0128; `RepairChange` and `RepairSweep`, ADR-0136), previewed by the engine before a
plan is kept, every number in a step is one the sentence writes, and a unit, a percentage of the span or a count in words is turned into
the engine's form by a fixed table, never by the model.

- A wing's tools: `add_plies` and `remove_plies` (plies of one angle in one part over a stretch of the half span), `analyze` (the hand
  calculation, ADR-0115), `check` (the finite element check, a job within the day's analyses, ADR-0119) and `answer`. The page reports
  the check as its job ends, and the answers (`WING_REPORTED`).
- A repair's tools: the engine's changes (`set`, `add_steps`, `remove_steps`, `set_steps`, `regroup`, `regroup_steps`), `sweep`,
  `use_pick` (the sweep's own pick, which no step writes: the model gives it no value), `solve` (the slice, ADR-0132), `bond` (followed
  until it lets go, ADR-0140) and `answer`. The server carries every step but the answers (`REPAIR_REPORTED`).
- `wing_view`, `repair_view`: what the model is shown, never a title, a source, a name or a note (R-11). `wing_schema`,
  `repair_schema`: its answer in a fixed schema. `check_wing_plan`, `check_repair_plan`: the checks a plan passes before it is kept.
  `make_wing_plan`, `make_repair_plan`: one call and one more try (`planner.plan_with`).
- `changed_wing`: a wing plan's changes made by the engine, for its approval. `run_summary`: what a run record keeps of a run's answer.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from anisotropy_engine.repair import RepairChange, RepairSweep, bond_needs, preview_change as preview_repair_change, repair_from_dict, solve_needs, sweep_repair
from anisotropy_engine.repair.changes import QUANTITIES
from anisotropy_engine.units import UNIT_SYSTEMS
from anisotropy_engine.wing.changes import PARTS, PlyChange, change_wing, preview_change as preview_wing_change

from . import setup_tools
from .assistant import REPAIR_PLAN_SYSTEM, WING_PLAN_SYSTEM
from .planner import (MAX_STEPS, MAX_QUESTION, Checked, Planned, _nullable, _question_reason, _quote_reason, _unread, answer_line, plan_with,
                      stray_numbers)
from .proposals import _NUMBER, UNREAD_REASONS, _plain, _squash, numbers_written

# What a refusal of the engine's may raise while it previews a change, works a sweep or reads a description.
REFUSALS = (ValueError, TypeError, KeyError, ArithmeticError)

# A count may be written as a word: the page's own (lib/wing-chat.ts and lib/repair-chat.ts, COUNT_WORDS), one way each.
COUNT_WORDS = {"a": 1, "an": 1, "one": 1, "another": 1, "single": 1, "a pair of": 2, "a couple of": 2, "two": 2, "three": 3, "four": 4,
               "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def _step(n: int, role: str, tool: str, line: str, *, quote: str | None = None, regions: list[str] | None = None,
          change: dict[str, Any] | None = None, question: str | None = None) -> dict[str, Any]:
    return {"n": n, "role": role, "tool": tool, "line": line, "quote": quote, "regions": list(regions or []), "change": change,
            "question": question, "state": "planned", "note": None}


def _schema(tools: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    """The model's answer (structured outputs), as a coupon's: steps of a tool on offer, its arguments (every one, null where it takes
    none) and its quote; a question asked back; the words not read."""
    text = {"type": "string"}
    args = {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    step = {"type": "object", "properties": {"tool": {"type": "string", "enum": tools}, "args": args, "quote": text},
            "required": ["tool", "args", "quote"], "additionalProperties": False}
    unread = {"type": "object", "properties": {"quote": text, "reason": {"type": "string", "enum": list(UNREAD_REASONS)}},
              "required": ["quote", "reason"], "additionalProperties": False}
    return {"type": "object",
            "properties": {"steps": {"type": "array", "items": step}, "question": _nullable(text), "unread": {"type": "array", "items": unread}},
            "required": ["steps", "question", "unread"], "additionalProperties": False}


def _opened(raw: dict[str, Any], sentence: str) -> tuple[Checked, list | None]:
    """The words not read, and a question asked back, which stands alone with no step, or no step at all; the steps to check otherwise
    (None when the answer is settled here), as a coupon's plan is read."""
    out = Checked()
    steps = raw.get("steps")
    steps = steps if isinstance(steps, list) else []
    quoted = {_plain(s["quote"]) for s in steps if isinstance(s, dict) and isinstance(s.get("quote"), str) and s["quote"].strip()}
    out.unread = _unread(raw.get("unread"), sentence, quoted)
    question = raw.get("question")
    if isinstance(question, str) and question.strip():
        if len(question.strip()) > MAX_QUESTION:
            out.reasons.append(f"the question back is longer than {MAX_QUESTION} characters")
        elif stray_numbers(question, sentence):
            out.reasons.append(f"the question back writes {', '.join(stray_numbers(question, sentence))}, which the sentence does not")
        else:
            out.question = question.strip()
        return out, None
    if not steps:
        out.reasons.append("the plan has no step and asks no question")
        return out, None
    return out, steps


def _number(text: Any, sentence: str, what: str) -> tuple[Decimal | None, str | None]:
    """One number as a step copies it from the sentence: the number, or why it cannot be one (none, several, or one the sentence does not
    write). The sign may come from the words, as a coupon's force's may."""
    if text is None or not str(text).strip():
        return None, f"it names no {what}"
    found = numbers_written(str(text))
    if len(found) != 1:
        return None, f"its {what} {text!r} is not one number"
    stray = stray_numbers(str(text), sentence)
    if stray:
        return None, f"{', '.join(stray)} is not a number the sentence writes; a value is copied as written and the tools convert it"
    return found[0], None


def _count(text: Any, sentence: str, what: str) -> tuple[int | None, str | None]:
    """A count as the sentence writes it, in digits or in words ("two plies", "add a step"), turned into a whole number by the table."""
    word = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    if word in COUNT_WORDS:
        if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", _plain(sentence)):
            return COUNT_WORDS[word], None
        return None, f"its {what} {text!r} is not written in the sentence"
    value, reason = _number(text, sentence, what)
    if reason:
        return None, reason
    if value != value.to_integral_value() or value < 1:
        return None, f"its {what} {text!r} is not a whole number of 1 or more"
    return int(value), None


def _first_error(exc: ValidationError) -> str:
    """The engine's own reason for a change it does not take, without pydantic's frame."""
    error = exc.errors()[0]
    message = str(error.get("msg", "")).removeprefix("Value error, ")
    where = ".".join(str(part) for part in error.get("loc", ()) if part != "__root__")
    return message if not where else f"{where}: {message}"


def _words(text: str) -> str:
    """An engine sentence after a colon: its first word in lower case unless it is a name, as an answer's line is written."""
    first, _, rest = text.partition(" ")
    if first[:1].isupper() and first[1:].islower() and first.isalpha():
        first = first.lower()
    return f"{first} {rest}" if rest else first


# ===================================================================================================== a wing (ADR-0122, ADR-0128)

WING_CHANGES = ("add_plies", "remove_plies")
WING_RUNS = ("analyze", "check")
WING_TOOLS = (*WING_CHANGES, *WING_RUNS, "answer")
WING_REPORTED = ("check", "answer")  # the page reports the check as its job ends (`/v1/wings/checks/{job}`), and each answer
WING_ARGS = ("part", "angle", "count", "from", "to", "placement", "question")
WING_LINES = {"analyze": "Work the wing by hand: every flight case, its margins, mass, deflection and frequencies",
              "check": "Run the finite element check of the wing beside the hand calculation"}
SPAN_ENDS = {"root": Decimal(0), "tip": Decimal(100)}  # where along the half span, in percent from the root, by its word

WING_TOOL_WORDS: dict[str, tuple[str, dict[str, str]]] = {
    "add_plies": ("Add plies of one angle to one part of the wing over a stretch of the half span (the whole span when the sentence names "
                  "none). A laminate stays symmetric: plies go in pairs, one each side of its middle, or one on each face of a sandwich.",
                  {"part": "the part, by name", "angle": "the ply angle in degrees, as the sentence writes it",
                   "count": "the plies of the whole laminate as the sentence writes them, in digits or a word",
                   "from": "where along the half span it starts: root, or a percentage of the half span as written; null for the root",
                   "to": "where it ends: tip, or a percentage of the half span as written; null for the tip",
                   "placement": "beside the plies of the same angle, or at the middle of the laminate; null for beside"}),
    "remove_plies": ("Take plies of one angle out of one part of the wing over a stretch of the half span (the whole span when the "
                     "sentence names none), the ones nearest the middle, in pairs.",
                     {"part": "the part, by name", "angle": "the ply angle in degrees, as the sentence writes it",
                      "count": "the plies of the whole laminate as the sentence writes them, in digits or a word",
                      "from": "where along the half span it starts: root, or a percentage of the half span as written; null for the root",
                      "to": "where it ends: tip, or a percentage of the half span as written; null for the tip"}),
    "analyze": ("Work the wing as it then stands by the hand calculation: every flight case, its margins, mass, tip deflection and "
                "frequencies, in a moment.", {}),
    "check": ("Run the finite element check of the wing as it then stands, beside the hand calculation: a background job of a minute or "
              "so, counted among the day's analyses.", {}),
    "answer": ("Answer a question about the result of the hand calculation or the check, from the result's own values, after it.",
               {"question": "the engineer's question about the result, in one short sentence"}),
}


def wing_parts(wing: dict[str, Any]) -> list[str]:
    """The parts whose plies a change may set: those of the wing file that the wing has (the spar caps only when it has them)."""
    return [part for part in PARTS if isinstance(wing.get(part), dict)]


def wing_view(ask: str, wing: dict[str, Any], refused: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the model is shown: the sentence, the wing's units and each part on offer with the outer half of its laminate and its zones
    (fractions of the half span from the root, as the wing file holds them), and the tools. Never the wing's title or source (R-11)."""
    parts = []
    for part in wing_parts(wing):
        table = wing[part]
        parts.append({"part": part, "is": PARTS[part], "half_stack": list(table.get("half_stack") or []),
                      "sandwich": bool(table.get("core") or table.get("core_thickness")),
                      "zones": [{"start": z.get("start"), "end": z.get("end"), "half_stack": list(z.get("half_stack") or [])}
                                for z in table.get("zones") or [] if isinstance(z, dict)]})
    view: dict[str, Any] = {"sentence": ask, "wing": {"units": wing.get("units"), "parts": parts},
                            "tools": [{"name": name, "does": WING_TOOL_WORDS[name][0], "takes": dict(WING_TOOL_WORDS[name][1])} for name in WING_TOOLS]}
    if refused is not None:
        view["refused"] = {"plan": refused["plan"], "reasons": list(refused["reasons"])}
    return view


def wing_schema(wing: dict[str, Any]) -> dict[str, Any]:
    text = {"type": "string"}
    parts = wing_parts(wing)
    return _schema(list(WING_TOOLS), {
        "part": _nullable({"type": "string", "enum": parts}) if parts else {"type": "null"}, "angle": _nullable(text), "count": _nullable(text),
        "from": _nullable(text), "to": _nullable(text), "placement": _nullable({"type": "string", "enum": ["beside", "middle"]}),
        "question": _nullable(text)})


def _span(text: Any, sentence: str, end: str) -> tuple[Decimal | None, str | None]:
    """Where along the half span, as a percentage from the root: `root` or `tip` by the word, else a percentage the sentence writes."""
    if text is None or not str(text).strip():
        return SPAN_ENDS["root" if end == "from" else "tip"], None
    word = str(text).strip().lower()
    if word in SPAN_ENDS:
        return SPAN_ENDS[word], None
    return _number(text, sentence, f"place along the span ({end})")


def _ply_change(tool: str, args: dict[str, Any], sentence: str, parts: list[str]) -> tuple[PlyChange | None, list[str]]:
    """A step's change of plies in the engine's form, every number the sentence's; or why it cannot be made one."""
    part = args.get("part")
    if part not in parts:
        return None, [f"{part or 'no part'} is not a part of this wing; it has {', '.join(parts)}"]
    reasons = []
    angle, reason = _number(args.get("angle"), sentence, "ply angle")
    if reason:
        reasons.append(reason)
    count, reason = _count(args.get("count"), sentence, "count of plies")
    if reason:
        reasons.append(reason)
    start, reason = _span(args.get("from"), sentence, "from")
    if reason:
        reasons.append(reason)
    end, reason = _span(args.get("to"), sentence, "to")
    if reason:
        reasons.append(reason)
    placement = args.get("placement") or "beside"
    if placement not in ("beside", "middle"):
        reasons.append(f"{placement!r} is not a placement; plies go beside those of the same angle, or at the middle")
    if reasons:
        return None, reasons
    try:
        change = PlyChange(action=tool, part=part, angle=float(angle), count=count, start=float(start / 100), end=float(end / 100),
                           placement=placement if tool == "add_plies" else "beside")
    except ValidationError as exc:
        return None, [_first_error(exc)]
    return change, []


def check_wing_plan(raw: dict[str, Any], sentence: str, wing: dict[str, Any]) -> Checked:
    """A wing's plan judged against the sentence and the wing it was worked out on: only the tools on offer; every quote words of the
    sentence; every part one the wing has; every number the sentence's; the changes first, then the hand calculation and the check, each
    once, then the answers; at most `MAX_STEPS` steps; and every change previewed by the engine on the wing as the changes before it
    leave it, every one or none. The steps kept carry the engine's own sentence as their line and its `PlyChange` as their change."""
    out, steps = _opened(raw, sentence)
    if steps is None:
        return out
    parts = wing_parts(wing)
    planned: list[tuple[int, str, PlyChange | None, str, str | None]] = []
    ran: list[str] = []
    for index, step in enumerate(steps, start=1):
        def refuse(reason: str, index: int = index) -> None:
            out.reasons.append(f"step {index}: {reason}")

        if not isinstance(step, dict):
            refuse("it is not a step")
            continue
        tool, args = step.get("tool"), step.get("args") if isinstance(step.get("args"), dict) else {}
        if tool not in WING_TOOLS:
            refuse(f"{tool!r} is not a tool on offer here; the tools are {', '.join(WING_TOOLS)}")
            continue
        quote_reason = _quote_reason(step.get("quote"), sentence)
        if quote_reason:
            refuse(quote_reason)
            continue
        quote = step["quote"].strip()
        if tool in WING_RUNS:
            if tool in ran:
                refuse("the plan works the wing by hand once" if tool == "analyze" else "the plan runs the check once")
                continue
            ran.append(tool)
            planned.append((index, tool, None, quote, None))
            continue
        if tool == "answer":
            reason = _question_reason(args.get("question"), sentence)
            if reason:
                refuse(reason)
            elif not ran:
                refuse("an answer reads the result of the hand calculation or the check, so it comes after one of them")
            else:
                planned.append((index, tool, None, quote, args["question"].strip()))
            continue
        if ran:
            refuse("a change after the hand calculation or the check would not be in it: the changes come first")
            continue
        change, reasons = _ply_change(tool, args, sentence, parts)
        for reason in reasons:
            refuse(reason)
        if change is not None:
            planned.append((index, tool, change, quote, None))

    if len(planned) > MAX_STEPS:
        out.reasons.append(f"the plan has {len(planned)} steps; a plan has at most {MAX_STEPS}")
    if out.reasons:
        return out

    lines: dict[int, str] = {}
    data = wing
    for index, _, change, _, _ in planned:
        if change is None:
            continue
        try:
            preview = preview_wing_change(data, change)  # the engine's change, worked by hand before and after
        except REFUSALS as exc:
            out.reasons.append(f"step {index}: {str(exc) or exc.__class__.__name__}")
            return out
        lines[index], data = preview["words"], preview["wing"]

    kept = []
    for index, tool, change, quote, asked in planned:
        if change is not None:
            kept.append(_step(0, "Setup", tool, lines[index], quote=quote, regions=[change.part], change=change.model_dump(mode="json")))
        elif tool == "answer":
            kept.append(_step(0, "Report", tool, answer_line(asked), quote=quote, question=asked))
        else:
            kept.append(_step(0, "Solver", tool, WING_LINES[tool], quote=quote))
    for n, step in enumerate(kept, start=1):
        step["n"] = n
    out.steps = kept
    return out


def make_wing_plan(assistant: Any, sentence: str, wing: dict[str, Any], calls: list) -> Planned:
    return plan_with(assistant, calls, view=lambda refused: wing_view(sentence, wing, refused), schema=wing_schema(wing),
                     check=lambda raw: check_wing_plan(raw, sentence, wing), system=WING_PLAN_SYSTEM)


def changed_wing(wing: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A wing plan's changes made in order by the engine (`change_wing`), for its approval: the wing file they give, or None when the
    plan changes nothing. A change the wing no longer takes raises the engine's refusal."""
    changes = [PlyChange(**step["change"]) for step in steps if step["tool"] in WING_CHANGES]
    if not changes:
        return None
    for change in changes:
        wing = change_wing(wing, change)
    return wing


# ===================================================================================================== a repair (ADR-0135, ADR-0136)

REPAIR_CHANGES = ("set", "add_steps", "remove_steps", "set_steps", "regroup", "regroup_steps")
REPAIR_TOOLS = (*REPAIR_CHANGES, "sweep", "use_pick", "solve", "bond", "answer")
REPAIR_RUNS = ("sweep", "solve", "bond")
REPAIR_REPORTED = ("answer",)  # the server carries the rest at the approval
REPAIR_ARGS = ("quantity", "value", "unit", "count", "angles", "start", "end", "load", "load_unit", "cut_faces", "question")
SET_QUANTITIES = tuple(QUANTITIES)
SWEPT = ("step_length", "bondline", "cover_overlap", "patch_overlap", "steps")
STEPS_WORDS = "the number of steps"
REPAIR_LINES = {"solve": "Solve the slice of the repair as it then stands", "bond": "Follow the bond until it lets go"}
CUT_FACES = ("open", "bonded")

# A unit as the engine spells it (engine units.py), from the page's own table (lib/repair-chat.ts, ENGINE_UNIT); a unit the engine has
# no name for goes to it as written and is refused there in its words.
REPAIR_UNITS = {
    "mm": "mm", "millimeter": "mm", "millimeters": "mm", "millimetre": "mm", "millimetres": "mm", "cm": "cm", "m": "m", "in": "in", "inch": "in",
    "inches": "in", '"': "in", "n/mm": "N/mm", "n/m": "N/m", "kn/m": "kN/m", "kn/mm": "kN/mm", "lb/in": "lb/in", "lbf/in": "lb/in", "lbs/in": "lb/in",
    "lb/inch": "lb/in", "lbf/inch": "lb/in", "lbs/inch": "lb/in", "pli": "lb/in", "kip/in": "kip/in", "kips/in": "kip/in", "psi": "psi", "ksi": "ksi",
    "msi": "Msi", "mpa": "MPa", "gpa": "GPa",
}
_UNIT_AFTER = re.compile(r"\s*(kn/mm|kn/m|n/mm|n/m|lbf?s?/in(?:ch)?|kips?/in|pli|millimet(?:er|re)s?|mm|cm|inch(?:es)?|in|\"|m|psi|ksi|msi|mpa|gpa)(?![a-z/])")

REPAIR_TOOL_WORDS: dict[str, tuple[str, dict[str, str]]] = {
    "set": ("Set one quantity of the repair to a value: the step length, the bondline's thickness, the load per unit width, the damage's "
            "diameter, the cover plies' overlap or the patch's overlap.",
            {"quantity": "the quantity, by name", "value": "the value as the sentence writes it", "unit": "the unit written beside it, or null"}),
    "add_steps": ("Add steps to the repair, each one more group of plies cut; a patch whose plies are listed needs the angles of the new "
                  "plies.", {"count": "how many steps, as written, in digits or a word",
                             "angles": "the angles of the new plies as the sentence writes them, or null"}),
    "remove_steps": ("Take steps away from the repair.", {"count": "how many steps, as written, in digits or a word"}),
    "set_steps": ("Make the number of steps a given number.", {"count": "the number of steps, as written",
                                                               "angles": "the angles of any new plies as written, or null"}),
    "regroup": ("Group the same plies in steps of a given number of plies each.", {"count": "the plies in each step, as written"}),
    "regroup_steps": ("Cut the same plies in a given number of equal steps.", {"count": "the number of steps, as written"}),
    "sweep": ("Work the repair by hand over a range of one quantity (the step length, the bondline's thickness, the cover plies' or the "
              "patch's overlap, or the number of steps the same plies are grouped in). With a load named it picks, by its own rule, the "
              "smallest repair whose adhesive is still elastic at that load.",
              {"quantity": "the quantity to vary, by name: the step length when the sentence names none", "start": "the range's start as written, or null",
               "end": "the range's end as written, or null", "unit": "the unit of the range as written, or null",
               "load": "the load per unit width the adhesive is to stay elastic at, as written, or null",
               "load_unit": "the unit written beside the load, or null"}),
    "use_pick": ("Make the repair the sweep's pick, right after the sweep: the pick is the sweep's own, so this step takes no value.", {}),
    "solve": ("Solve the slice of the repair as it then stands (a few seconds): its bondline's shear and peel, its plies and what reaches "
              "its limit first; after use_pick, the pick held to the load the sweep named.",
              {"cut_faces": "whether the adhesive on the cut faces of a flush repair carries load (bonded) or not (open); null for open"}),
    "bond": ("Follow the repair's bond until it lets go (up to a minute or so): the load where it first softens and where it lets go.", {}),
    "answer": ("Answer a question about the result of the sweep, the solve or the bond, from the result's own values, after it.",
               {"question": "the engineer's question about the result, in one short sentence"}),
}


def repair_digest(repair: dict[str, Any]) -> str:
    """The SHA-256 of a repair's description, the plan's `base`: its keys in order, and a whole number written as one whether it came as
    100 or 100.0, so a description that went through the browser's JSON is the same description."""
    def plain(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, list):
            return [plain(item) for item in value]
        if isinstance(value, float) and value.is_integer() and abs(value) < 2 ** 53:
            return int(value)
        return value
    return hashlib.sha256(json.dumps(plain(repair), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _system(repair: dict[str, Any]) -> dict[str, Any]:
    return UNIT_SYSTEMS.get(repair.get("units"), UNIT_SYSTEMS["mm-MPa"])


def repair_view(ask: str, repair: dict[str, Any], refused: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the model is shown: the sentence; the repair's units, whether its patch is flush or bonded on top, its steps and the plies in
    a step, whether the patch's plies are listed, and each quantity a change may set with its value as stated and its unit; and the
    tools. Never the repair's title or source (R-11)."""
    system = _system(repair)
    steps = repair.get("steps") if isinstance(repair.get("steps"), dict) else {}
    patch = repair.get("patch") if isinstance(repair.get("patch"), dict) else {}
    quantities = []
    for name, (table, key, kind, words) in QUANTITIES.items():
        stated = repair.get(table) if isinstance(repair.get(table), dict) else {}
        quantities.append({"quantity": name, "is": words, "value": stated.get(key), "unit": system[kind][1]})
    view: dict[str, Any] = {
        "sentence": ask,
        "repair": {"units": repair.get("units"), "patch": "bonded on top" if repair.get("kind") == "external" else "flush",
                   "steps": steps.get("count"), "plies_per_step": steps.get("plies", 1), "patch_plies_listed": isinstance(patch.get("layup"), list),
                   "quantities": quantities},
        "tools": [{"name": name, "does": REPAIR_TOOL_WORDS[name][0], "takes": dict(REPAIR_TOOL_WORDS[name][1])} for name in REPAIR_TOOLS]}
    if refused is not None:
        view["refused"] = {"plan": refused["plan"], "reasons": list(refused["reasons"])}
    return view


def repair_schema() -> dict[str, Any]:
    text = {"type": "string"}
    return _schema(list(REPAIR_TOOLS), {
        "quantity": _nullable({"type": "string", "enum": [*SET_QUANTITIES, "steps"]}), "value": _nullable(text), "unit": _nullable(text),
        "count": _nullable(text), "angles": _nullable({"type": "array", "items": text}), "start": _nullable(text), "end": _nullable(text),
        "load": _nullable(text), "load_unit": _nullable(text), "cut_faces": _nullable({"type": "string", "enum": list(CUT_FACES)}),
        "question": _nullable(text)})


def _unit(unit: Any, sentence: str) -> tuple[str | None, str | None]:
    """A unit as the step copies it, in the engine's spelling; or why it is not the sentence's."""
    if unit is None:
        return None, None
    written = str(unit).strip()
    if not written or _squash(written) not in _squash(sentence):
        return None, f"the unit {unit} is not written in the sentence"
    return REPAIR_UNITS.get(written.lower(), written), None


def units_beside(sentence: str, number: Decimal) -> list[str | None]:
    """The unit the sentence writes right after each place it writes the number, None where it writes none."""
    text = _plain(sentence)
    found: list[str | None] = []
    for match in _NUMBER.finditer(text):
        try:
            value = Decimal(match.group())
        except ArithmeticError:
            continue
        if abs(value) != abs(number):
            continue
        after = _UNIT_AFTER.match(text, match.end())
        found.append(after.group(1) if after else None)
    return found


def _no_unit(value: Decimal, unit: str | None, sentence: str) -> str | None:
    """A value given with no unit that the sentence writes with one everywhere: the engine would read it in the file's own unit."""
    if unit is not None:
        return None
    beside = units_beside(sentence, value)
    if beside and all(beside):
        return f"the sentence writes {setup_tools._written(abs(value))} {REPAIR_UNITS.get(beside[0], beside[0])}, and the step gives it with no unit"
    return None


def _repair_change(tool: str, args: dict[str, Any], sentence: str) -> tuple[RepairChange | None, list[str]]:
    """A step's change in the engine's form (`RepairChange`), every number the sentence's; or why it cannot be made one."""
    reasons = []
    if tool == "set":
        quantity = args.get("quantity")
        if quantity not in SET_QUANTITIES:
            return None, [f"{quantity or 'no quantity'} is not a quantity a change sets; they are {', '.join(SET_QUANTITIES)}"]
        value, reason = _number(args.get("value"), sentence, "value")
        unit, unit_reason = _unit(args.get("unit"), sentence)
        reasons += [r for r in (reason, unit_reason) if r]
        if not reasons:
            reasons += [r for r in (_no_unit(value, unit, sentence),) if r]
        if reasons:
            return None, reasons
        fields: dict[str, Any] = {"action": "set", "quantity": quantity, "value": float(value), "unit": unit}
    else:
        count, reason = _count(args.get("count"), sentence, "count")
        if reason:
            reasons.append(reason)
        angles = None
        if args.get("angles") is not None:
            angles = []
            for written in args["angles"] if isinstance(args["angles"], list) else [args["angles"]]:
                angle, reason = _number(written, sentence, "ply angle")
                if reason:
                    reasons.append(reason)
                else:
                    angles.append(float(angle))
        if reasons:
            return None, reasons
        fields = {"action": tool, "count": count, "angles": None if angles is None else tuple(angles)}
    try:
        return RepairChange(**fields), []
    except ValidationError as exc:
        return None, [_first_error(exc)]


def _sweep(args: dict[str, Any], sentence: str) -> tuple[RepairSweep | None, list[str]]:
    """A step's sweep in the engine's form (`RepairSweep`), every number the sentence's; or why it cannot be made one."""
    quantity = args.get("quantity")
    if quantity not in SWEPT:
        return None, [f"{quantity or 'no quantity'} is not a quantity a sweep varies; they are {', '.join(SWEPT)}"]
    reasons, fields = [], {"quantity": quantity}
    for name in ("start", "end", "load"):
        if args.get(name) is None:
            continue
        value, reason = _number(args.get(name), sentence, name)
        if reason:
            reasons.append(reason)
        else:
            fields[name] = float(value)
    for name, of in (("unit", "start"), ("load_unit", "load")):
        unit, reason = _unit(args.get(name), sentence)
        if reason:
            reasons.append(reason)
        elif unit is not None:
            fields[name] = unit
        elif of in fields:
            missing = _no_unit(Decimal(str(fields[of])), None, sentence)
            if missing:
                reasons.append(missing)
    if reasons:
        return None, reasons
    try:
        return RepairSweep(**fields), []
    except ValidationError as exc:
        return None, [_first_error(exc)]


def _sweep_line(sweep: RepairSweep, repair: dict[str, Any]) -> str:
    """A sweep's line: what it varies, over the range the sentence writes, and the load it picks at as written, each in its unit as
    written or the file's when none is."""
    system = _system(repair)
    written = lambda value: setup_tools._written(Decimal(str(value)))  # noqa: E731 - the sentence's own number, as it wrote it
    line = f"Sweep {STEPS_WORDS if sweep.quantity == 'steps' else QUANTITIES[sweep.quantity][3]}"
    if sweep.start is not None:
        line += f" from {written(sweep.start)} to {written(sweep.end)} {sweep.unit or system[QUANTITIES[sweep.quantity][2]][1]}"
    if sweep.load is not None:
        line += f", picking by its rule the smallest repair whose adhesive is still elastic at {written(sweep.load)} {sweep.load_unit or system['N'][1]}"
    return line


def _pick_change(found: dict[str, Any]) -> RepairChange:
    """The sweep's pick as the change that makes it (the value of its row), so its line is the engine's own sentence."""
    row = found["rows"][found["pick"]]
    if found["sweep"]["quantity"] == "steps":
        return RepairChange(action="regroup", count=row["plies_per_step"])
    return RepairChange(action="set", quantity=found["sweep"]["quantity"], value=row["value"])


def tool_needs(tool: str, repair: dict[str, Any]) -> str | None:
    """What the solve or the bond still needs of the repair as it then stands, in the engine's words; None when nothing."""
    stated, load = repair_from_dict(repair)
    if tool == "solve":
        needs = solve_needs(stated, load)
        return None if not needs else "The solve of the slice needs: " + "; ".join(need["words"] for need in needs) + "."
    needs = bond_needs(stated)
    return None if not needs else "To follow the bond until it lets go the repair needs: " + "; ".join(need["words"] for need in needs) + "."


def check_repair_plan(raw: dict[str, Any], sentence: str, repair: dict[str, Any]) -> Checked:
    """A repair's plan judged against the sentence and the description it was worked out on: only the tools on offer; every quote words of
    the sentence; every number the sentence's (a unit converted only by the engine); the changes and one sweep first, `use_pick` only
    right after a sweep that names a load and with no value of its own (the pick is the sweep's); then the solve and the bond, each once;
    then the answers; at most `MAX_STEPS` steps. Then everything previewed by the engine in order, every one or none: each change, the
    sweep worked by hand, its pick (a sweep with none refuses the plan with its own answer), and what a solve or a bond still needs."""
    out, steps = _opened(raw, sentence)
    if steps is None:
        return out
    planned: list[tuple[int, str, Any, str, str | None]] = []  # (step, tool, its change, its sweep or its cut faces, its quote, its question)
    ran: list[str] = []
    previous = None  # the tool of the step before, kept or refused
    for index, step in enumerate(steps, start=1):
        def refuse(reason: str, index: int = index) -> None:
            out.reasons.append(f"step {index}: {reason}")

        if not isinstance(step, dict):
            refuse("it is not a step")
            continue
        tool, args = step.get("tool"), step.get("args") if isinstance(step.get("args"), dict) else {}
        before, previous = previous, tool
        if tool not in REPAIR_TOOLS:
            refuse(f"{tool!r} is not a tool on offer here; the tools are {', '.join(REPAIR_TOOLS)}")
            continue
        quote_reason = _quote_reason(step.get("quote"), sentence)
        if quote_reason:
            refuse(quote_reason)
            continue
        quote = step["quote"].strip()
        if tool == "answer":
            reason = _question_reason(args.get("question"), sentence)
            if reason:
                refuse(reason)
            elif not ran:
                refuse("an answer reads the result of the sweep, the solve or the bond, so it comes after one of them")
            else:
                planned.append((index, tool, None, quote, args["question"].strip()))
            continue
        if tool in ("solve", "bond"):
            if tool in ran:
                refuse("the plan solves the slice once" if tool == "solve" else "the plan follows the bond once")
                continue
            ran.append(tool)
            cut = args.get("cut_faces") or "open"
            if tool == "solve" and cut not in CUT_FACES:
                refuse(f"{cut!r} is not a choice of the cut faces; they are open or bonded")
                continue
            planned.append((index, tool, {"cut_faces": cut} if tool == "solve" else None, quote, None))
            continue
        if any(done in ran for done in ("solve", "bond")):
            refuse("a change or a sweep after the solve or the bond would not be in it: they come first")
            continue
        if tool == "use_pick":
            given = [name for name in ("value", "unit", "count", "angles", "start", "end", "load", "load_unit") if args.get(name) not in (None, [], "")]
            last = planned[-1] if planned else None
            if given:
                refuse(f"the pick is the sweep's own: use_pick takes no value, and this one gives {', '.join(given)}")
            elif before != "sweep":
                refuse("use_pick takes the pick of the sweep just before it, and there is none")
            elif last is None or last[1] != "sweep":
                pass  # the sweep just before it is refused, and its reasons say why
            elif last[2].load is None:
                refuse("the sweep before it names no load, so it picks nothing: a pick is the smallest repair whose adhesive stays elastic at a load")
            else:
                planned.append((index, tool, None, quote, None))
            continue
        if tool == "sweep":
            if "sweep" in ran:
                refuse("the plan sweeps once")
                continue
            ran.append("sweep")
            sweep, reasons = _sweep(args, sentence)
            for reason in reasons:
                refuse(reason)
            if sweep is not None:
                planned.append((index, tool, sweep, quote, None))
            continue
        change, reasons = _repair_change(tool, args, sentence)
        for reason in reasons:
            refuse(reason)
        if change is not None:
            planned.append((index, tool, change, quote, None))

    if len(planned) > MAX_STEPS:
        out.reasons.append(f"the plan has {len(planned)} steps; a plan has at most {MAX_STEPS}")
    if out.reasons:
        return out

    kept = []
    data, found, picked = repair, None, False
    for index, tool, typed, quote, asked in planned:
        try:
            if tool in REPAIR_CHANGES:
                preview = preview_repair_change(data, typed)  # the engine's change, read and worked by hand before and after
                role = "Setup" if typed.quantity == "load" else "Geometry"
                kept.append(_step(0, role, tool, preview["words"], quote=quote, change=typed.model_dump(mode="json")))
                data = preview["repair"]
            elif tool == "sweep":
                found = sweep_repair(data, typed)  # worked by hand at every value, in milliseconds
                kept.append(_step(0, "Solver", tool, _sweep_line(typed, data), quote=quote, change=typed.model_dump(mode="json")))
            elif tool == "use_pick":
                if found["pick"] is None:
                    out.reasons.append(f"step {index}: the sweep picks nothing to use: {' '.join(found['answer'])}")
                    return out
                change = _pick_change(found)
                words = preview_repair_change(data, change)["words"]
                kept.append(_step(0, "Geometry", tool, f"Use the sweep's pick: {_words(words)}", quote=quote, change=change.model_dump(mode="json")))
                data, picked = found["picked"], True
            elif tool in ("solve", "bond"):
                missing = tool_needs(tool, data)
                if missing:
                    out.reasons.append(f"step {index}: {missing}")
                    return out
                line = REPAIR_LINES[tool]
                if tool == "solve":
                    line += ", the cut faces bonded" if typed["cut_faces"] == "bonded" else ""
                    line += ", and hold the sweep's pick to the load it names" if picked else ""
                kept.append(_step(0, "Solver", tool, line, quote=quote, change=typed))
            else:
                kept.append(_step(0, "Report", tool, answer_line(asked), quote=quote, question=asked))
        except REFUSALS as exc:
            out.reasons.append(f"step {index}: {str(exc) or exc.__class__.__name__}")
            return out
    for n, step in enumerate(kept, start=1):
        step["n"] = n
    out.steps = kept
    return out


def make_repair_plan(assistant: Any, sentence: str, repair: dict[str, Any], calls: list) -> Planned:
    return plan_with(assistant, calls, view=lambda refused: repair_view(sentence, repair, refused), schema=repair_schema(),
                     check=lambda raw: check_repair_plan(raw, sentence, repair), system=REPAIR_PLAN_SYSTEM)


# ===================================================================================================== what each kind reports and keeps

REPORTED = {"wing": WING_REPORTED, "repair": REPAIR_REPORTED}  # a coupon's and a plate's are `planner.REPORTED`


def run_summary(tool: str, answer: dict[str, Any]) -> dict[str, Any]:
    """What a run record keeps of a run an approval carried, as each run's own route keeps it: never the drawings, the curves or the
    slice's fields (ADR-0026)."""
    if tool == "analyze":
        report = answer.get("report") or {}
        return {key: report.get(key) for key in ("wing", "passes", "seconds", "design", "governing", "aeroelastic")}
    if tool == "check":
        return {key: answer.get(key) for key in ("job_id", "state", "message")}
    if tool == "sweep":
        pick = answer.get("pick")
        return {"sweep": answer.get("sweep"), "words": answer.get("words"), "rows": len(answer.get("rows") or []), "target": answer.get("target"),
                "pick": None if pick is None else answer["rows"][pick], "flat_from": answer.get("flat_from")}
    report = answer.get("report") or {}
    summary = {"headline": answer.get("headline"), "model": report.get("model"), "checks": report.get("checks")}
    if tool == "solve":
        check = answer.get("check")
        summary |= {"first": report.get("first"),
                    "check": None if check is None else {key: check.get(key) for key in ("state", "holds", "close", "first", "words")}}
    else:
        summary |= {"ended": report.get("ended"), "largest_load": (report.get("largest") or {}).get("load")}
    return summary
