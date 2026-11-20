"""A plate's supports and loads proposed from a message and the place clicked (ADR-0101). On a plate (ADR-0054) the engineer holds and
loads named regions. The page offers the regions, and says which of them the clicked element belongs to (`here`); the model reads the
message and proposes supports and loads over them in a fixed schema; the guard here keeps a proposal only when the engineer's words or
the engineer's click hold it; and the page shows what is kept in the card the engineer ticks (ADR-0088). Nothing here computes a result.

The guard, per proposal:
- the region is one the page offered, and it is either named by the quoted words ("the left edge") or one of the regions clicked;
- the quote is copied from the message;
- a support holds directions from the six a plate has, each once;
- a load's value is a number the quote writes, in a unit of the plate's own system, converted to the row's unit as a coupon's is;
- a pressure acts on an area; a force names a direction (x, y or z);
- a force stated as tension or compression takes its direction and its sign from the edge it acts on, here and not from the model:
  tension pulls along the edge's outward normal. A region with no outward normal (the face, a tab, the hole) is refused with the reason.
The model is shown no result, no file, no name and no region the engineer named (a drawn box is not offered).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .proposals import MAX_QUOTE, _plain, _row_value, _written

# The regions a plate always has or gains from its rows (ADR-0054; `lib/coupon-form-definition.json`, the `plate` block), with their kind.
REGION_KINDS: dict[str, str] = {
    "Edge-Bottom": "edge", "Edge-Top": "edge", "Edge-Left": "edge", "Edge-Right": "edge", "Hole": "edge",
    "Face": "area", "Tab-Bottom": "area", "Tab-Top": "area",
}
# The directions a support may hold, as the model names them, and the plate's own numbers (1 to 3 along x, y, z; 4 to 6 about them).
DIRECTIONS: dict[str, int] = {"x": 1, "y": 2, "z": 3, "tilt_x": 4, "tilt_y": 5, "turn_z": 6}
FORCE_DIRECTIONS = ("x", "y", "z")
SENSES = ("tension", "compression", "as_signed")
# A straight edge's outward normal in the plate's axes (the mesher's node rows: Edge-Left at x = 0, Edge-Right at x = width, Edge-Bottom at
# y = 0, Edge-Top at y = length): the direction's number and the sign of a pull along it.
EDGE_NORMAL: dict[str, tuple[int, int]] = {"Edge-Left": (1, -1), "Edge-Right": (1, 1), "Edge-Bottom": (2, -1), "Edge-Top": (2, 1)}
MAX_ENTRIES = 12
# Abaqus's words for a boundary condition and a force, as an engineer writes them (ADR-0110). Each has one meaning, so the quoted words fix
# the directions whatever the model wrote: a named condition holds its set, a code holds its direction, CF1 to CF3 point a force along x,
# y or z. A roller alone names no direction, so it needs one written beside it.
NAMED_SUPPORTS: dict[str, tuple[int, ...]] = {
    "encastre": (1, 2, 3, 4, 5, 6), "encastré": (1, 2, 3, 4, 5, 6), "pinned": (1, 2, 3), "pin": (1, 2, 3),
    "xsymm": (1, 5, 6), "ysymm": (2, 4, 6), "zsymm": (3, 4, 5),
}
DIRECTION_CODES: dict[str, int] = {"u1": 1, "u2": 2, "u3": 3, "ur1": 4, "ur2": 5, "ur3": 6}
FORCE_CODES: dict[str, str] = {"cf1": "x", "cf2": "y", "cf3": "z"}


def _word(word: str, text: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text) is not None


def written_directions(quote: str) -> list[int] | None:
    """The directions the quoted words fix by Abaqus's names and codes ("encastre", "XSYMM", "U1 and UR3"), or None when they fix none."""
    q = _plain(quote)
    found = {d for word, dofs in NAMED_SUPPORTS.items() if _word(word, q) for d in dofs} | {d for code, d in DIRECTION_CODES.items() if _word(code, q)}
    return sorted(found) or None


def written_force_direction(quote: str) -> str | None:
    """The direction a force's quoted words fix by CF1, CF2 or CF3, or None; two codes fix none."""
    q = _plain(quote)
    found = {axis for code, axis in FORCE_CODES.items() if _word(code, q)}
    return found.pop() if len(found) == 1 else None

PLATE_SYSTEM = (
    " This problem is a plate, held and loaded over named regions. Besides rows you may propose supports and loads. plate.regions lists "
    "the regions on offer, each an edge or an area. plate.here lists the regions of the element the engineer clicked on the model: words "
    "such as here, this edge, this face or the selected one mean one of those. Choose the one whose kind fits the words (an edge for an "
    "edge, the face for the face); when two fit equally, or the words point at a place and plate.here is empty, propose nothing for it and "
    "ask one short question. A support names a region and the directions it holds, from x, y, z, tilt_x, tilt_y and turn_z: held or fixed "
    "with no direction named is x, y and z; clamped or built-in is all six; simply supported is z. A load is a force, the total over its "
    "region, or a pressure on an area. For a force the message states as tension or compression on an edge, set sense to tension or "
    "compression and direction to null: the direction is worked out from the edge. For any other force set sense to as_signed and give the "
    "direction x, y or z, with a minus sign on the value when the words say it acts against that axis (downward is against z). A pressure "
    "has direction null and sense as_signed, and is positive when it presses down on the plate; give a minus sign for suction or a "
    "pressure from below. Value, unit and quote follow the same rules as for rows. plate.held and plate.loaded name the regions already "
    "held and loaded. The engineer may use Abaqus's words: a boundary condition (BC) is a support; U1, U2, U3 are x, y, z and UR1, UR2, "
    "UR3 are tilt_x, tilt_y, turn_z; encastre is all six; pinned (or pin) is x, y and z; XSYMM is x, tilt_y and turn_z; YSYMM is y, tilt_x and "
    "turn_z; ZSYMM is z, tilt_x and tilt_y; CF1, CF2 and CF3 are a force along x, y and z. A roller with no direction written: propose "
    "nothing for it and ask which direction it holds. Quote the words that hold these names."
)


def plate_schema(base: dict[str, Any], regions: list[str]) -> dict[str, Any]:
    """The proposals' schema with a plate's two lists added: the regions are the ones on offer and nothing else can be named."""
    schema = copy.deepcopy(base)
    text_or_null = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    schema["properties"]["supports"] = {"type": "array", "items": {
        "type": "object",
        "properties": {"region": {"type": "string", "enum": list(regions)},
                       "directions": {"type": "array", "items": {"type": "string", "enum": list(DIRECTIONS)}},
                       "quote": {"type": "string"}},
        "required": ["region", "directions", "quote"], "additionalProperties": False}}
    schema["properties"]["loads"] = {"type": "array", "items": {
        "type": "object",
        "properties": {"region": {"type": "string", "enum": list(regions)},
                       "kind": {"type": "string", "enum": ["force", "pressure"]},
                       "direction": {"anyOf": [{"type": "string", "enum": list(FORCE_DIRECTIONS)}, {"type": "null"}]},
                       "sense": {"type": "string", "enum": list(SENSES)},
                       "value": {"type": "string"}, "unit": text_or_null, "quote": {"type": "string"}},
        "required": ["region", "kind", "direction", "sense", "value", "unit", "quote"], "additionalProperties": False}}
    schema["required"] = [*schema["required"], "supports", "loads"]
    return schema


def plate_view(offer: dict[str, Any]) -> dict[str, Any]:
    """What the model may see of the plate: the regions on offer with their kind, those of the clicked element, the units a load is stated
    in, and which regions are already held and loaded. No value, no name, no box the engineer drew."""
    return {"regions": [{"name": r["name"], "kind": r["kind"]} for r in offer["regions"]], "here": list(offer["here"]),
            "force_unit": offer["force_unit"], "pressure_unit": offer["stress_unit"],
            "held": list(offer.get("held") or []), "loaded": list(offer.get("loaded") or [])}


@dataclass
class KeptPlate:
    supports: list[dict[str, Any]] = field(default_factory=list)
    loads: list[dict[str, Any]] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)

    def not_taken(self, unread: list[dict[str, str]]) -> list[dict[str, str]]:
        """The unread parts of a message (ADR-0088 amendment 1) less the words a kept support or load quotes."""
        quoted = {_plain(entry["quote"]) for entry in [*self.supports, *self.loads]}
        return [part for part in unread if _plain(part["quote"]) not in quoted]


def _one_slip(word: str, side: str) -> bool:
    """Whether a typed word is the side's name with one slip of the keys: a letter doubled, dropped, struck for another or two swapped
    ("lefft", "rigt", "botom", "tpo"). The side is the model's choice and the guard only checks that the words point at it, so a word one
    slip from it does; a slip of a word of three letters is a swap alone ("top", not "tip")."""
    if word == side or abs(len(word) - len(side)) > 1:
        return word == side
    if len(word) == len(side):
        diff = [i for i, (a, b) in enumerate(zip(word, side)) if a != b]
        swapped = len(diff) == 2 and diff[1] == diff[0] + 1 and word[diff[0]] == side[diff[1]] and word[diff[1]] == side[diff[0]]
        return swapped or (len(diff) == 1 and len(side) > 3)
    if len(side) <= 3:
        return False
    short, long = (word, side) if len(word) < len(side) else (side, word)
    return any(long[:i] + long[i + 1:] == short for i in range(len(long)))


def _names(region: str, quote: str) -> bool:
    """Whether the quoted words name the region: an edge by its side, a tab by its side and the word tab, the face, the hole. A side's
    name typed with one slip names it too (ADR-0101 amendment 3)."""
    q = _plain(quote)
    words = re.findall(r"[a-z]+", q)

    def has(pattern: str) -> bool:
        return re.search(pattern, q) is not None

    def side(name: str) -> bool:
        return any(_one_slip(word, name) for word in words)

    tab = has(r"\btabs?\b")
    if region.startswith("Edge-"):
        return side(region[5:].lower()) and not tab
    if region.startswith("Tab-"):
        return tab and side(region[4:].lower())
    if region == "Hole":
        return has(r"\bholes?\b")
    if region == "Face":
        return has(r"\b(?:face|surface|whole plate|entire plate)\b")
    return False


def plate_guard(raw: dict[str, Any], message: str, offer: dict[str, Any]) -> KeptPlate:
    """What of the model's supports and loads the engineer's words and click hold. `raw` is the model's answer as parsed; `offer` is what
    the page offered: the regions, those clicked, and the units a force and a pressure are stated in."""
    kept = KeptPlate()
    plain_message = _plain(message)
    kinds = {r["name"]: r["kind"] for r in offer["regions"]}
    here = set(offer["here"])

    def placed(region: str, quote: str) -> str | None:
        """Why the proposal's region or quote does not stand, or None."""
        if region not in kinds:
            return "not a region on offer"
        if not quote.strip() or len(quote) > MAX_QUOTE or _plain(quote) not in plain_message:
            return "the quoted words are not in the message"
        if not _names(region, quote) and region not in here:
            return f"the quoted words do not name {region}, and it is not where you clicked"
        return None

    held: set[str] = set()
    for item in list(raw.get("supports") or [])[:MAX_ENTRIES]:
        if not isinstance(item, dict):
            continue
        region, quote = str(item.get("region", "")), str(item.get("quote", ""))
        names = item.get("directions")
        reason = placed(region, quote)
        written = written_directions(quote)
        if reason is None and region in held:
            reason = "held twice; the first stands"
        if reason is None and written is None and _word("roller", _plain(quote)) and not re.search(r"(?<![a-z0-9])[xyz](?![a-z0-9])", _plain(quote)):
            reason = "a roller holds one direction: say which, x, y or z"
        if reason is None and written is None and (not isinstance(names, list) or not names or any(n not in DIRECTIONS for n in names)):
            reason = "it names no direction a plate holds"
        if reason is not None:
            kept.dropped.append({"key": f"support on {region}" if region in kinds else "support", "reason": reason})
            continue
        held.add(region)
        dofs = written if written is not None else sorted({DIRECTIONS[n] for n in names})
        kept.supports.append({"region": region, "dofs": dofs, "quote": quote.strip()})

    for item in list(raw.get("loads") or [])[:MAX_ENTRIES]:
        if not isinstance(item, dict):
            continue
        region, quote, kind = str(item.get("region", "")), str(item.get("quote", "")), str(item.get("kind", ""))
        value, unit_text = str(item.get("value", "")).strip(), item.get("unit")
        unit_text = str(unit_text).strip() if unit_text not in (None, "") else None
        direction, sense = item.get("direction"), str(item.get("sense", "as_signed"))
        key = f"load on {region}" if region in kinds else "load"

        def drop(reason: str, key: str = key) -> None:
            kept.dropped.append({"key": key, "reason": reason})

        reason = placed(region, quote)
        if reason is not None:
            drop(reason)
            continue
        if kind not in ("force", "pressure") or sense not in SENSES:
            drop("neither a force nor a pressure")
            continue
        target = offer["force_unit"] if kind == "force" else offer["stress_unit"]
        outcome = _row_value({"kind": "number", "unit": target}, value, unit_text, quote)
        if isinstance(outcome, str):
            drop(outcome)
            continue
        amount = Decimal(outcome[0])
        if amount == 0:
            drop("a load of zero is no load")
            continue
        dof: int | None = None
        if kind == "pressure":
            if kinds[region] != "area":
                drop(f"a pressure acts on an area, and {region} is an edge")
                continue
            sense = "as_signed"
        elif sense in ("tension", "compression") and written_force_direction(quote) is None:
            if region not in EDGE_NORMAL:
                drop(f"{sense} has no one direction on {region}: name the direction, x, y or z")
                continue
            dof, outward = EDGE_NORMAL[region]
            amount = abs(amount) * (outward if sense == "tension" else -outward)
        else:
            coded = written_force_direction(quote)  # "CF2 = 500 N" is along y and signed as written, whatever the model wrote
            if coded is not None:
                direction, sense = coded, "as_signed"
            if direction not in FORCE_DIRECTIONS:
                drop("a force needs a direction: x, y or z")
                continue
            dof = DIRECTIONS[direction]
        kept.loads.append({"region": region, "kind": kind, "dof": dof, "value": _written(amount), "unit": target, "written_value": value,
                           "written_unit": unit_text, "sense": sense if kind == "force" else None, "quote": quote.strip()})
    return kept
