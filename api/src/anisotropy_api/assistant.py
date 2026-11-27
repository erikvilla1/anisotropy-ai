"""The assistant's writers (ADR-0052): one interface, a template that is always on, and a language model behind a setting, with a guard
that keeps every number it writes equal to one the engine computed (ADR-0001). Nothing here computes a result.

The fea package writes a fact sheet beside every solve (`fields.json`'s summary, flattened by `explain.py`) and the template's
sentences from it. The template writer returns those sentences. The Claude writer asks the model to rephrase them for an engineer
from the same fact sheet, then the number guard reads every number in the draft: a number that is not a fact at the precision it was
written withholds the whole draft, and the template's sentences stand instead. A model that does not answer (no network, a
refusal, a rate limit) also leaves the template's sentences, with the reason. The model sees the fact sheet and the sentences, never
a file, a deck or the team's own constants.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Protocol

from .model_costs import ModelCall, measure, sent_fingerprint
from .proposals import UNREAD_REASONS
from .verdict_guard import verdict_guard

NUMBER = re.compile(r"(?<![\w.\-+])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w.])")  # a number on its own, not the digits of a name
PROVIDER_ANTHROPIC = "anthropic"
MAX_TOKENS = 2000
EFFORT = "low"  # every call; its tokens and cost are kept per call (ADR-0120)
FALLBACK_BETA = "server-side-fallback-2026-07-01"  # the "default" fallbacks form routes a declined request by its category
# How every explanation reads (ADR-0091, docs/copy-style-guide.md): the product's own words, no model, vendor or tool named.
VOICE = (
    " Write as the product's own text, short and confident: never mention a language model, AI, a vendor, or a program by name (such as "
    "Abaqus, CalculiX or PrePoMax), and never internal files, scripts, records or people. Call the second solver the reference solver. "
    "Use the symbols σ₁, σ₂ and τ₁₂ for the ply stresses."
)
# What no prose of the model's may say (ADR-0139): the verdict guard sets aside an answer that does, and these words keep that rare.
DECIDES = (
    " Never call a design safe, unsafe, certified or strong enough: the analysis gives a verdict by each criterion, and the engineer "
    "decides."
)
VERDICT = DECIDES + " Say the laminate holds or fails only as the fact sheet's verdict for each criterion says, at the applied loading."
SETUP_SYSTEM = (
    "You explain the setup check of a composite coupon test to the engineer who stated it. You are given the check's items, each passed, "
    "warned, failed, missing or pending, with what the tools found. Write short plain sentences, one per item that needs the engineer's "
    "attention and one summary line first. Quote numbers only as they are written in the items, digit for digit; never compute, convert or "
    "round a number, and never add one. Name the form rows to change. Do not use markdown." + VOICE
)
RESULT_SYSTEM = (
    "You explain the result of a finite element solve of a composite coupon to an engineer. You are given a fact sheet of numbers a "
    "tested engine computed, and sentences a template wrote from it. Write three to six short sentences for an engineer, the verdict first: what the coupon "
    "carries, where it moves and is stressed most, and by each failure criterion whether the laminate holds at the applied loading, which "
    "ply limits it, where, and the physical reason in the mode's words. Every number you write must appear in the fact sheet exactly as "
    "printed there, digit for digit; never compute, convert, round differently, or add a number, a percentage or a ratio that is not in the "
    "sheet. Say nothing the sheet does not support. Do not use markdown." + VOICE + VERDICT
)
LAMINATE_SYSTEM = (
    "You explain the answer to a laminate problem (classical lamination theory) to the engineer or student who stated it. You are given a "
    "fact sheet of numbers a tested engine computed, with the unit of each kind, and sentences a template wrote from it. Write two to "
    "five short sentences: what the stack is, how it deforms under the loads, how stiff it is, and by each failure criterion which ply "
    "fails first, in which mode, at what multiple of the loads. Every number you write must appear in the fact sheet exactly as printed "
    "there, digit for digit; never compute, convert, round differently, or add a number, a percentage or a ratio that is not in the "
    "sheet. Say nothing the sheet does not support. Do not use markdown." + VOICE + DECIDES
)
PROPOSE_MAX_TOKENS = 8000
PROPOSE_SYSTEM = (
    "You read an engineer's message in a composite analysis workspace and propose which of the offered rows it states, so the engineer can "
    "confirm them. You are given the message, the rows on offer (each with its key, label and kind, the unit it is stated in or the dimension "
    "of the units it takes, and for a choice its choices), the conditions on offer, and the rows already filled. Propose a row only when the "
    "message states its value. For each proposal give: the row's key; the value exactly as the message writes it, digit for digit, never "
    "converted, computed, rounded, completed or guessed (a cooling or a drop is a negative change, so you may add a minus sign); the unit "
    "copied exactly as the message writes it beside the value, or null when it writes none; and the quote, the shortest span of the message, "
    "copied character for character, that states the value and its unit. For a choice row the value is one of the row's choice values. For "
    "a notation row the value is the notation as written. For an angle row the value is the ply's angle in degrees. Propose a condition only when the message asks for its physics, quoting the words "
    "that ask. When a value is ambiguous, propose nothing for it and ask one short question; otherwise the question is null. Never propose a "
    "row that is not on offer and never state a value the message does not write. When the message asks for a change you propose nothing "
    "for, list it under unread: the words that ask, copied character for character from the message, and one reason. The reasons: "
    "not_offered, no row or choice on offer covers it; no_value, it names a row on offer but writes no value that row takes (a count of "
    "plies is not a layup's notation); refers_back, it leans on an earlier message, which you were not given. With nothing of the kind, "
    "unread is an empty list." + VOICE
)
# The model's answer: a fixed schema, so the API compiles it once (structured outputs, `output_config.format`).
PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "proposals": {"type": "array", "items": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "value": {"type": "string"}, "unit": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                           "quote": {"type": "string"}},
            "required": ["key", "value", "unit", "quote"], "additionalProperties": False}},
        "conditions": {"type": "array", "items": {
            "type": "object", "properties": {"id": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["id", "quote"], "additionalProperties": False}},
        "question": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        # what the message asks for and the model proposes nothing for (ADR-0088 amendment 1): the engineer's own words and a reason by name
        "unread": {"type": "array", "items": {
            "type": "object", "properties": {"quote": {"type": "string"}, "reason": {"type": "string", "enum": list(UNREAD_REASONS)}},
            "required": ["quote", "reason"], "additionalProperties": False}},
    },
    "required": ["proposals", "conditions", "question", "unread"],
    "additionalProperties": False,
}


# Choosing among fixed tools (ADR-0094, part 8): the model names tools on offer and nothing else, so its answer holds no script, no path
# and no number. The order they run in and whether they can run at all is checked by the tools themselves.
TOOL_CHOICE_MAX_TOKENS = 1000
TOOL_CHOICE_SYSTEM = (
    "You read what an engineer asks for in a composite analysis workspace and choose which of the offered tools to run for it, in order. "
    "You are given the engineer's message, the tools on offer (each with its name and what it does) and the names of the tools whose work "
    "is already done. Choose only tools the message asks for, by name, each at most once, leaving out a tool that is already done. When the "
    "message asks for the whole job, choose every tool that is not done. When it asks for none of them, choose none. You choose names only: "
    "you never write a command, a script, a file name or a number."
)


def tool_choice_schema(names: list[str]) -> dict[str, Any]:
    """The model's answer when it chooses tools: a list of names from those on offer, and no other field."""
    return {"type": "object", "properties": {"tools": {"type": "array", "items": {"type": "string", "enum": list(names)}}},
            "required": ["tools"], "additionalProperties": False}


# A sentence read into a plan of typed tool steps (ADR-0144): the model names tools on offer, regions and rows by name, and copies each
# value as the sentence writes it; the server checks every step, previews the changes with the tools and adds the check and the QA.
PLAN_MAX_TOKENS = 4000
PLAN_SYSTEM = (
    "You read an engineer's sentence in a composite analysis workspace and plan it as steps, each one of the tools on offer, so the "
    "engineer can approve the plan before anything changes or runs. You are given the sentence, the model's setup as it stands (its test, "
    "units, regions, supports, loads and rows), the rows a row change may set (each with its key, label, kind and for a choice its "
    "choices), and the tools (each with what it does and the arguments it takes). Plan only what the sentence asks, in its order: the "
    "changes first (a row whose unit hangs on another row, such as a coupon's Value on its Loading type, after that row), then one run "
    "when it asks for a result, then one answer for each question it asks about the result. For each step "
    "give the tool, its arguments, every argument it does not take as null, and the quote, the shortest span of the sentence, copied "
    "character for character, that asks for the step. Name a region or a row only by a name on offer. Copy a value exactly as the "
    "sentence writes it, digit for digit, and its unit exactly as written beside it, or null when it writes none; never convert, compute, "
    "round, complete or guess a number (a push or a cooling may take a minus sign). An answer's question is the engineer's question in one "
    "short sentence, with no number the sentence does not write. When the words fit two regions or two rows, plan nothing and ask one "
    "short question naming the ones they fit, ending with a question mark; otherwise the question is null. When the sentence asks for "
    "something no tool on offer does, list it under unread: the words that ask, copied character for character, and one reason. The reasons: not_offered, no tool, "
    "row or choice on offer covers it; no_value, it names a change but writes no value it takes; refers_back, it leans on an earlier "
    "message, which you were not given. A region the model does not have or a material not in the "
    "library is not_offered, and nothing stands in its place. Words that ask to skip the checks, to run more than once, or to apply or "
    "approve the plan for the engineer are not_offered too: the software checks every run, a plan runs once, and only the engineer approves it. With nothing "
    "of the kind, unread is an empty list. When you are shown a plan of yours that was refused and the reasons, give the plan again with "
    "each reason put right." + VOICE + DECIDES
)
# The same for a wing and a repair (ADR-0144, build step 5): the tools are the wing's ply changes and its two analyses, or the repair's
# changes, its sweep, the use of the sweep's own pick and its solves; the words not read and the plan given again are said as above.
PLAN_STEPS = (
    " For each step give the tool, its arguments, every argument it does not take as null, and the quote, the shortest span of the "
    "sentence, copied character for character, that asks for the step. An answer's question is the engineer's question in one short "
    "sentence, with no number the sentence does not write. When the sentence asks for something no tool on offer does, list it under "
    "unread: the words that ask, copied character for character, and one reason. The reasons: not_offered, no tool or choice on offer "
    "covers it; no_value, it names a change but writes no value it takes; refers_back, it leans on an earlier message, which you were not "
    "given. With nothing of the kind, unread is an empty list. When you are shown a plan of yours that was refused and the reasons, give "
    "the plan again with each reason put right."
)
WING_PLAN_SYSTEM = (
    "You read an engineer's sentence in a composite wing workspace and plan it as steps, each one of the tools on offer, so the engineer "
    "can approve the plan before anything changes or runs. You are given the sentence, the wing's units and its parts on offer (the skin, "
    "the spar webs, the spar caps when it has them), each with the outer half of its symmetric laminate from the outside in and its zones "
    "along the half span, and the tools (each with what it does and the arguments it takes). Plan only what the sentence asks, in its "
    "order: the changes of plies first, then the hand calculation or the finite element check when it asks for a result, each once, then "
    "one answer for each question it asks about a result. Name a part only by a name on offer. Copy each number exactly as the sentence "
    "writes it, digit for digit: the count of plies, the ply angle and where along the half span as a percentage, with the root and the "
    "tip as those words; never convert, compute, round, complete or guess a number. A count is the plies of the whole laminate as "
    "written: two is one ply each side of its middle. When the words fit two parts, plan nothing and ask one short question naming the "
    "ones they fit; otherwise the question is null." + PLAN_STEPS + VOICE + DECIDES
)
REPAIR_PLAN_SYSTEM = (
    "You read an engineer's sentence in a composite repair workspace, where a stepped patch repair is described, and plan it as steps, "
    "each one of the tools on offer, so the engineer can approve the plan before anything changes or runs. You are given the sentence, the "
    "repair as it stands (its units, whether the patch is flush or bonded on top, its steps and the plies in a step, whether the patch's "
    "plies are listed, and the quantities a change may set with their values as stated) and the tools (each with what it does and the "
    "arguments it takes). Plan only what the sentence asks, in its order: the changes first; a sweep when it asks to try a range of "
    "values, or for the smallest, fewest or shortest repair that stays elastic at a load, and when the sentence names no quantity to "
    "sweep, the step length; then use_pick when it goes on with what the sweep finds, to use it or to solve it; then the solve of the "
    "slice or the bond followed until it lets go, each once, when it asks for them; then one answer for each question it asks about a "
    "result. The pick is the sweep's own: use_pick takes no argument, and no step ever writes the value the sweep picks. Copy each number "
    "exactly as the sentence writes it, digit for digit, and its unit exactly as written beside it, or null when it writes none; never "
    "convert, compute, round, complete or guess a number. When the words fit two quantities, plan nothing and ask one short question "
    "naming the ones they fit; otherwise the question is null." + PLAN_STEPS + VOICE + DECIDES
)


# A loose question about a result, read into a fixed request (ADR-0100): the model names what is asked for from what the page offers and
# writes no number of a result, which it is never shown; the page runs the request on the solver's values.
QUESTION_MAX_TOKENS = 1000
QUESTION_SYSTEM = (
    "You read an engineer's message in a composite analysis workspace, where a solved finite element model of a laminate coupon is on "
    "screen, and say which values of the results the message asks for, so the software can look them up. You never answer the question "
    "yourself and you never write a value of a result: you are shown none. You are given the message, the quantities on offer (each with "
    "its key and what it is), the plies numbered from the bottom face with their fibre angles, the regions on offer, and whether an element "
    "is clicked on the model. Answer with: kind, 'values' to read quantities at one element, 'extreme' to find where a quantity is largest "
    "or smallest over a region, 'failure' when the message asks which ply or layer fails, breaks or goes first, whether or when the coupon "
    "fails or holds, or the load, factor or strength ratio at first-ply failure (the software then shows its own failure answer; leave "
    "quantities and plies empty, element null, here false, sense null and region 'default'), or 'none' when the message states or changes "
    "the setup, asks to run or check, or is not about the results; "
    "quantities, the keys asked for (a plain 'stress' is the three ply stresses S11, S22 and S12, a plain 'strain' the three ply strains; "
    "how much load a ply carries is its stress along the fibres); plies, the ply numbers asked about, read from a number, an angle or a "
    "position such as the outer plies, and empty for every ply; element, the element's number only when the message writes it, else null; "
    "here, true when the message points at the clicked element ('here', 'this element') and no number is written; sense, for an extreme, "
    "'largest' for the most tensile value, 'smallest' for the most compressive, 'magnitude' for the largest regardless of sign, else null; "
    "region, 'default' unless the message names the gauge section or the whole model. Use 'values' only when an element is named or "
    "clicked; a question about plies in general, a comparison of plies with no element, or a question of why a ply is loaded as it is, is "
    "an 'extreme' over the plies and quantities it concerns, so the engineer sees the values; a question of which ply fails is never "
    "an 'extreme'. When the message is about the results but "
    "too unclear to read, use 'none' and ask one short question; otherwise the question is null. Read through typing mistakes." + VOICE
)


# A question about a result answered in words (ADR-0102): the model is shown the result's fact sheet and the sections of our theory pages
# the question found, and answers in a schema; the number guard then reads the answer, and the page names the sections.
ANSWER_MAX_TOKENS = 1500
ANSWER_SYSTEM = (
    "You answer an engineer's question about the result of a finite element solve of a composite laminate coupon. You are given the "
    "question, a fact sheet of numbers a tested engine computed for this result, and sections of the product's own theory pages, each "
    "with an id. Answer in at most three short, plain sentences of at most 25 words each, from the fact sheet and the sections alone. The "
    "first sentence is the answer on its own in at most nine words, as an engineer would say it to a colleague, and the page shows it as "
    "the heading; the others give only the one or two facts that "
    "make it so. Nothing restates the question, and a quantity is named in words, its symbol only beside them (the stress across the "
    "fibres, σ₂). The sheet says "
    "what happened in this result, and the sections say why. Every number you write must appear in the fact sheet or in the question "
    "exactly as printed there, digit for digit; never compute, convert, round differently, or add a number, a percentage or a ratio, "
    "and never copy a number or an equation out of a section: say in words what it means. Do not name or number a section in the "
    "answer; list in 'sections' the ids of those your answer rests on, and the page names them. Set 'covered' to true only when those "
    "sections hold the reason or the meaning asked for. When they do not, set it to false, say what the fact sheet shows about the "
    "matter and that the theory pages do not explain it yet, and give no reason of your own. When the question is not about this "
    "result or its theory, set 'covered' to false and say in one sentence what can be asked here. Do not use markdown." + VOICE + VERDICT
)


# A question asked in the FEA section before anything is set up (ADR-0124), or of a coupon with no result yet (ADR-0121 amendment 5): no
# result, so the model is shown the sections of our theory pages the question found and the kinds of work the page offers; the number
# guard then reads the answer against the question alone.
GENERAL_SYSTEM = (
    "You answer an engineer's question in the finite element section of a composite analysis workspace, before any model is set up. You "
    "are given the question, sections of the product's own theory pages, each with an id, and the kinds of work the workspace can set up. "
    "Answer in one to three short, plain sentences, the first the answer on its own in at most eight words and 60 characters, as an "
    "engineer would say it to a colleague, and nothing that restates the question, from the sections alone, "
    "and only what was asked: leave out the grips, tabs, meshes or checks of a section unless the question is about them. Never write the "
    "word engine: say the analysis or the laminate calculation. "
    "Write no number that is not in the question, digit for digit, and never copy a number or an equation out of a section: say in words "
    "what it means; a ply may be named by its angle, as the 90-degree ply. Do not name or number a section in the answer; list in 'sections' the ids of those your answer rests on, and the page "
    "names them. Set 'covered' to true only when those sections answer the question. When they do not, set it to false, say in one "
    "sentence that the theory pages do not cover it yet, and give no answer of your own. Set 'start' to the kind of work the engineer "
    "asks to set up or to analyse, when the question asks for one of those offered, and to 'none' otherwise. Do not use markdown." + VOICE + DECIDES
)


@dataclass(frozen=True)
class Reading:
    """What a writer read from a message (ADR-0088): the model's answer as parsed, before the source guard; None when no model read it,
    with the reason when one was asked."""

    raw: dict[str, Any] | None
    writer: str
    model: str | None
    reason: str | None = None
    call: ModelCall | None = None  # what the call to the model was billed for (ADR-0120); None when no model was called


@dataclass(frozen=True)
class Draft:
    """What a writer gave: the prose as sentences, who wrote it, and when the model's draft was set aside, why."""

    prose: tuple[str, ...]
    writer: str  # "template" or the provider's name
    model: str | None
    withheld: bool = False  # the model's draft held a number not in the facts; the template's prose stands
    reason: str | None = None  # why the template's prose stands when the model was asked: withheld, no answer, a refusal
    offending: tuple[str, ...] = ()
    call: ModelCall | None = None  # what the call to the model was billed for, kept or not (ADR-0120); None when no model was called


@dataclass(frozen=True)
class Guard:
    ok: bool
    offending: tuple[str, ...] = ()


class Assistant(Protocol):
    """One interface for every writer (ADR-0027 item 2)."""

    name: str

    def explain_setup(self, checklist: dict[str, Any], template: list[str]) -> Draft: ...

    def explain_result(self, facts: dict[str, Any], template: list[str]) -> Draft: ...

    def explain_laminate(self, facts: dict[str, Any], template: list[str]) -> Draft: ...

    def propose(self, view: dict[str, Any], schema: dict[str, Any] | None = None, system: str = "") -> Reading: ...

    def choose_tools(self, view: dict[str, Any]) -> Reading: ...

    def read_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading: ...

    def answer_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading: ...

    def answer_general(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading: ...

    def plan(self, view: dict[str, Any], schema: dict[str, Any], system: str | None = None) -> Reading: ...


def numbers_in(text: str) -> list[str]:
    return NUMBER.findall(text)


def _tolerance(token: str) -> float:
    """Half the unit of the token's last written digit: 0.5 for "16211", 0.005 for "0.31", a relative half-unit for "1.62e+04"."""
    mantissa, _, exponent = token.lower().partition("e")
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    scale = 10.0 ** int(exponent) if exponent else 1.0
    return 0.5 * 10.0 ** (-decimals) * scale


def fact_numbers(facts: dict[str, Any]) -> list[float]:
    """Every number the facts hold, lists included; booleans are not numbers."""
    out: list[float] = []
    for value in facts.values():
        for v in (value if isinstance(value, (list, tuple)) else [value]):
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)) and math.isfinite(v):
                out.append(float(v))
            elif isinstance(v, str):
                out.extend(float(t) for t in numbers_in(v) if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", t))
    return out


def number_guard(prose: str, facts: dict[str, Any]) -> Guard:
    """Every number written in the prose equals a fact at the precision it was written; else the offending tokens."""
    values = fact_numbers(facts)
    offending = []
    for token in numbers_in(prose):
        try:
            written = float(token)
        except ValueError:
            offending.append(token)
            continue
        allowed = _tolerance(token)
        if not any(abs(written - value) <= allowed + 1e-12 * abs(value) for value in values):
            offending.append(token)
    return Guard(not offending, tuple(dict.fromkeys(offending)))


def model_view_of_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    """What the model may see of a checklist: the items' ids, labels, states, rows and messages, the material's source cut to its kind
    (a library record, or the engineer's own constants, in the words of before or after ADR-0091 amendment 2) so a source the team or
    the customer named stays with the coupon (R-11). The coupon's record name is left out, so the model cannot write it (audit fea-run-8)."""
    items = []
    for item in checklist.get("items", []):
        message = str(item.get("message", ""))
        if item.get("id") == "material":
            message = re.sub(r"(the team's|your) own constants(?:: |, from ).*?(;|$)", r"\1 own constants\2", message)
        items.append({"id": item.get("id"), "label": item.get("label"), "state": item.get("state"), "message": message, "rows": list(item.get("rows", []))})
    return {"state": checklist.get("state"), "items": items}


def model_view_of_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """What the model may see of a fact sheet: every fact but the notes and names the form carries (the sheet holds none today; the rule
    is stated so a later fact does not slip through), and not the coupon's record name, which the page never shows (audit fea-run-8)."""
    return {key: value for key, value in facts.items() if key not in ("filled_by", "notes", "date", "designation")}


class TemplateAssistant:
    """The fea package's sentences, as written: never wrong about a number, always available."""

    name = "template"

    def explain_setup(self, checklist: dict[str, Any], template: list[str]) -> Draft:
        return Draft(tuple(template), "template", None)

    def explain_result(self, facts: dict[str, Any], template: list[str]) -> Draft:
        return Draft(tuple(template), "template", None)

    def explain_laminate(self, facts: dict[str, Any], template: list[str]) -> Draft:
        return Draft(tuple(template), "template", None)

    def propose(self, view: dict[str, Any], schema: dict[str, Any] | None = None, system: str = "") -> Reading:
        """The template reads nothing: the page's own patterns read the message (ADR-0055)."""
        return Reading(None, "template", None)

    def choose_tools(self, view: dict[str, Any]) -> Reading:
        """The template reads no message, so it chooses nothing: the caller takes the tools' own order."""
        return Reading(None, "template", None)

    def read_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        """The template reads nothing: the page's own patterns read a question about a result (ADR-0099)."""
        return Reading(None, "template", None)

    def answer_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        """The template writes no answer to a question: the page names the theory sections found (ADR-0102)."""
        return Reading(None, "template", None)

    def answer_general(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        """The template writes no answer to a question asked before a setup either: the page names the sections found (ADR-0124)."""
        return Reading(None, "template", None)

    def plan(self, view: dict[str, Any], schema: dict[str, Any], system: str | None = None) -> Reading:
        """The template plans nothing: the plan is `unavailable` and the page reads the sentence with its patterns (ADR-0144)."""
        return Reading(None, "template", None)


# The models the real-model Assistant check (ADR-0121, check 2) has been run with over every bank, by id, with the run (ADR-0121
# amendment 8). A model joins only by pull request, after a run with it (the workflow's `model` input) fails no more answers than the
# listed run of the model it replaces, and a person has read its report. Another model may still be set on the site; the page is told it
# is unchecked (/v1/workspace/assistant) and the check after a deploy fails until it is listed or set back.
CHECKED_MODELS: dict[str, str] = {
    "claude-opus-5-5": "run 44671161192, 2026-11-20: 95 answers graded, 64 hold, 26 weak, 5 fail (ADR-0121 amendment 7)",
}

# Why the model was not asked (ADR-0139): the person's calls today reached the day's cap. The page shows its own fixed words for it, by
# this sentence (lib/studio-api.ts, DAILY_LIMIT_REASON), and reads with its patterns until midnight UTC.
DAILY_LIMIT_REASON = "the day's limit of free-text readings for this sign-in is reached"


class LimitedAssistant(TemplateAssistant):
    """The writer of a person who has reached the day's cap on calls to the model (ADR-0139): the template's, which calls nothing, with
    the reason the page reads. Nothing is billed, so nothing is recorded in model_calls."""

    def __init__(self, cap: int):
        self.cap = cap

    def _draft(self, template: list[str]) -> Draft:
        return Draft(tuple(template), "template", None, reason=DAILY_LIMIT_REASON)

    def _reading(self) -> Reading:
        return Reading(None, "template", None, DAILY_LIMIT_REASON)

    def explain_setup(self, checklist: dict[str, Any], template: list[str]) -> Draft:
        return self._draft(template)

    def explain_result(self, facts: dict[str, Any], template: list[str]) -> Draft:
        return self._draft(template)

    def explain_laminate(self, facts: dict[str, Any], template: list[str]) -> Draft:
        return self._draft(template)

    def propose(self, view: dict[str, Any], schema: dict[str, Any] | None = None, system: str = "") -> Reading:
        return self._reading()

    def choose_tools(self, view: dict[str, Any]) -> Reading:
        return self._reading()

    def read_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        return self._reading()

    def answer_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        return self._reading()

    def answer_general(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        return self._reading()

    def plan(self, view: dict[str, Any], schema: dict[str, Any], system: str | None = None) -> Reading:
        return self._reading()


def _sentences(text: str) -> tuple[str, ...]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if p.strip()]
    return tuple(parts)


class ClaudeAssistant:
    """Claude, through the Anthropic SDK, behind the setting (ADR-0027); its draft stands only when the number guard passes."""

    name = PROVIDER_ANTHROPIC

    def __init__(self, model: str, client: Any | None = None, client_factory: Callable[[], Any] | None = None):
        self.model = model
        self._client = client
        self._factory = client_factory

    @property
    def client(self) -> Any:
        if self._client is None:
            if self._factory is not None:
                self._client = self._factory()
            else:
                import anthropic  # imported here: with the assistant off, the SDK is never loaded and nothing can call out

                self._client = anthropic.Anthropic()
        return self._client

    def _ask(self, feature: str, system: str, user: str, schema: dict[str, Any] | None = None,
             max_tokens: int = MAX_TOKENS) -> tuple[str | None, str | None, ModelCall | None]:
        """The model's text, or None with the reason it gave none; with a schema, the text is JSON in that schema (structured outputs).
        Third, what the call was billed for (ADR-0120), whatever became of its answer; None when no answer came back to bill."""
        import anthropic

        output_config: dict[str, Any] = {"effort": EFFORT}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        started = time.monotonic()
        try:
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=max_tokens, system=system, output_config=output_config,
                betas=[FALLBACK_BETA], fallbacks="default", messages=[{"role": "user", "content": user}],
            )
        except anthropic.AuthenticationError as exc:
            return None, f"the model's credential was refused: {exc.message}", None
        except anthropic.RateLimitError:
            return None, "the model is rate limited; the template's prose stands", None
        except anthropic.APIStatusError as exc:
            return None, f"the model answered with an error ({exc.status_code}): {exc.message}", None
        except anthropic.APIConnectionError:
            return None, "the model could not be reached; the template's prose stands", None
        answer = "".join(block.text for block in response.content or [] if getattr(block, "type", "") == "text")
        call = measure(feature, self.model, EFFORT, response, answer, time.monotonic() - started)
        if call is not None:
            call = replace(call, sent_sha256=sent_fingerprint(system, user, schema))
        if response.stop_reason == "refusal":
            return None, "the model declined the request; the template's prose stands", call
        if response.stop_reason == "max_tokens":
            return None, "the model's answer was cut short; the template's prose stands", call
        text = answer.strip()
        if not text:
            return None, "the model answered with no text; the template's prose stands", call
        return text, None, call

    def _draft(self, feature: str, system: str, user: str, facts: dict[str, Any], template: list[str]) -> Draft:
        text, reason, call = self._ask(feature, system, user)
        if text is None:
            return Draft(tuple(template), "template", None, reason=reason, call=call)
        guard = number_guard(text, facts)
        if not guard.ok:
            return Draft(tuple(template), "template", None, withheld=True, offending=guard.offending,
                         reason="the model's draft held numbers that are not in the fact sheet: " + ", ".join(guard.offending), call=call)
        words = verdict_guard(text, facts)  # and no word against the engine's verdict, none deciding for the engineer (ADR-0139)
        if not words.ok:
            return Draft(tuple(template), "template", None, withheld=True, offending=words.offending, reason=words.reason, call=call)
        return Draft(_sentences(text), self.name, self.model, call=call)

    def explain_setup(self, checklist: dict[str, Any], template: list[str]) -> Draft:
        view = model_view_of_checklist(checklist)
        user = "The setup check:\n" + json.dumps(view, ensure_ascii=False, indent=1) + "\n\nThe template's sentences:\n" + "\n".join(template)
        facts = {"items": [item["message"] for item in view["items"]] + [row for item in view["items"] for row in item["rows"]]}
        return self._draft("explain_setup", SETUP_SYSTEM, user, facts, template)

    def explain_result(self, facts: dict[str, Any], template: list[str]) -> Draft:
        view = model_view_of_facts(facts)
        user = "The fact sheet:\n" + json.dumps(view, ensure_ascii=False, indent=1) + "\n\nThe template's sentences:\n" + "\n".join(template)
        return self._draft("explain_result", RESULT_SYSTEM, user, view, template)

    def explain_laminate(self, facts: dict[str, Any], template: list[str]) -> Draft:
        """A laminate problem's answer (ADR-0060): the fact sheet is the API's, in the reporting units, and the guard reads it as any other."""
        view = model_view_of_facts(facts)
        user = "The fact sheet:\n" + json.dumps(view, ensure_ascii=False, indent=1) + "\n\nThe template's sentences:\n" + "\n".join(template)
        return self._draft("explain_laminate", LAMINATE_SYSTEM, user, view, template)

    def _read(self, feature: str, system: str, view: dict[str, Any], schema: dict[str, Any], max_tokens: int) -> Reading:
        """The model's answer to a view, as JSON in the schema asked for and not yet judged; none, with the reason, when it gave none."""
        text, reason, call = self._ask(feature, system, json.dumps(view, ensure_ascii=False, indent=1), schema=schema, max_tokens=max_tokens)
        if text is None:
            return Reading(None, "template", None, (reason or "the model gave no answer").replace("; the template's prose stands", ""), call=call)
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return Reading(None, "template", None, "the model's answer was not the JSON asked for", call=call)
        if not isinstance(raw, dict):
            return Reading(None, "template", None, "the model's answer was not the JSON asked for", call=call)
        return Reading(raw, self.name, self.model, call=call)

    def propose(self, view: dict[str, Any], schema: dict[str, Any] | None = None, system: str = "") -> Reading:
        """The model's reading of a message (ADR-0088): proposals in the fixed schema, which the source guard then reads. `view` is what the
        model may see: the message, the rows and conditions on offer, and the filled rows with no name, note or source (R-11). A plate
        passes its own schema and instructions, the rows' with its supports and loads added (ADR-0101)."""
        return self._read("propose_changes", PROPOSE_SYSTEM + system, view, schema or PROPOSAL_SCHEMA, PROPOSE_MAX_TOKENS)

    def read_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        """The model's reading of a question about a result (ADR-0100), in a schema of names on offer and whole numbers, which the guard
        then reads. `view` is what the model may see: the message, the quantities, plies and regions on offer; never a result."""
        return self._read("read_question", QUESTION_SYSTEM, view, schema, QUESTION_MAX_TOKENS)

    def answer_question(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        """The model's answer to a question about a result (ADR-0102), as JSON in the schema asked for and not yet judged: the number guard
        reads its text. `view` is what the model may see: the question, the result's fact sheet and the theory sections found."""
        return self._read("answer_question", ANSWER_SYSTEM, view, schema, ANSWER_MAX_TOKENS)

    def answer_general(self, view: dict[str, Any], schema: dict[str, Any]) -> Reading:
        """The model's answer to a question asked in the FEA section before a setup (ADR-0124), as JSON in the schema asked for and not
        yet judged. `view` is the question, the theory sections found and the kinds of work offered. Billed as `answer_question`, the
        one feature for questions answered from the theory pages (ADR-0120)."""
        return self._read("answer_question", GENERAL_SYSTEM, view, schema, ANSWER_MAX_TOKENS)

    def plan(self, view: dict[str, Any], schema: dict[str, Any], system: str | None = None) -> Reading:
        """The model's plan for a sentence (ADR-0144), as JSON in the schema asked for and not yet judged: the planner's checks read it.
        `view` is what the model may see: the sentence, the setup as `read_setup` reads it, the rows and the tools on offer; with a plan
        it gave that was refused, that plan and the reasons. Never a name, a note, an email or another project (R-11). A wing's or a
        repair's plan passes its own instructions (`WING_PLAN_SYSTEM`, `REPAIR_PLAN_SYSTEM`) and its own view of the wing or the repair."""
        return self._read("plan_steps", system or PLAN_SYSTEM, view, schema, PLAN_MAX_TOKENS)

    def choose_tools(self, view: dict[str, Any]) -> Reading:
        """The model's choice among the tools on offer (ADR-0094, part 8), in a schema that holds their names and nothing else. `view` is
        what the model may see: the message, each tool's name and description, and the names of those already done."""
        names = [str(tool["name"]) for tool in view.get("tools", [])]
        return self._read("choose_tools", TOOL_CHOICE_SYSTEM, view, tool_choice_schema(names), TOOL_CHOICE_MAX_TOKENS)


def assistant_for(provider: str | None, model: str | None) -> Assistant:
    """The writer the settings name: the template when the assistant is off."""
    if provider is None:
        return TemplateAssistant()
    if provider == PROVIDER_ANTHROPIC:
        return ClaudeAssistant(model or "")
    raise ValueError(f"unknown assistant provider {provider!r}")
