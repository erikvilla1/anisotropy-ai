"""The workspace's planner (ADR-0144, build step 2): one call to the model turns an engineer's sentence into a plan of typed tool steps,
the checks here decide whether the plan is kept, and one approval applies its changes and starts its run. Nothing here computes a
result (ADR-0001) and nothing here calls the model itself: the caller hands in the writer (`assistant.py`), and the typed changes are
the workspace's own tools (`setup_tools.py`, ADR-0143), which work out every change and every unit conversion.

- `tools_for`: the tools offered for a model: a plate's supports and loads (`hold`, `move`, `force`, `pressure`, `free`, `unload`), a
  row of the form (`row`, a coupon's only change), `run` and `answer`. The server, never the model, puts `check` before a run and `qa`
  after it.
- `plan_view`: what the model sees: the sentence, the setup as `read_setup` reads it, the rows a `row` change may set and the tools,
  in plain words. Never a name, a note, an email or another project (R-11).
- `plan_schema`: the model's answer, a fixed JSON schema: steps (a tool, its arguments, the words that ask for it), a question asked
  back when the words fit two regions, and the words it did not read (`unread`, as the proposals' are, ADR-0088 amendment 1).
- `check_plan`: what the server checks before a plan is kept: only tools on offer; at most `MAX_STEPS` steps with the server's own;
  every change previewed by `setup_tools.change_setup`, every one or none; every region one the model has; every number in a step
  written in the sentence (a unit converted only by the tools); every quote a span of the sentence; one run, the changes before it and
  the answers after it. A plan kept is a list of steps, each with its role, its one line and its state.
- `make_plan`: one call, one more with the reasons when the plan fails the checks, then the plan, the question or why there is none.
- `run_values`: the values a run and its check take for the setup, exactly as the page's `workspaceValues` (`lib/tension-screen.ts`)
  writes them, so a plan's run is the run the page would start.
- `report_step`: a step the page carries (`run`, `qa`, `answer`) reported, and the plan's state that follows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from . import setup_tools
from .proposals import (_NUMBER, COUPON_UNITS, HIDDEN_ENDINGS, HIDDEN_KEYS, MAX_QUOTE, UNREAD_REASONS, _plain, _squash, numbers_written,
                        unit_named)

MAX_STEPS = 12  # a plan's steps, the server's check and qa among them (ADR-0144)
MAX_ASK = 1000
MAX_QUESTION = 200
MAX_UNREAD = 5
MAX_NOTE = 400
STATES = ("proposed", "question", "refused", "unavailable", "capped", "approved", "running", "done", "stopped")
STEP_STATES = ("planned", "running", "done", "failed", "skipped")
# A request that asked no model is no plan: it is not counted against the day's planned requests.
UNCOUNTED = ("capped", "unavailable")
# Why no model was asked: the person's planned requests today reached the day's limit (ADR-0144). The page reads the state `capped`.
PLAN_LIMIT_REASON = "the day's limit of planned requests for this sign-in is reached"
AGENT_REQUESTS_DEFAULT = 30

PLATE_TOOLS = ("hold", "move", "force", "pressure", "free", "unload")
CHANGE_TOOLS = setup_tools.ACTIONS
OFFERED = (*PLATE_TOOLS, "row", "run", "answer")  # what a model may name; `check` and `qa` are the server's
SERVER_TOOLS = ("check", "qa")
REPORTED = ("run", "qa", "answer")  # the steps the page carries and reports (ADR-0144)
DOFS = (1, 2, 3, 4, 5, 6)
ARGS = ("region", "dofs", "dof", "sense", "value", "unit", "key", "question")
# The arguments each change takes, in the order the page's fixtures write them.
CHANGE_ARGS: dict[str, tuple[str, ...]] = {
    "hold": ("region", "dofs"), "move": ("region", "dof", "value", "unit"), "force": ("region", "sense", "dof", "value", "unit"),
    "pressure": ("region", "value", "unit"), "free": ("region",), "unload": ("region",), "row": ("key", "value", "unit"),
}
# The rows of size or shape: a change to one of them is the Geometry's; every other change is the Setup's.
GEOMETRY_KEYS = frozenset({"length", "width", "thickness", "tab_length", "tab_thickness", "tab_bevel", "narrow_width", "narrow_length",
                           "radius", "outer_radius", "span", "overhang", "load_span", "hole_diameter"})
ROLES = {"check": "Solver", "run": "Solver", "qa": "QA", "answer": "Report"}
LINES = {"check": "Check the setup before the run", "run": "Run the analysis"}
QA_LINES = {True: "Check the result: reference solver, mesh study, equilibrium, held corners",
            False: "Check the result: reference solver, mesh study, equilibrium"}
ANGLE_WORDS = frozenset({"deg", "degs", "degree", "degrees", "°", "rad", "radian", "radians"})
_UNIT_AFTER = re.compile(r"\s*([a-zµμ°\"]+(?:\s*/\s*[a-z]+)?)")

# What each tool does and takes, in the words the model is shown.
TOOL_WORDS: dict[str, tuple[str, dict[str, str]]] = {
    "hold": ("Hold a region of the plate in the directions given; it takes the place of the hold the region had.",
             {"region": "the region, by name", "dofs": "the directions held, each once: 1, 2, 3 along x, y, z and 4, 5, 6 about them; "
                                                       "clamped, fixed or built-in is all six; pinned is 1, 2 and 3"}),
    "move": ("Move a region by a set amount along one direction, or turn it about one.",
             {"region": "the region, by name", "dof": "the direction: 1, 2, 3 along x, y, z, or 4, 5, 6 about them",
              "value": "the amount as the sentence writes it", "unit": "the unit written beside it, or null"}),
    "force": ("A force on a region, the total over it; it takes the place of the region's force along that direction.",
              {"region": "the region, by name", "sense": "tension or compression on a straight edge, which takes its direction from the "
                                                         "edge; null when a direction is given",
               "dof": "the direction, 1, 2 or 3 (x, y, z), with the value signed; null when a sense is given",
               "value": "the force as the sentence writes it", "unit": "the unit written beside it, or null"}),
    "pressure": ("A pressure on an area, positive pressing down on the plate; it takes the place of the area's pressure.",
                 {"region": "the area, by name", "value": "the pressure as the sentence writes it, with a minus sign for suction",
                  "unit": "the unit written beside it, or null"}),
    "free": ("Remove every hold and set move on a region.", {"region": "the region, by name"}),
    "unload": ("Remove every load on a region.", {"region": "the region, by name"}),
    "row": ("Set a row of the form, by its key: a size, the material, a ply's angle, the element size.",
            {"key": "the row's key, from those listed", "value": "the value as the sentence writes it, or a choice of the row's",
             "unit": "the unit written beside it, or null"}),
    "run": ("Run the analysis of the model as it then stands, after every change before it.", {}),
    "answer": ("Answer a question about the result of the run, from the result's own checks and values, after the run.",
               {"question": "the engineer's question about the result, in one short sentence"}),
}


# ----------------------------------------------------------------------------------------------- what the model is offered and shown

def is_plate(content: dict[str, Any]) -> bool:
    return setup_tools.form_of(content).get("test") == setup_tools.plate_test()


def tool_names(content: dict[str, Any]) -> list[str]:
    """The tools offered for this model: a coupon's supports and loads are its test's grips, so it is offered rows, a run and answers."""
    return [*PLATE_TOOLS, "row", "run", "answer"] if is_plate(content) else ["row", "run", "answer"]


def tools_for(content: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"name": name, "does": TOOL_WORDS[name][0], "takes": dict(TOOL_WORDS[name][1])} for name in tool_names(content)]


def offered_rows(content: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows a `row` change may set: those the form shows for the model's test, less the test and the units (set on the page), and
    less every row that names a person, a source, a note or the team's own names (R-11). Each with its label in the model's units, its
    kind, its choices and its value as written."""
    form = setup_tools.form_of(content)
    units = setup_tools.units_of(form)
    rows = []
    for f in setup_tools._fields():
        key = f["key"]
        if (key in setup_tools.FIXED_ROWS or key in HIDDEN_KEYS or key.endswith(HIDDEN_ENDINGS) or key.startswith("name_")
                or not setup_tools._visible(key, form)):
            continue
        row = {"key": key, "label": f.get("labels", {}).get(units, f["label"]), "kind": f["kind"]}
        if f.get("words"):
            row["choices"] = list(f["words"])
        row["value"] = (form.get(key) or "").strip() or None
        rows.append(row)
    return rows


def plan_view(ask: str, content: dict[str, Any], refused: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the model is shown: the sentence, the setup as `read_setup` reads it, the rows and the tools. With `refused`, the plan it
    gave before and why the server refused it, for its one more try."""
    setup = setup_tools.read_setup(content)
    setup.pop("digest", None)
    view: dict[str, Any] = {"sentence": ask, "setup": setup, "rows": offered_rows(content), "tools": tools_for(content)}
    if refused is not None:
        view["refused"] = {"plan": refused["plan"], "reasons": list(refused["reasons"])}
    return view


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def plan_schema(content: dict[str, Any]) -> dict[str, Any]:
    """The model's answer, compiled once per model's offer (structured outputs): tools, regions and rows by name from those offered;
    every argument a tool does not take is null."""
    regions = [r["name"] for r in setup_tools.regions(content)] if is_plate(content) else []
    keys = [r["key"] for r in offered_rows(content)]
    text = {"type": "string"}
    args = {
        "type": "object",
        "properties": {
            "region": _nullable({"type": "string", "enum": regions}) if regions else {"type": "null"},
            "dofs": _nullable({"type": "array", "items": {"type": "integer", "enum": list(DOFS)}}),
            "dof": _nullable({"type": "integer", "enum": list(DOFS)}),
            "sense": _nullable({"type": "string", "enum": ["tension", "compression"]}),
            "value": _nullable(text),
            "unit": _nullable(text),
            "key": _nullable({"type": "string", "enum": keys}) if keys else {"type": "null"},
            "question": _nullable(text),
        },
        "required": list(ARGS),
        "additionalProperties": False,
    }
    step = {"type": "object", "properties": {"tool": {"type": "string", "enum": tool_names(content)}, "args": args, "quote": text},
            "required": ["tool", "args", "quote"], "additionalProperties": False}
    unread = {"type": "object", "properties": {"quote": text, "reason": {"type": "string", "enum": list(UNREAD_REASONS)}},
              "required": ["quote", "reason"], "additionalProperties": False}
    return {"type": "object",
            "properties": {"steps": {"type": "array", "items": step}, "question": _nullable(text), "unread": {"type": "array", "items": unread}},
            "required": ["steps", "question", "unread"], "additionalProperties": False}


# ----------------------------------------------------------------------------------------------- the checks before a plan is kept

@dataclass
class Checked:
    """What the checks make of the model's answer: the plan's steps when it is kept, the question it asks back, the words it did not
    read, and why the plan cannot be kept, one reason each."""

    steps: list[dict[str, Any]] = field(default_factory=list)
    question: str | None = None
    unread: list[dict[str, str]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons


def _decimal(token: str) -> Decimal | None:
    try:
        value = Decimal(token)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _numbers(text: str) -> set[Decimal]:
    return {abs(n) for n in numbers_written(text)}


def stray_numbers(text: str, sentence: str) -> list[str]:
    """The numbers the text writes that the sentence does not, as written (a sign may come from the words: a push is a negative force)."""
    written = _numbers(sentence)
    return [setup_tools._written(abs(n)) for n in numbers_written(text) if abs(n) not in written]


def _unit_word(word: str, angle: bool) -> str | None:
    """A unit typed after a number: one of a coupon's (a length, a force, a stress) or, for a turn, an angle's; None for another word."""
    word = word.strip()
    if angle:
        return word if word in ANGLE_WORDS else None
    named = unit_named(word)
    return named if named in COUPON_UNITS else None


def units_beside(sentence: str, number: Decimal, angle: bool = False) -> list[str | None]:
    """The unit the sentence writes right after each place it writes the number (as `numbers_written` reads it), None where it writes none."""
    text = _plain(sentence)
    found: list[str | None] = []
    for match in _NUMBER.finditer(text):
        value = _decimal(match.group())
        if value is None or abs(value) != abs(number):
            continue
        after = _UNIT_AFTER.match(text, match.end())
        found.append(_unit_word(after.group(1), angle) if after else None)
    return found


def _value_reasons(change: dict[str, Any], sentence: str) -> list[str]:
    """Why a change's value cannot be the sentence's: a number it does not write, a unit it does not write, or a value the sentence writes
    with a unit given with none (which the tools would read in the model's own units)."""
    reasons = []
    value, unit = change.get("value"), change.get("unit")
    if value is None:
        return reasons
    stray = stray_numbers(str(value), sentence)
    if stray:
        reasons.append(f"{', '.join(stray)} is not a number the sentence writes; a value is copied as written and the tools convert it")
        return reasons
    if unit is not None:
        if not str(unit).strip() or _squash(str(unit)) not in _squash(sentence):
            reasons.append(f"the unit {unit} is not written in the sentence")
        return reasons
    angle = change.get("action") == "move" and isinstance(change.get("dof"), int) and change["dof"] >= 4
    for number in numbers_written(str(value)):
        beside = units_beside(sentence, number, angle)
        if beside and all(beside):
            reasons.append(f"the sentence writes {setup_tools._written(abs(number))} {beside[0]}, and the step gives it with no unit")
    return reasons


def _quote_reason(quote: Any, sentence: str) -> str | None:
    if not isinstance(quote, str) or not quote.strip():
        return "it quotes no words of the sentence"
    if len(quote) > MAX_QUOTE or _plain(quote) not in _plain(sentence):
        return "its quote is not words of the sentence"
    return None


def _question_reason(question: Any, sentence: str) -> str | None:
    if not isinstance(question, str) or not question.strip():
        return "an answer names the question it answers"
    if len(question.strip()) > MAX_QUESTION:
        return f"its question is longer than {MAX_QUESTION} characters"
    stray = stray_numbers(question, sentence)
    if stray:
        return f"its question writes {', '.join(stray)}, which the sentence does not"
    return None


def _change(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """The typed change a step names, as `change_setup` takes it: the action and the arguments it uses, none left null."""
    change: dict[str, Any] = {"action": tool}
    for name in CHANGE_ARGS[tool]:
        value = args.get(name)
        if value is None:
            continue
        change[name] = list(value) if isinstance(value, list) else value
    return change


def _unread(raw: Any, sentence: str, quoted: set[str]) -> list[dict[str, str]]:
    """What the sentence asks and no step takes: the engineer's own words, once each, with a reason by name (as the proposals', ADR-0088
    amendment 1). Anything else is left out."""
    kept: list[dict[str, str]] = []
    for item in raw if isinstance(raw, list) else []:
        if len(kept) >= MAX_UNREAD:
            break
        if not isinstance(item, dict):
            continue
        quote, reason = str(item.get("quote", "")).strip(), str(item.get("reason", ""))
        plain = _plain(quote)
        if not plain or len(quote) > MAX_QUOTE or plain not in _plain(sentence) or reason not in UNREAD_REASONS or plain in quoted:
            continue
        quoted.add(plain)
        kept.append({"quote": quote, "reason": reason})
    return kept


def answer_line(question: str) -> str:
    """An answer step's line: the question after "Answer:", its first word in lower case unless it is a name (Edge-Top, Tsai-Wu)."""
    first, _, rest = question.partition(" ")
    if first[:1].isupper() and first[1:].islower() and first.isalpha():
        first = first.lower()
    return f"Answer: {first}{' ' + rest if rest else ''}"


def _step(n: int, tool: str, line: str, *, quote: str | None = None, change: dict[str, Any] | None = None, question: str | None = None,
          plate: bool = True) -> dict[str, Any]:
    regions = [change["region"]] if change and change.get("region") else []
    role = ROLES.get(tool) or ("Geometry" if change and change.get("action") == "row" and change.get("key") in GEOMETRY_KEYS else "Setup")
    return {"n": n, "role": role, "tool": tool, "line": line, "quote": quote, "regions": regions, "change": change, "question": question,
            "state": "planned", "note": None}


def check_plan(raw: dict[str, Any], sentence: str, content: dict[str, Any]) -> Checked:
    """The model's answer judged against the sentence and the setup it was worked out on. A question asked back stands alone, with no
    step; otherwise every check below must pass, or the plan is not kept and each reason says which step failed and why."""
    out = Checked()
    steps = raw.get("steps")
    steps = steps if isinstance(steps, list) else []
    quoted = {_plain(s["quote"]) for s in steps if isinstance(s, dict) and isinstance(s.get("quote"), str) and s["quote"].strip()}
    out.unread = _unread(raw.get("unread"), sentence, quoted)

    question = raw.get("question")
    if isinstance(question, str) and question.strip():
        reason = None
        if len(question.strip()) > MAX_QUESTION:
            reason = f"the question back is longer than {MAX_QUESTION} characters"
        elif stray_numbers(question, sentence):
            reason = f"the question back writes {', '.join(stray_numbers(question, sentence))}, which the sentence does not"
        if reason:
            out.reasons.append(reason)
        else:
            out.question = question.strip()
        return out
    if not steps:
        out.reasons.append("the plan has no step and asks no question")
        return out

    offered = tool_names(content)
    plate = is_plate(content)
    regions = {r["name"] for r in setup_tools.regions(content)} if plate else set()
    rows = {r["key"] for r in offered_rows(content)}
    planned: list[tuple[int, str, dict[str, Any] | None, str, str | None]] = []  # (step, tool, change, quote, question)
    ran_at: int | None = None
    for index, step in enumerate(steps, start=1):
        def refuse(reason: str, index: int = index) -> None:
            out.reasons.append(f"step {index}: {reason}")

        if not isinstance(step, dict):
            refuse("it is not a step")
            continue
        tool, args = step.get("tool"), step.get("args") if isinstance(step.get("args"), dict) else {}
        if tool not in offered:
            refuse(f"{tool!r} is not a tool on offer here; the tools are {', '.join(offered)}")
            continue
        quote_reason = _quote_reason(step.get("quote"), sentence)
        if quote_reason:
            refuse(quote_reason)
            continue
        quote = step["quote"].strip()
        if tool == "run":
            if ran_at is not None:
                refuse("the plan runs the analysis once")
                continue
            ran_at = index
            planned.append((index, tool, None, quote, None))
            continue
        if tool == "answer":
            reason = _question_reason(args.get("question"), sentence)
            if reason:
                refuse(reason)
            elif ran_at is None:
                refuse("an answer reads the result of the plan's run, so it comes after a run")
            else:
                planned.append((index, tool, None, quote, args["question"].strip()))
            continue
        change = _change(tool, args)
        if ran_at is not None:
            refuse("a change after the run would not be in it: the changes come before the run")
            continue
        if tool == "row":
            if change.get("key") not in rows:
                refuse(f"{change.get('key') or 'no row'} is not a row on offer")
                continue
        elif change.get("region") not in regions:
            refuse(f"{change.get('region') or 'no region'} is not a region of this model; it has {', '.join(sorted(regions)) or 'none'}")
            continue
        value_reasons = _value_reasons(change, sentence)
        if value_reasons:
            for reason in value_reasons:
                refuse(reason)
            continue
        planned.append((index, tool, change, quote, None))

    total = len(planned) + (len(SERVER_TOOLS) if ran_at is not None else 0)
    if total > MAX_STEPS:
        out.reasons.append(f"the plan has {total} steps with the checks the software adds; a plan has at most {MAX_STEPS}")
    if out.reasons:
        return out

    changes = [(index, change) for index, tool, change, _, _ in planned if change is not None]
    done: list[str] = []
    if changes:
        previewed = setup_tools.change_setup(content, [change for _, change in changes])
        if not previewed.ok:
            for refused in previewed.refused:
                where = changes[refused["change"] - 1][0] if refused["change"] >= 1 else None
                out.reasons.append(f"step {where}: {refused['reason']}" if where else refused["reason"])
            return out
        done = previewed.done

    kept: list[dict[str, Any]] = []
    lines = iter(done)
    for _, tool, change, quote, asked in planned:
        if tool == "run":
            kept.append(_step(0, "check", LINES["check"]))
            kept.append(_step(0, "run", LINES["run"], quote=quote))
            kept.append(_step(0, "qa", QA_LINES[plate]))
        elif tool == "answer":
            kept.append(_step(0, "answer", answer_line(asked), quote=quote, question=asked))
        else:
            kept.append(_step(0, tool, next(lines), quote=quote, change=change))
    for n, step in enumerate(kept, start=1):
        step["n"] = n
    out.steps = kept
    return out


def done_lines(steps: list[dict[str, Any]]) -> list[str]:
    """What the plan's changes do, one line each: the preview's own lines (ADR-0143)."""
    return [step["line"] for step in steps if step.get("change") is not None]


def changes_of(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(step["change"]) for step in steps if step.get("change") is not None]


# ----------------------------------------------------------------------------------------------- one call, one more try

@dataclass
class Planned:
    """What a request comes to: a plan proposed, a question asked back, a plan refused with the reasons, or no reading at all."""

    state: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    question: str | None = None
    unread: list[dict[str, str]] = field(default_factory=list)
    reason: str | None = None
    writer: str = "template"
    model: str | None = None


def _billed(calls: list, reading: Any) -> Any:
    if getattr(reading, "call", None) is not None:
        calls.append(reading.call)
    return reading


def make_plan(assistant: Any, sentence: str, content: dict[str, Any], calls: list) -> Planned:
    """The plan for a sentence: one call to the model; when its plan fails the checks, one more with the plan and the reasons; then the
    plan, the question asked back, or `refused` with why. With no model, or none that answered, `unavailable` with the writer's reason
    and the page reads the sentence as before. Every call made is added to `calls`, kept or not (ADR-0120)."""
    schema = plan_schema(content)
    reading = _billed(calls, assistant.plan(plan_view(sentence, content), schema))
    if reading.raw is None:
        return Planned("unavailable", reason=reading.reason, writer="template")
    checked = check_plan(reading.raw, sentence, content)
    if not checked.ok:
        again = _billed(calls, assistant.plan(plan_view(sentence, content, {"plan": reading.raw, "reasons": checked.reasons}), schema))
        if again.raw is None:
            return Planned("refused", unread=checked.unread, reason="; ".join(checked.reasons))
        retried = check_plan(again.raw, sentence, content)
        if not retried.ok:
            return Planned("refused", unread=retried.unread, reason="; ".join(retried.reasons))
        reading, checked = again, retried
    if checked.question is not None:
        return Planned("question", question=checked.question, unread=checked.unread, writer=reading.writer, model=reading.model)
    return Planned("proposed", steps=checked.steps, unread=checked.unread, writer=reading.writer, model=reading.model)


# ----------------------------------------------------------------------------------------------- the values a run takes

TENSION_INPUT = "tension"
LEFT_AT_DEFAULT = ("element_size",)
OWN_MATERIAL_KEYS = ("own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6", "own_source",
                     "ply_thickness", "G13", "G23")
LIBRARY_TOO = ("ply_thickness", "G13", "G23")


def _js_string(value: Any) -> str:
    """A number of the form definition as the page's `String(value)` writes it: 2.0 is "2"."""
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    text = repr(value)
    if "e" in text and 1e-7 <= abs(value) < 1e21:
        text = format(Decimal(text), "f")
    return text


def tension_keys() -> list[str]:
    """Every row the tension screen may send (`TENSION_KEYS`)."""
    plies = [f["key"] for f in setup_tools._fields() if re.fullmatch(r"ply_\d+", f["key"])]
    return ["library", *plies, "symmetric", "standard", "filled_by", *OWN_MATERIAL_KEYS, "control", "value", "length", "width", "tab_length",
            "element_size"]


def tension_values(form: dict[str, str]) -> dict[str, Any]:
    """The values the tension screen sends (`tensionValues`): its own rows only, numbers parsed, blanks left out, and `"input":
    "tension"` so the fea package chooses the rest; the default units unsaid, a library material without the own constants, an own
    material without a library id, and the element size left to the package while it is the blank form's."""
    definition = setup_tools.form_definition()
    values: dict[str, Any] = {"form_version": definition["form_version"], "input": TENSION_INPUT}
    units = setup_tools.units_of(form)
    if units != definition["units"]:
        values["units"] = units
    own = not (form.get("library") or "").strip()
    for key in tension_keys():
        if (key == "library") if own else (key in OWN_MATERIAL_KEYS and key not in LIBRARY_TOO):
            continue
        if key == "standard" and not (form.get("test") or "").strip():
            continue
        text = (form.get(key) or "").strip()
        if not text:
            continue
        f = setup_tools._field(key) or {}
        if key in LEFT_AT_DEFAULT:
            default = (f.get("defaults") or {}).get(units)
            if text == _js_string(default if default is not None else f.get("default")):
                continue
        number = f.get("kind") in ("number", "whole", "angle") and setup_tools.NUMBER.match(text)
        values[key] = setup_tools._js_number(text) if number else text
    return values


def run_values(content: dict[str, Any], all_tests: bool) -> dict[str, Any]:
    """The values the page sends for a project as it stands (`workspaceValues`): with every test offered, every row the form shows; else
    the tension screen's rows, or a plate's with what the package chooses for it."""
    form, lists = setup_tools.form_of(content), setup_tools.lists_of(content)
    if is_plate(content):
        return setup_tools.form_values(form, lists) if all_tests else setup_tools.plate_values(content)
    return setup_tools.form_values(form) if all_tests else tension_values(form)


RUN_BY = re.compile(r"^[^\s-][^\r\n]*$")


def run_by(content: dict[str, Any]) -> str:
    """Who the run is by, as the page names it: the form's Filled in by, else "studio" (the tension screen asks no name)."""
    name = (setup_tools.form_of(content).get("filled_by") or "").strip()
    return name if name and len(name) <= 120 and RUN_BY.match(name) else "studio"


# ----------------------------------------------------------------------------------------------- the steps as they run

class StepRefused(ValueError):
    """A step that cannot be reported: it is the server's, or it has already ended in another state."""


def step_of(steps: list[dict[str, Any]], tool: str) -> dict[str, Any] | None:
    return next((step for step in steps if step["tool"] == tool), None)


def settle(steps: list[dict[str, Any]], tools: tuple[str, ...], state: str, note: str | None = None) -> None:
    """The steps of those tools set to a state, in place."""
    for step in steps:
        if step["tool"] in tools:
            step["state"], step["note"] = state, note if note is None else note[:MAX_NOTE]


def stop_at(steps: list[dict[str, Any]], n: int, note: str | None) -> None:
    """The plan stopped at step n: that step failed with the note, and every step after it that had not ended is skipped."""
    for step in steps:
        if step["n"] == n:
            step["state"], step["note"] = "failed", None if note is None else note[:MAX_NOTE]
        elif step["n"] > n and step["state"] in ("planned", "running"):
            step["state"] = "skipped"


def check_note(checklist: dict[str, Any]) -> str:
    """Why the setup check stops a plan, in the check's own words: its problems, else the items that failed or are missing."""
    lines = [str(problem) for problem in checklist.get("problems") or [] if str(problem).strip()]
    if not lines:
        lines = [f"{item.get('label')}: {item.get('message')}" for item in checklist.get("items") or []
                 if isinstance(item, dict) and item.get("state") in ("fail", "missing")]
    return ("; ".join(lines) or "the setup check did not pass")[:MAX_NOTE]


def plan_state(steps: list[dict[str, Any]]) -> str:
    """A running plan's state from its steps: stopped once one failed, done once each is done or skipped, running until then."""
    if any(step["state"] == "failed" for step in steps):
        return "stopped"
    if all(step["state"] in ("done", "skipped") for step in steps):
        return "done"
    return "running"


def report_step(steps: list[dict[str, Any]], n: int, state: str, note: str | None) -> str:
    """A step the page carries reported (`run`, `qa`, `answer`), in place; the plan's state after it. A failed step stops the plan. The
    same report twice changes nothing; a step that has ended in another state, or one of the server's, is refused."""
    step = next((s for s in steps if s["n"] == n), None)
    if step is None:
        raise LookupError(f"the plan has no step {n}")
    if step["tool"] not in REPORTED:
        raise StepRefused(f"step {n} ({step['tool']}) is the server's to carry out; the page reports {', '.join(REPORTED)}")
    if step["state"] in ("done", "failed", "skipped") and step["state"] != state:
        raise StepRefused(f"step {n} has ended: it is {step['state']}")
    if state == "failed":
        stop_at(steps, n, note)
    else:
        step["state"], step["note"] = state, None if note is None else note[:MAX_NOTE]
    return plan_state(steps)
