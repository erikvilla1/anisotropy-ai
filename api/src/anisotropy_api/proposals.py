"""The model proposes, the engineer confirms (ADR-0088). The page offers the rows a message may fill; the model reads the message and
proposes values for them; the source guard here keeps a proposal only when the engineer's own words hold it, and the page shows what is
kept in a card the engineer ticks before anything enters the problem. Nothing here computes a result (ADR-0001): a proposal is a value the
engineer wrote, in a row the page offered, converted only between the decimal units of one system (kN to N, GPa to MPa), never across.

The guard, per proposal:
- the row is one the page offered, proposed once;
- the quote is copied from the message;
- a number is one the quote writes (its sign may be read from the words: "cooled by 150" is -150), and a written unit is in the quote;
- the unit is one the row takes: for a coupon, a unit of the row's own system, converted to the row's unit; for a laminate, any unit of the
  row's dimension, kept as written (the engine converts, ADR-0060);
- a choice is one of the row's choices; a notation is written in the quote.
A condition must be offered and asked for in the quote; a question may hold only numbers the message holds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from anisotropy_engine.units import UNITS

# What the model never sees of a form (R-11): who filled it in, notes, sources and names, the team's model and data.
HIDDEN_KEYS = frozenset({"filled_by", "date", "notes", "size_from", "team_model", "test_data", "material_code", "layup_code", "tab_material",
                         "title", "name", "source"})
HIDDEN_ENDINGS = ("_name", "_source", "_notes")
MAX_PROPOSALS = 60
MAX_QUOTE = 400

# The units a coupon row may be proposed in (ADR-0061): name -> (dimension, system, factor to the system's base unit). A value is converted
# only within its system, by an exact power of ten; a value in the other system is refused, as the chat refuses it.
COUPON_UNITS: dict[str, tuple[str, str, Decimal]] = {
    "m": ("length", "SI", Decimal(1)), "cm": ("length", "SI", Decimal("0.01")), "mm": ("length", "SI", Decimal("0.001")),
    "in": ("length", "US", Decimal(1)),
    "N": ("force", "SI", Decimal(1)), "kN": ("force", "SI", Decimal(1000)),
    "lbf": ("force", "US", Decimal(1)), "kip": ("force", "US", Decimal(1000)),
    "Pa": ("stress", "SI", Decimal(1)), "kPa": ("stress", "SI", Decimal("1e3")), "MPa": ("stress", "SI", Decimal("1e6")), "GPa": ("stress", "SI", Decimal("1e9")),
    "psi": ("stress", "US", Decimal(1)), "ksi": ("stress", "US", Decimal("1e3")), "Msi": ("stress", "US", Decimal("1e6")),
}
SYSTEM_WORDS = {"SI": "SI units (mm, N, MPa)", "US": "US units (in, lbf, psi)"}

# Typed spellings of the units both tables name, squashed (lower case, no spaces, products as *): the canonical name.
_SPELLINGS: dict[str, str] = {
    "inch": "in", "inches": "in", '"': "in", "millimetre": "mm", "millimetres": "mm", "millimeter": "mm", "millimeters": "mm",
    "metre": "m", "metres": "m", "meter": "m", "meters": "m", "centimetre": "cm", "centimetres": "cm", "centimeter": "cm", "centimeters": "cm",
    "newton": "N", "newtons": "N", "kilonewton": "kN", "kilonewtons": "kN", "lb": "lbf", "lbs": "lbf", "pound": "lbf", "pounds": "lbf",
    "pound-force": "lbf", "kips": "kip", "lbf/in": "lb/in", "lbs/in": "lb/in", "kips/in": "kip/in", "n*mm/mm": "N*mm/mm", "nmm/mm": "N*mm/mm",
    "n*m/m": "N*m/m", "nm/m": "N*m/m", "kn*m/m": "kN*m/m", "knm/m": "kN*m/m", "lb*in/in": "lb*in/in", "lbf*in/in": "lb*in/in",
    "lbin/in": "lb*in/in", "kip*in/in": "kip*in/in", "kipin/in": "kip*in/in",
}
_CANONICAL = {name.lower(): name for name in [*UNITS, *COUPON_UNITS] if name not in ("K",) and "deg" not in name}
_NUMBER = re.compile(r"(?<![A-WYZa-wyz_\d.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_MICRO = re.compile(r"^(?:[x×*]?\s*10\s*\^?\s*\(?\s*-\s*6\s*\)?|[x×*]?\s*10⁻⁶|1?e-6|µ|μ|micro(?:strain)?s?|ppm)$")


def _plain(text: str) -> str:
    """Text as the guard compares it: one kind of minus and quote mark, thousands separators gone, spaces collapsed, lower case."""
    t = text.replace("−", "-").replace("–", "-").replace("“", '"').replace("”", '"').replace("’", "'").replace(" ", " ")
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", _plain(text))


def temperature_unit(text: str) -> str | None:
    """A temperature unit as typed (°C, deg C, C, celsius, K, °F) as the engine's table names a change of it; None when it is none."""
    s = re.sub(r"°|º|degrees?|deg|\s", "", text.lower())
    return {"c": "degC", "celsius": "degC", "f": "degF", "fahrenheit": "degF", "k": "K", "kelvin": "K"}.get(s)


def unit_named(text: str) -> str | None:
    """The canonical name of a unit as typed, from the engine's table and the coupon's forces; None when the text names no unit."""
    t = _plain(text)
    if not t:
        return None
    temperature = temperature_unit(t)
    if temperature:
        return temperature
    per = re.match(r"^(.*?)\s*(?:/|per\s+)\s*(°?\s*(?:deg(?:rees?)?\s*)?[a-z]+)$", t)
    if per and temperature_unit(per.group(2)):
        left = per.group(1).strip()
        if left in ("", "1"):
            return f"1/{temperature_unit(per.group(2))}"
        if _MICRO.match(left):
            return f"1e-6/{temperature_unit(per.group(2))}"
        return None
    squashed = t.replace(" ", "").replace("·", "*").replace("×", "*")
    return _SPELLINGS.get(squashed) or _CANONICAL.get(squashed)


def dimension_of(unit: str) -> str | None:
    if unit in UNITS:
        return UNITS[unit][0]
    return COUPON_UNITS[unit][0] if unit in COUPON_UNITS else None


def numbers_written(text: str) -> list[Decimal]:
    """Every number the text writes, the digits of a name such as IM7 apart; a unit may follow a number ("10kN", "0.125mm")."""
    out = []
    for token in _NUMBER.findall(_plain(text)):
        try:
            out.append(Decimal(token))
        except InvalidOperation:
            continue
    return out


def _decimal(text: str) -> Decimal | None:
    t = _plain(text)
    if not re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?", t):
        return None
    try:
        value = Decimal(t)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _written(value: Decimal) -> str:
    """A converted value as a row takes it: plain digits, no exponent, no trailing zeros."""
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def model_view_of_form(form: dict[str, str]) -> dict[str, str]:
    """The filled rows the model may see: none that names a person, a source, a note or the team's own files (R-11)."""
    return {key: value for key, value in form.items()
            if value.strip() and key not in HIDDEN_KEYS and not key.endswith(HIDDEN_ENDINGS)}


@dataclass
class Kept:
    proposals: list[dict[str, Any]] = field(default_factory=list)
    conditions: list[dict[str, Any]] = field(default_factory=list)
    question: str | None = None
    dropped: list[dict[str, str]] = field(default_factory=list)


def _row_value(row: dict[str, Any], value: str, unit_text: str | None, quote: str) -> tuple[str, str | None] | str:
    """The value and unit a row takes from a proposal, or the reason the proposal is dropped."""
    kind = row["kind"]
    if kind == "choice":
        choices = [c["value"] for c in row.get("choices") or []]
        if value not in choices:
            return f"{value!r} is not one of the row's choices"
        if unit_text:
            return "a choice carries no unit"
        return value, None
    if kind == "notation":
        if not value.strip() or _squash(value) not in _squash(quote):
            return "the notation is not written in the quoted words"
        return value.strip(), None
    number = _decimal(value)
    if number is None:
        return f"{value!r} is not a number"
    written = numbers_written(quote)
    if abs(number) not in [abs(n) for n in written] and not (number == 0 and re.search(r"\b(zero|nil|none|nothing)\b", _plain(quote))):
        return f"{value} is not a number the quoted words write"
    if unit_text and _squash(unit_text) not in _squash(quote):
        return f"the unit {unit_text!r} is not written in the quoted words"
    unit = unit_named(unit_text) if unit_text else None
    if unit_text and unit is None:
        return f"{unit_text!r} is not a unit the engine knows"
    if row.get("dimension"):  # a laminate row: any unit of its dimension, kept as written (the engine converts, ADR-0060)
        if unit is not None and dimension_of(unit) != row["dimension"]:
            return f"{unit_text} is not a unit of {row['dimension'].replace('_', ' ')}"
        return _plain(value).lstrip("+"), unit
    if row.get("unit"):  # a coupon row: a unit of the row's own system, converted to the row's unit (ADR-0061)
        target = row["unit"]
        if unit is None or unit == target:
            return _plain(value).lstrip("+"), target
        if unit not in COUPON_UNITS or target not in COUPON_UNITS or COUPON_UNITS[unit][0] != COUPON_UNITS[target][0]:
            return f"{unit_text} is not a unit of the row, which is stated in {target}"
        if COUPON_UNITS[unit][1] != COUPON_UNITS[target][1]:
            return (f"{unit_text} belongs to {SYSTEM_WORDS[COUPON_UNITS[unit][1]]}, and this coupon is stated in "
                    f"{SYSTEM_WORDS[COUPON_UNITS[target][1]]}: give it in {target}, or switch the coupon's units")
        return _written(number * COUPON_UNITS[unit][2] / COUPON_UNITS[target][2]), target
    if unit is not None:
        return "the row is a pure number and carries no unit"
    return _plain(value).lstrip("+"), None


def source_guard(raw: dict[str, Any], message: str, rows: list[dict[str, Any]], conditions: list[dict[str, Any]]) -> Kept:
    """What of the model's reading the engineer's words hold: the proposals kept, each with the value and unit the row takes, and those
    dropped with the reason. `raw` is the model's answer as parsed; `rows` and `conditions` are what the page offered."""
    kept = Kept()
    plain_message = _plain(message)
    offered = {row["key"]: row for row in rows}
    taken: set[str] = set()
    for item in list(raw.get("proposals") or [])[:MAX_PROPOSALS]:
        if not isinstance(item, dict):
            continue
        key, value, unit_text, quote = (str(item.get("key", "")), str(item.get("value", "")).strip(), item.get("unit"), str(item.get("quote", "")))
        unit_text = str(unit_text).strip() if unit_text not in (None, "") else None

        def drop(reason: str) -> None:
            kept.dropped.append({"key": key, "reason": reason})

        if key not in offered:
            drop("not a row on offer")
            continue
        if key in taken:
            drop("proposed twice; the first stands")
            continue
        if not quote.strip() or len(quote) > MAX_QUOTE or _plain(quote) not in plain_message:
            drop("the quoted words are not in the message")
            continue
        outcome = _row_value(offered[key], value, unit_text, quote)
        if isinstance(outcome, str):
            drop(outcome)
            continue
        taken.add(key)
        row_value, unit = outcome
        kept.proposals.append({"key": key, "label": offered[key]["label"], "value": row_value, "unit": unit,
                               "written_value": value, "written_unit": unit_text, "quote": quote.strip()})
    on_offer = {c["id"]: c for c in conditions}
    for item in list(raw.get("conditions") or [])[:len(on_offer) + 5]:
        if not isinstance(item, dict):
            continue
        cid, quote = str(item.get("id", "")), str(item.get("quote", ""))
        if cid not in on_offer:
            kept.dropped.append({"key": cid, "reason": "not a condition on offer"})
        elif not quote.strip() or len(quote) > MAX_QUOTE or _plain(quote) not in plain_message:
            kept.dropped.append({"key": cid, "reason": "the quoted words are not in the message"})
        elif cid not in [c["id"] for c in kept.conditions]:
            kept.conditions.append({"id": cid, "title": on_offer[cid]["title"], "quote": quote.strip()})
    question = raw.get("question")
    if isinstance(question, str) and question.strip():
        allowed = [abs(n) for n in numbers_written(message)]
        stray = [n for n in numbers_written(question) if abs(n) not in allowed]
        if len(question) > MAX_QUOTE:
            kept.dropped.append({"key": "question", "reason": "too long"})
        elif stray:
            kept.dropped.append({"key": "question", "reason": "it holds numbers the message does not: " + ", ".join(_written(n) for n in stray)})
        else:
            kept.question = question.strip()
    return kept
