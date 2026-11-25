"""What a model's words may say of whether the part holds (ADR-0139). The number guard (ADR-0052) keeps every number a model writes equal
to one the engine computed; it reads no word, so an answer could say "the laminate holds" beside the engine's "fails" with no wrong
number in it, or call a design safe, which no analysis here decides. This guard reads the words, sentence by sentence, and sets the
whole answer aside when:

- it calls something safe, unsafe, airworthy, certified, "strong enough", "good to go" or signed off: the engine gives a verdict per
  criterion at the applied loading and the engineer decides; the product never does;
- it says the laminate or coupon holds (survives, does not fail) while the engine says a criterion fails at the applied loading, or
  says it fails while the engine says every criterion holds. A sentence that names a criterion is held to that criterion's verdict alone;
  a sentence that names none is held to all of them. A sentence that only supposes ("would", "if"), or places the failure at a multiple
  of the loading ("fails at 1.032 times the applied loading", "fails first in ply 4"), states no verdict at the applied loading and stands.

The verdicts are the fact sheet's own (`<criterion>_fails`, written by the fea package's `explain.py`). A fact sheet without them (a
setup check, a laminate problem, a question asked before anything is solved) is read for the first rule alone. Nothing here computes a
result. It is deliberately narrow: what it does not recognise stands, so a good answer is not set aside for its wording.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Words that decide for the engineer whether a design may be used: never the product's to say (ADR-0139).
APPROVAL = re.compile(
    r"\b(?:un)?safe(?:ly)?\b|\bairworthy\b|\bcertified\b|\bstrong enough\b|\bgood to go\b|\bsign(?:ed|s)?[- ]off\b",
    re.IGNORECASE)
# What a sentence's claim is about: the part as a whole, not a ply or a grip.
SUBJECT = r"(?:laminate|coupon|specimen|part|design|panel|plate|structure|it)"
_GAP = r"[^.;:!?]{0,40}?"  # the claim's verb within a few words of its subject, in the same clause
HOLDS = re.compile(
    rf"\b{SUBJECT}\b{_GAP}\b(?:holds|survives|withstands|does not fail|doesn't fail|does not break|doesn't break|will not fail|won't fail"
    rf"|is not going to fail|carries the applied (?:load|loading))\b"
    r"|\b(?:no ply|none of the plies|nothing) (?:fails|breaks)\b",
    re.IGNORECASE)
FAILS = re.compile(
    rf"\b{SUBJECT}\b{_GAP}\b(?:fails|breaks|ruptures|does not hold|doesn't hold|will fail|will break|cannot carry|can't carry"
    r"|does not survive|doesn't survive)\b"
    r"|\b(?:every|each) ply fails\b",
    re.IGNORECASE)
# A sentence that supposes states no verdict; one that places the failure at a multiple of the loading, or names the first ply to go,
# describes when it would fail, which a laminate that holds also has.
SUPPOSES = re.compile(r"\b(?:would|if|were|unless|could|might)\b", re.IGNORECASE)
PLACES_FAILURE = re.compile(r"\b(?:times|factor|first|once|beyond|above|until|when|before)\b|×|\bat (?:a|an|\d)", re.IGNORECASE)
# How a sentence names a criterion, by the fact sheet's keys (fea/src/anisotropy_fea/audit.py, CRITERION).
CRITERION_WORDS = {
    "max_stress": re.compile(r"\bmax(?:imum)?[- ]stress\b", re.IGNORECASE),
    "max_strain": re.compile(r"\bmax(?:imum)?[- ]strain\b", re.IGNORECASE),
    "tsai_hill": re.compile(r"\btsai[- ]hill\b", re.IGNORECASE),
    "tsai_wu": re.compile(r"\btsai[- ]wu\b", re.IGNORECASE),
}
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
# A sentence may set two criteria side by side ("holds by maximum stress but fails by Tsai-Hill"): each clause is judged by the criteria
# it names, else by those its sentence names, else by all of them.
_CLAUSE = re.compile(r"\b(?:but|while|whilst|whereas|however)\b|;", re.IGNORECASE)


@dataclass(frozen=True)
class Verdicts:
    """What the guard holds an answer to: each criterion's verdict at the applied loading, True when it fails there."""

    fails: dict[str, bool]


@dataclass(frozen=True)
class WordGuard:
    ok: bool
    offending: tuple[str, ...] = ()
    reason: str | None = None


def verdicts_of(facts: dict[str, Any] | None) -> Verdicts | None:
    """The fact sheet's verdict per criterion, or None when it states none (a setup check, a laminate problem, no result)."""
    if not facts:
        return None
    criteria = facts.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return None
    fails = {str(c): facts.get(f"{c}_fails") for c in criteria}
    if not all(isinstance(v, bool) for v in fails.values()):
        return None
    return Verdicts({c: bool(v) for c, v in fails.items()})


def _named(text: str, verdicts: Verdicts) -> list[str]:
    return [c for c in verdicts.fails if c in CRITERION_WORDS and CRITERION_WORDS[c].search(text)]


def verdict_guard(prose: str, facts: dict[str, Any] | None) -> WordGuard:
    """Whether the model's words keep to the engine's verdict and decide nothing for the engineer (ADR-0139), with the words that do not."""
    verdicts = verdicts_of(facts)
    approval: list[str] = []
    contrary: list[str] = []
    for sentence in (s.strip() for s in _SENTENCE.split(prose or "")):
        if not sentence:
            continue
        approval += [m.group(0) for m in APPROVAL.finditer(sentence)]
        if verdicts is None or SUPPOSES.search(sentence):
            continue
        in_sentence = _named(sentence, verdicts)
        for clause in _CLAUSE.split(sentence):
            named = _named(clause, verdicts) or in_sentence
            judged = {c: verdicts.fails[c] for c in named} if named else verdicts.fails
            held = HOLDS.search(clause)
            if held and any(judged.values()):
                contrary.append(held.group(0))
            failed = FAILS.search(clause)
            if failed and not PLACES_FAILURE.search(clause) and not any(judged.values()):
                contrary.append(failed.group(0))
    if approval:
        words = ", ".join(dict.fromkeys(w.lower() for w in approval))
        return WordGuard(False, tuple(dict.fromkeys(approval)),
                         f"the model's answer called the design {words}, which no analysis here decides: the engineer does")
    if contrary:
        return WordGuard(False, tuple(dict.fromkeys(contrary)),
                         "the model's answer said " + "; ".join(f"“{c}”" for c in dict.fromkeys(contrary))
                         + ", against the engine's verdict at the applied loading")
    return WordGuard(True)
