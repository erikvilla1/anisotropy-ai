"""A question about a result answered in words (ADR-0102). The page sends the question and the fact sheet of the result it shows, the
numbers our engine computed (`explanation.json`, ADR-0052). The sections of our own theory pages that the question's words find
(`theory.find`) are put beside them, and a model answers from the two in a fixed schema: the answer, the ids of the sections it rests on,
and whether those sections hold the reason asked for. The model writes prose, so the guard here is the explanation's (ADR-0052): the
answer stands only when every number in it is a number of the fact sheet or of the question, at the precision written. The sections are
named by the page from their ids, never by the model, and an id that was not shown is dropped.

With no model nothing is written: the answer names the sections found and the page says where to read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .assistant import _sentences, number_guard
from .theory import Section

SECTIONS_SHOWN = 3  # how many sections a question brings to the model
MAX_ANSWER = 1500  # characters; the model is asked for one to three short sentences


def answer_schema(ids: list[str]) -> dict[str, Any]:
    """The model's answer: its text, the sections it rests on from those shown, and whether they hold the reason."""
    properties: dict[str, Any] = {"answer": {"type": "string"}, "covered": {"type": "boolean"}}
    if ids:  # with no section found there is none to name
        properties["sections"] = {"type": "array", "items": {"type": "string", "enum": list(ids)}}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def answer_view(question: str, facts: dict[str, Any], found: list[Section]) -> dict[str, Any]:
    """What the model may see: the question, the fact sheet as the explanation's writer sees it (no name, note, date or record name), and
    the sections found, each with its id, where it is from and its text."""
    return {"question": question, "facts": facts,
            "sections": [{"id": s.id, "from": s.cited(), "text": s.shown} for s in found]}


@dataclass(frozen=True)
class KeptAnswer:
    prose: tuple[str, ...] = ()
    sources: tuple[Section, ...] = ()
    covered: bool = False
    withheld: bool = False
    reason: str | None = None


def answer_guard(raw: dict[str, Any], question: str, facts: dict[str, Any], found: list[Section]) -> KeptAnswer:
    """What of the model's answer stands. The text is kept only when every number in it is the fact sheet's or the question's; the
    sections are those it named among the ones shown, in the order shown; `covered` needs at least one of them."""
    text = raw.get("answer")
    if not isinstance(text, str) or not text.strip():
        return KeptAnswer(reason="the model's answer held no text")
    if len(text) > MAX_ANSWER:
        return KeptAnswer(withheld=True, reason="the model's answer was longer than an answer here may be")
    guard = number_guard(text, {**facts, "the question": question})
    if not guard.ok:
        return KeptAnswer(withheld=True, reason="the model's answer held numbers that are in neither the results nor the question: " + ", ".join(guard.offending))
    named = raw.get("sections") if isinstance(raw.get("sections"), list) else []
    sources = tuple(s for s in found if s.id in named)
    covered = raw.get("covered") is True and bool(sources)
    return KeptAnswer(prose=_sentences(text), sources=sources if covered else (), covered=covered)
