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
SETUP_SYSTEM = (
    "You explain the setup check of a composite coupon test to the engineer who stated it. You are given the check's items, each passed, "
    "warned, failed, missing or pending, with what the tools found. Write short plain sentences, one per item that needs the engineer's "
    "attention and one summary line first. Quote numbers only as they are written in the items, digit for digit; never compute, convert or "
    "round a number, and never add one. Name the form rows to change. Do not use markdown."
)
RESULT_SYSTEM = (
    "You explain the result of a finite element solve of a composite coupon to an engineer. You are given a fact sheet of numbers a "
    "tested engine computed, and sentences a template wrote from it. Write four to eight plain sentences for an engineer: what the coupon "
    "carries, where it moves and is stressed most, and by each failure criterion whether the laminate holds at the applied loading, which "
    "ply limits it, where, and the physical reason in the mode's words. Every number you write must appear in the fact sheet exactly as "
    "printed there, digit for digit; never compute, convert, round differently, or add a number, a percentage or a ratio that is not in the "
    "sheet. Say nothing the sheet does not support. Do not use markdown."
)


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

    def _ask(self, system: str, user: str) -> tuple[str | None, str | None]:
        """The model's text, or None with the reason it gave none."""
        import anthropic

        try:
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=MAX_TOKENS, system=system, output_config={"effort": "low"},
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


def assistant_for(provider: str | None, model: str | None) -> Assistant:
    """The writer the settings name: the template when the assistant is off."""
    if provider is None:
        return TemplateAssistant()
    if provider == PROVIDER_ANTHROPIC:
        return ClaudeAssistant(model or "")
    raise ValueError(f"unknown assistant provider {provider!r}")
