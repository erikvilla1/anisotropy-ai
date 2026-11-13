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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

NUMBER = re.compile(r"(?<![\w.\-+])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w.])")  # a number on its own, not the digits of a name
PROVIDER_ANTHROPIC = "anthropic"
MAX_TOKENS = 2000
FALLBACK_BETA = "server-side-fallback-2026-07-01"  # the "default" fallbacks form routes a declined request by its category
# How every explanation reads (ADR-0091, docs/copy-style-guide.md): the product's own words, no model, vendor or tool named.
VOICE = (
    " Write as the product's own text, short and confident: never mention a language model, AI, a vendor, or a program by name (such as "
    "Abaqus, CalculiX or PrePoMax), and never internal files, scripts, records or people. Call the second solver the reference solver. "
    "Use the symbols σ₁, σ₂ and τ₁₂ for the ply stresses."
)
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
    "sheet. Say nothing the sheet does not support. Do not use markdown." + VOICE
)
LAMINATE_SYSTEM = (
    "You explain the answer to a laminate problem (classical lamination theory) to the engineer or student who stated it. You are given a "
    "fact sheet of numbers a tested engine computed, with the unit of each kind, and sentences a template wrote from it. Write two to "
    "five short sentences: what the stack is, how it deforms under the loads, how stiff it is, and by each failure criterion which ply "
    "fails first, in which mode, at what multiple of the loads. Every number you write must appear in the fact sheet exactly as printed "
    "there, digit for digit; never compute, convert, round differently, or add a number, a percentage or a ratio that is not in the "
    "sheet. Say nothing the sheet does not support. Do not use markdown." + VOICE
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
    "a notation row the value is the notation as written. Propose a condition only when the message asks for its physics, quoting the words "
    "that ask. When a value is ambiguous, propose nothing for it and ask one short question; otherwise the question is null. Never propose a "
    "row that is not on offer and never state a value the message does not write." + VOICE
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
    },
    "required": ["proposals", "conditions", "question"],
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


@dataclass(frozen=True)
class Reading:
    """What a writer read from a message (ADR-0088): the model's answer as parsed, before the source guard; None when no model read it,
    with the reason when one was asked."""

    raw: dict[str, Any] | None
    writer: str
    model: str | None
    reason: str | None = None


@dataclass(frozen=True)
class Draft:
    """What a writer gave: the prose as sentences, who wrote it, and when the model's draft was set aside, why."""

    prose: tuple[str, ...]
    writer: str  # "template" or the provider's name
    model: str | None
    withheld: bool = False  # the model's draft held a number not in the facts; the template's prose stands
    reason: str | None = None  # why the template's prose stands when the model was asked: withheld, no answer, a refusal
    offending: tuple[str, ...] = ()


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

    def propose(self, view: dict[str, Any]) -> Reading: ...

    def choose_tools(self, view: dict[str, Any]) -> Reading: ...


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
    (a library record, or the team's own constants) so a source the team named stays with the coupon (R-11)."""
    items = []
    for item in checklist.get("items", []):
        message = str(item.get("message", ""))
        if item.get("id") == "material":
            message = re.sub(r"the team's own constants: .*?(;|$)", r"the team's own constants\1", message)
        items.append({"id": item.get("id"), "label": item.get("label"), "state": item.get("state"), "message": message, "rows": list(item.get("rows", []))})
    return {"state": checklist.get("state"), "designation": checklist.get("designation"), "items": items}


def model_view_of_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """What the model may see of a fact sheet: every fact but the notes and names the form carries (the sheet holds none today; the rule
    is stated so a later fact does not slip through)."""
    return {key: value for key, value in facts.items() if key not in ("filled_by", "notes", "date")}


class TemplateAssistant:
    """The fea package's sentences, as written: never wrong about a number, always available."""

    name = "template"

    def explain_setup(self, checklist: dict[str, Any], template: list[str]) -> Draft:
        return Draft(tuple(template), "template", None)

    def explain_result(self, facts: dict[str, Any], template: list[str]) -> Draft:
        return Draft(tuple(template), "template", None)

    def explain_laminate(self, facts: dict[str, Any], template: list[str]) -> Draft:
        return Draft(tuple(template), "template", None)

    def propose(self, view: dict[str, Any]) -> Reading:
        """The template reads nothing: the page's own patterns read the message (ADR-0055)."""
        return Reading(None, "template", None)

    def choose_tools(self, view: dict[str, Any]) -> Reading:
        """The template reads no message, so it chooses nothing: the caller takes the tools' own order."""
        return Reading(None, "template", None)


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

    def _ask(self, system: str, user: str, schema: dict[str, Any] | None = None, max_tokens: int = MAX_TOKENS) -> tuple[str | None, str | None]:
        """The model's text, or None with the reason it gave none; with a schema, the text is JSON in that schema (structured outputs)."""
        import anthropic

        output_config: dict[str, Any] = {"effort": "low"}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        try:
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=max_tokens, system=system, output_config=output_config,
                betas=[FALLBACK_BETA], fallbacks="default", messages=[{"role": "user", "content": user}],
            )
        except anthropic.AuthenticationError as exc:
            return None, f"the model's credential was refused: {exc.message}"
        except anthropic.RateLimitError:
            return None, "the model is rate limited; the template's prose stands"
        except anthropic.APIStatusError as exc:
            return None, f"the model answered with an error ({exc.status_code}): {exc.message}"
        except anthropic.APIConnectionError:
            return None, "the model could not be reached; the template's prose stands"
        if response.stop_reason == "refusal":
            return None, "the model declined the request; the template's prose stands"
        if response.stop_reason == "max_tokens":
            return None, "the model's answer was cut short; the template's prose stands"
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()
        if not text:
            return None, "the model answered with no text; the template's prose stands"
        return text, None

    def _draft(self, system: str, user: str, facts: dict[str, Any], template: list[str]) -> Draft:
        text, reason = self._ask(system, user)
        if text is None:
            return Draft(tuple(template), "template", None, reason=reason)
        guard = number_guard(text, facts)
        if not guard.ok:
            return Draft(tuple(template), "template", None, withheld=True, offending=guard.offending,
                         reason="the model's draft held numbers that are not in the fact sheet: " + ", ".join(guard.offending))
        return Draft(_sentences(text), self.name, self.model)

    def explain_setup(self, checklist: dict[str, Any], template: list[str]) -> Draft:
        view = model_view_of_checklist(checklist)
        user = "The setup check:\n" + json.dumps(view, ensure_ascii=False, indent=1) + "\n\nThe template's sentences:\n" + "\n".join(template)
        facts = {"items": [item["message"] for item in view["items"]] + [row for item in view["items"] for row in item["rows"]]}
        return self._draft(SETUP_SYSTEM, user, facts, template)

    def explain_result(self, facts: dict[str, Any], template: list[str]) -> Draft:
        view = model_view_of_facts(facts)
        user = "The fact sheet:\n" + json.dumps(view, ensure_ascii=False, indent=1) + "\n\nThe template's sentences:\n" + "\n".join(template)
        return self._draft(RESULT_SYSTEM, user, view, template)

    def explain_laminate(self, facts: dict[str, Any], template: list[str]) -> Draft:
        """A laminate problem's answer (ADR-0060): the fact sheet is the API's, in the reporting units, and the guard reads it as any other."""
        view = model_view_of_facts(facts)
        user = "The fact sheet:\n" + json.dumps(view, ensure_ascii=False, indent=1) + "\n\nThe template's sentences:\n" + "\n".join(template)
        return self._draft(LAMINATE_SYSTEM, user, view, template)

    def propose(self, view: dict[str, Any]) -> Reading:
        """The model's reading of a message (ADR-0088): proposals in the fixed schema, which the source guard then reads. `view` is what the
        model may see: the message, the rows and conditions on offer, and the filled rows with no name, note or source (R-11)."""
        text, reason = self._ask(PROPOSE_SYSTEM, json.dumps(view, ensure_ascii=False, indent=1), schema=PROPOSAL_SCHEMA, max_tokens=PROPOSE_MAX_TOKENS)
        if text is None:
            return Reading(None, "template", None, (reason or "the model gave no answer").replace("; the template's prose stands", ""))
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return Reading(None, "template", None, "the model's answer was not the JSON asked for")
        if not isinstance(raw, dict):
            return Reading(None, "template", None, "the model's answer was not the JSON asked for")
        return Reading(raw, self.name, self.model)

    def choose_tools(self, view: dict[str, Any]) -> Reading:
        """The model's choice among the tools on offer (ADR-0094, part 8), in a schema that holds their names and nothing else. `view` is
        what the model may see: the message, each tool's name and description, and the names of those already done."""
        names = [str(tool["name"]) for tool in view.get("tools", [])]
        text, reason = self._ask(TOOL_CHOICE_SYSTEM, json.dumps(view, ensure_ascii=False, indent=1), schema=tool_choice_schema(names),
                                 max_tokens=TOOL_CHOICE_MAX_TOKENS)
        if text is None:
            return Reading(None, "template", None, (reason or "the model gave no answer").replace("; the template's prose stands", ""))
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return Reading(None, "template", None, "the model's answer was not the JSON asked for")
        if not isinstance(raw, dict):
            return Reading(None, "template", None, "the model's answer was not the JSON asked for")
        return Reading(raw, self.name, self.model)


def assistant_for(provider: str | None, model: str | None) -> Assistant:
    """The writer the settings name: the template when the assistant is off."""
    if provider is None:
        return TemplateAssistant()
    if provider == PROVIDER_ANTHROPIC:
        return ClaudeAssistant(model or "")
    raise ValueError(f"unknown assistant provider {provider!r}")
