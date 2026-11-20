"""A question asked in the FEA section before anything is set up, answered in words (ADR-0124). There is no result to read: the sections
of our own theory pages that the question's words find (`theory.find`) go to a model with the question, and it answers in a fixed
schema: the answer, the ids of the sections it rests on, whether they cover the question, and the kind of work the question asks to set
up, from those the page offers, or none. The guard is the why answers' (ADR-0102): the answer stands only when every number in it is the
question's, since there is no fact sheet; a number of the theory pages is said in words. The sections are named by the page from their
ids, and an id or a kind that was not offered is dropped. The page sets nothing up on the model's word: a kind named is offered as a
button.

With no model nothing is written: the page names the sections found.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .assistant import _sentences, number_guard
from .result_answers import MAX_ANSWER
from .theory import Section

# The kinds of FEA work the page may offer to set up, with the words the model reads them by (ADR-0124); the wing is offered since it joined FEA (ADR-0118 amendment 1).
KIND_WORDS = {
    "coupon": "a test coupon (tension, compression, shear or bending; open-hole or unnotched), set up from its material and layup",
    "wing": "a wing: its skins, spars and ribs under flight loads",
}
NONE = "none"


def general_schema(ids: list[str], kinds: list[str]) -> dict[str, Any]:
    """The model's answer: its text, the sections it rests on from those shown, whether they cover the question, and a kind to set up."""
    properties: dict[str, Any] = {"answer": {"type": "string"}, "covered": {"type": "boolean"}}
    if ids:  # with no section found there is none to name
        properties["sections"] = {"type": "array", "items": {"type": "string", "enum": list(ids)}}
    if kinds:
        properties["start"] = {"type": "string", "enum": [*kinds, NONE]}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def general_view(question: str, found: list[Section], kinds: list[str]) -> dict[str, Any]:
    """What the model may see: the question, the sections found, each with its id, where it is from and its text, and the kinds of work
    offered with what each is. Nothing of a model, a result or a person."""
    return {"question": question, "sections": [{"id": s.id, "from": s.cited(), "text": s.shown} for s in found],
            "kinds": [{"id": kind, "is": KIND_WORDS[kind]} for kind in kinds]}


@dataclass(frozen=True)
class KeptGeneral:
    prose: tuple[str, ...] = ()
    sources: tuple[Section, ...] = ()
    covered: bool = False
    withheld: bool = False
    reason: str | None = None
    start: str | None = None


def general_guard(raw: dict[str, Any], question: str, found: list[Section], kinds: list[str]) -> KeptGeneral:
    """What of the model's answer stands. The kind to set up stands when it is one offered, whatever becomes of the text; the text only
    when every number in it is the question's; the sections are those it named among the ones shown; `covered` needs one of them."""
    start = raw.get("start") if raw.get("start") in kinds else None
    text = raw.get("answer")
    if not isinstance(text, str) or not text.strip():
        return KeptGeneral(reason="the model's answer held no text", start=start)
    if len(text) > MAX_ANSWER:
        return KeptGeneral(withheld=True, reason="the model's answer was longer than an answer here may be", start=start)
    guard = number_guard(text, {"the question": question})
    if not guard.ok:
        return KeptGeneral(withheld=True, reason="the model's answer held numbers that are not in the question: " + ", ".join(guard.offending), start=start)
    named = raw.get("sections") if isinstance(raw.get("sections"), list) else []
    sources = tuple(s for s in found if s.id in named)
    covered = raw.get("covered") is True and bool(sources)
    return KeptGeneral(prose=_sentences(text), sources=sources if covered else (), covered=covered, start=start)
