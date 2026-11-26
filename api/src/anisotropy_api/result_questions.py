"""A model reads a loose question about a result into a fixed request (ADR-0100). The page offers what a question may name: the
quantities of its probe table, the plies with their angles, the regions, and whether an element is clicked. The model answers in a schema
that holds a kind, quantities and regions from those on offer, ply numbers, an element number and an end ("largest"); it holds no number
of a result, and the model is shown none. The guard here keeps the reading only when it stays inside the offer and the engineer's own
words hold the element it names. The page then runs the request on the results it shows (`lib/result-question.ts`), so every value the
engineer reads is one the solver wrote (ADR-0001).

The guard:
- the kind is one of values, extreme, failure, none; "none" is no request (the message is the setup's, or not about the results);
- "failure" (amendment 1) asks which ply fails first, whether the coupon fails or at what loading: it names no quantity, ply, element
  or region, and whatever of those the model wrote is dropped; the page answers with the package's own first-ply failure;
- the quantities are among those offered, each once, at least one;
- a ply is a whole number the laminate holds (plies may be named by angle or by position, so the message need not write the number;
  the page shows which plies it read);
- an element is a whole number the message writes: an element is only ever named by its number, or by a click ("here");
- an extreme names its end, and its region is one on offer;
- a question back may hold only numbers the message holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .proposals import MAX_QUOTE, _written, numbers_written

# The probe table's columns (lib/studio-fields.ts PROBE_COLUMNS), each in the words the model reads.
QUANTITIES: dict[str, str] = {
    "S11": "ply stress along the fibres, σ₁",
    "S22": "ply stress across the fibres, σ₂",
    "S12": "ply in-plane shear stress, τ₁₂",
    "Mises": "ply von Mises stress (a comparison quantity, not a composite failure criterion)",
    "Tresca": "ply Tresca stress (a comparison quantity)",
    "Max. Principal": "largest principal stress of the ply",
    "Mid. Principal": "middle principal stress of the ply",
    "Min. Principal": "smallest principal stress of the ply",
    "Pressure": "pressure stress of the ply",
    "E11": "ply strain along the fibres, ε₁",
    "E22": "ply strain across the fibres, ε₂",
    "E12": "ply engineering shear strain, γ₁₂",
}
REGIONS: dict[str, str] = {
    "default": "no region named: the gauge section where the model has one, a plate away from its held corners, else the whole model",
    "gauge": "the gauge section, away from the grips",
    "whole": "the whole model, the grips' clamped edges included",
}
KINDS = ("values", "extreme", "failure", "none")
SENSES = ("largest", "smallest", "magnitude")
MAX_PLIES = 200


def question_schema(quantities: list[str], regions: list[str]) -> dict[str, Any]:
    """The model's answer: names from those on offer, whole numbers for plies and an element, and no other field."""
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(KINDS)},
            "quantities": {"type": "array", "items": {"type": "string", "enum": list(quantities)}},
            "plies": {"type": "array", "items": {"type": "integer"}},
            "element": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "here": {"type": "boolean"},
            "sense": {"anyOf": [{"type": "string", "enum": list(SENSES)}, {"type": "null"}]},
            "region": {"type": "string", "enum": list(regions)},
            "question": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
        "required": ["kind", "quantities", "plies", "element", "here", "sense", "region", "question"],
        "additionalProperties": False,
    }


def model_view(message: str, quantities: list[str], plies: list[dict[str, Any]], gauge: bool, picked: bool) -> dict[str, Any]:
    """What the model may see: the message, the quantities and regions on offer in words, the plies with their angles, and whether an
    element is clicked. No result, no file, no name, note or source (R-11), and no region the engineer named."""
    regions = [key for key in REGIONS if key != "gauge" or gauge]
    return {"message": message, "quantities": [{"key": key, "words": QUANTITIES[key]} for key in quantities],
            "plies": [{"ply": int(p["ply"]), "angle": p["angle"]} for p in plies],
            "regions": [{"key": key, "words": REGIONS[key]} for key in regions], "element_clicked": bool(picked)}


@dataclass
class KeptQuestion:
    request: dict[str, Any] | None = None
    question: str | None = None
    dropped: list[str] = field(default_factory=list)


def _whole(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def question_guard(raw: dict[str, Any], message: str, view: dict[str, Any]) -> KeptQuestion:
    """What of the model's reading stands: the request, inside the offer and with an element the message writes, or none with the reasons;
    and a question back that holds only the message's numbers. `raw` is the model's answer as parsed; `view` is what it was shown."""
    kept = KeptQuestion()
    written = [abs(n) for n in numbers_written(message)]
    question = raw.get("question")
    if isinstance(question, str) and question.strip():
        stray = [n for n in numbers_written(question) if abs(n) not in written]
        if len(question) > MAX_QUOTE:
            kept.dropped.append("the question back is too long")
        elif stray:
            kept.dropped.append("the question back holds numbers the message does not: " + ", ".join(_written(n) for n in stray))
        else:
            kept.question = question.strip()

    kind = raw.get("kind")
    if kind == "none":
        return kept
    if kind not in KINDS:
        kept.dropped.append(f"{kind!r} is not a kind of request")
        return kept
    if kind == "failure":  # nothing the model names goes with it: the page reads the answer the package wrote (ADR-0100 amendment 1)
        kept.request = {"kind": "failure", "quantities": [], "plies": [], "element": None, "here": False, "sense": None, "region": "default"}
        return kept
    offered = [q["key"] for q in view["quantities"]]
    named = raw.get("quantities") if isinstance(raw.get("quantities"), list) else []
    quantities = [key for key in offered if key in named]
    if not quantities or any(key not in offered for key in named):
        kept.dropped.append("no quantity on offer is named" if not quantities else "a quantity that is not on offer is named")
        return kept
    count = len(view["plies"])
    plies_raw = raw.get("plies") if isinstance(raw.get("plies"), list) else []
    read = [_whole(v) for v in plies_raw[:MAX_PLIES]]
    plies = sorted({p for p in read if p is not None})
    if None in read or any(p < 1 or p > count for p in plies):
        kept.dropped.append(f"a ply is named that the laminate's {count} plies do not hold")
        return kept
    element = _whole(raw.get("element")) if raw.get("element") is not None else None
    if raw.get("element") is not None and (element is None or element < 1 or Decimal(element) not in written):
        kept.dropped.append("the element named is not a number the message writes")
        return kept
    here = raw.get("here") is True and element is None
    if kind == "values":
        kept.request = {"kind": "values", "quantities": quantities, "plies": plies, "element": element, "here": here, "sense": None, "region": "default"}
        return kept
    sense, region = raw.get("sense"), raw.get("region")
    if sense not in SENSES:
        kept.dropped.append("an extreme names no end (largest, smallest or magnitude)")
        return kept
    if region not in [r["key"] for r in view["regions"]]:
        kept.dropped.append(f"{region!r} is not a region on offer")
        return kept
    kept.request = {"kind": "extreme", "quantities": quantities, "plies": plies, "element": None, "here": False, "sense": sense, "region": region}
    return kept
