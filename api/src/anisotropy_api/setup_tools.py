"""The workspace's tools over a model's setup (ADR-0143): one set of typed steps for the page, the MCP server and, from build step 2, the
workspace's planner. A tool reads the model as a project keeps it (`content`: the form's rows as text and a plate's lists, as the page
writes them, `lib/project-store.ts`) and answers in data. No model is asked here and nothing here computes a result (ADR-0001): the fea
package judges every row and every list at check time, as always (ADR-0051).

- `read_setup`: what the model is, in its own units: the test, the size, the regions a plate is held and loaded on with where each lies
  and whether it is an end or a side, and what is held and loaded, one line each.
- `regions`: the plate's regions, all of them or those of one role: its ends (the edges across the width at y = 0 and y = length, which
  a pull along the plate acts on, and the tabs there), its sides (the long edges), its edges or its areas.
- `change_setup`: typed changes (hold, move, force, pressure, free, unload, row) made on a copy, every one or none: what changed, one line
  each, or why each refused change cannot be made. The page's own reader (`lib/plate-edits.ts`) applies a sentence by the same rules: a
  new hold on a region takes the place of the one it had, a new force along a direction or a new pressure takes the place of the one
  there, and tension pulls along an edge's outward normal (`plate_proposals.EDGE_NORMAL`).
- `plate_values`: the values the fea package takes for a plate on the model tree, as `lib/tension-screen.ts` (`plateTreeValues`) writes
  them; `tests/fixtures/studio-plate/plate-values.json` holds what the page writes, and the page and this module are both tested on it.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .plate_proposals import EDGE_NORMAL
from .proposals import COUPON_UNITS, HIDDEN_ENDINGS, HIDDEN_KEYS, SYSTEM_WORDS, _written, unit_named

REPO = Path(__file__).resolve().parents[3]
FORM_DEFINITION = REPO / "lib" / "coupon-form-definition.json"  # written by fea/tools/export_form_definition.py; the page is built from it

ACTIONS = ("hold", "move", "force", "pressure", "free", "unload", "row")
ROLES = ("all", "ends", "sides", "edges", "areas")
MAX_CHANGES = 24
MAX_TEXT = 200
# The rows of the form the page groups, as `lib/studio-form.ts` names them; which a test shows is `_visible`, as `sectionsFor` there.
HOLE_KEYS = ("hole_diameter", "hole_circumferential", "hole_radial", "hole_ring", "hole_growth")
BENDING_KEYS = ("span", "overhang", "load_span")
GRIP_KEYS = ("grips", "region", "tab_length")
LOADING_KEYS = ("control", "value")
TAB_KEYS = ("tab_thickness", "tab_bevel", "tab_material")
STRAIN_KEYS = ("strain_device", "strain_length")
DOGBONE_KEYS = ("narrow_width", "narrow_length", "radius", "outer_radius")
ISOTROPIC_KEYS = ("thickness", "own_E", "own_nu")
ISOTROPIC_TESTS = ("unnotched tension", "unnotched compression", "open-hole tension")
PLY_MATERIAL_KEYS = ("library", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6", "G13", "G23",
                     "f12_star")
OPEN_HOLE_TEST = "open-hole tension"
BENDING_TESTS = ("three-point bending", "four-point bending")
FOUR_POINT_TEST = "four-point bending"
DOGBONE_TEST = "unnotched tension"
# Rows a change may not make: the test and the unit system change what every other row means, and the page changes them itself.
FIXED_ROWS = frozenset({"test", "units"})
NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$", re.IGNORECASE)
ANGLE_UNITS = {"rad": Decimal(1), "radian": Decimal(1), "radians": Decimal(1),
               "deg": None, "degs": None, "degree": None, "degrees": None, "°": None}  # None: degrees, times pi/180
ABAQUS_NAMES: list[tuple[frozenset[int], str]] = [(frozenset({1, 2, 3}), "pinned"), (frozenset({1, 5, 6}), "XSYMM"),
                                                   (frozenset({2, 4, 6}), "YSYMM"), (frozenset({3, 4, 5}), "ZSYMM")]


@functools.cache
def form_definition() -> dict[str, Any]:
    """The coupon form the page is built from."""
    return json.loads(FORM_DEFINITION.read_text(encoding="utf-8"))


def _fields() -> list[dict[str, Any]]:
    return [f for section in form_definition()["sections"] for f in section["fields"]]


def _field(key: str) -> dict[str, Any] | None:
    return next((f for f in _fields() if f["key"] == key), None)


def plate_test() -> str:
    return form_definition().get("plate", {}).get("test", "plate")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def units_of(form: dict[str, str]) -> str:
    """The system a form is stated in: its Units row, or the form's own when the row is blank or unknown (`unitsOf`)."""
    systems = form_definition()["unit_systems"]
    stated = _text(form.get("units"))
    return stated if stated in systems else form_definition()["units"]


def unit_labels(form: dict[str, str]) -> dict[str, str]:
    return form_definition()["unit_systems"][units_of(form)]["labels"]


def _js_number(text: str) -> int | float:
    """A row's text as the page's `Number(text)` reads it, written to JSON as the page writes it: a whole number without a decimal point."""
    value = float(text)
    return int(value) if value.is_integer() and abs(value) < 2**53 else value


def _parsed(text: Any) -> Any:
    """A list entry's text as `plateValues` sends it: a number when it reads as one, else the text trimmed."""
    t = _text(text).strip()
    return _js_number(t) if NUMBER.match(t) else t


def _positive(text: Any) -> bool:
    """`Number(text) > 0` as the page reads a row: blank and words are not."""
    t = _text(text).strip()
    try:
        return t != "" and float(t) > 0
    except ValueError:
        return False


def _standard(form: dict[str, str]) -> dict[str, Any] | None:
    return next((p for p in form_definition()["standards"]["profiles"] if p["designation"] == form.get("standard")), None)


def _visible(key: str, form: dict[str, str]) -> bool:
    """Whether the form shows a row for its test, as `sectionsFor` in `lib/studio-form.ts` decides it."""
    test = _text(form.get("test"))
    plate = test == plate_test()
    bending = test in BENDING_TESTS
    isotropic = form.get("material_kind") == "isotropic" and test in ISOTROPIC_TESTS
    if key in HOLE_KEYS:
        return test == OPEN_HOLE_TEST or plate
    if key in BENDING_KEYS:
        return bending and (key != "load_span" or test == FOUR_POINT_TEST)
    if key == "tab_length":
        return not bending
    if key in GRIP_KEYS:
        return not bending and not plate
    if key in LOADING_KEYS:
        return not plate
    if key in TAB_KEYS or key in STRAIN_KEYS:
        return not bending and not plate
    if key == "specimen":
        standard = _standard(form)
        return bool(standard and standard.get("variant_words"))
    if key in DOGBONE_KEYS:
        return test == DOGBONE_TEST
    if key == "material_kind":
        return test in ISOTROPIC_TESTS
    if key in ISOTROPIC_KEYS:
        return isotropic
    if re.fullmatch(r"ply_\d+", key) or key in PLY_MATERIAL_KEYS or key in ("symmetric", "ply_thickness", "criteria"):
        return not isotropic
    return True


# ----------------------------------------------------------------------------------------------------- the plate's lists

def lists_of(content: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """A project's plate lists, each list present, as `projectOfRecord` reads them."""
    plate = content.get("plate") if isinstance(content.get("plate"), dict) else {}
    return {key: [dict(e) for e in plate.get(key) or [] if isinstance(e, dict)] for key in ("supports", "loads", "regions")}


def form_of(content: dict[str, Any]) -> dict[str, str]:
    form = content.get("form") if isinstance(content.get("form"), dict) else {}
    return {k: v for k, v in form.items() if isinstance(v, str)}


def plate_lists_values(lists: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """The lists as the API takes them (`plateValues`): numbers parsed, a blank value left out so the check names the row."""
    supports = [{"region": _text(s.get("region")), "dofs": list(s.get("dofs") or []),
                 **({"value": _parsed(s.get("value"))} if _text(s.get("value")).strip() else {})} for s in lists["supports"]]
    loads = [{"region": _text(l.get("region")), "pressure": _parsed(l.get("pressure"))} if l.get("kind") == "pressure"
             else {"region": _text(l.get("region")), "dof": l.get("dof"), "total": _parsed(l.get("total"))} for l in lists["loads"]]
    regions = [{"name": _text(r.get("name")).strip(), **{k: _parsed(r.get(k)) for k in ("x0", "x1", "y0", "y1")}} for r in lists["regions"]]
    return {"supports": supports, "loads": loads, "regions": regions}


def form_values(form: dict[str, str], lists: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """The values object of a form (`buildValues`): every row the test shows, numbers parsed, blanks left out; a plate's lists beside."""
    values: dict[str, Any] = {"form_version": form_definition()["form_version"]}
    for f in _fields():
        if not _visible(f["key"], form):
            continue
        text = _text(form.get(f["key"])).strip()
        if not text:
            continue
        values[f["key"]] = _js_number(text) if f["kind"] in ("number", "whole", "angle") and NUMBER.match(text) else text
    if form.get("test") == plate_test() and lists is not None:
        values.update(plate_lists_values(lists))
    return values


def plate_values(content: dict[str, Any]) -> dict[str, Any]:
    """The values of a plate on the model tree (`plateTreeValues`): its rows and lists, and `"input": "plate"` so the fea package chooses
    what the engineer is not asked for, each with its reason (ADR-0089 amendment 8). A coupon's values are the tension screen's own
    (`tensionValues`), not these."""
    form = form_of(content)
    if form.get("test") != plate_test():
        raise ValueError(f"these are a plate's values, and this model is a {form.get('test') or 'coupon with no test yet'}")
    return {**form_values(form, lists_of(content)), "input": "plate"}


def content_digest(content: dict[str, Any]) -> str:
    """The SHA-256 of a setup as stored, so a change worked out on one setup is never applied to another."""
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def setup_key(content: dict[str, Any]) -> str:
    """The SHA-256 of a setup as a version counts it (`setupKey` in `lib/model-versions.ts`): the filled rows but the date, and the lists."""
    rows = {k: v.strip() for k, v in form_of(content).items() if k != "date" and v.strip()}
    return hashlib.sha256(json.dumps([rows, lists_of(content)], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------------------------------- reading the model

def dof_word(dof: int) -> str:
    return form_definition().get("plate", {}).get("dofs", {}).get(str(dof), f"direction {dof}")


def held_line(region: str, dofs: list[int]) -> str:
    """A hold in one line, as `heldWords` in `lib/studio-copy.ts` writes it: fixed (encastre), or the directions with Abaqus's name."""
    held = set(dofs)
    if held >= {1, 2, 3, 4, 5, 6}:
        return f"{region}: fixed (encastre)"
    if 2 not in held and held >= {1, 3, 4, 5, 6}:
        return f"{region}: free to move along the coupon only"
    named = next((name for of, name in ABAQUS_NAMES if of == held), None)
    words = list(dict.fromkeys(dof_word(d) for d in dofs))
    return f"{region}: held along {', '.join(words)}" + (f" ({named})" if named else "")


def support_line(support: dict[str, Any], labels: dict[str, str]) -> str:
    region, dofs, value = _text(support.get("region")), list(support.get("dofs") or []), _text(support.get("value")).strip()
    if not value:
        return held_line(region, dofs)
    dof = dofs[0] if dofs else 0
    if dof >= 4:
        return f"{region}: turned {value} rad about {'xyz'[dof - 4]}"
    return f"{region}: moved {value} {labels['length']} along {dof_word(dof)}"


def load_line(load: dict[str, Any], labels: dict[str, str]) -> str:
    region = _text(load.get("region"))
    if load.get("kind") == "pressure":
        pressure = _text(load.get("pressure")).strip() or "?"
        lifting = pressure.startswith("-")
        return f"{region}: pressure of {pressure} {labels['stress']}, {'lifting the plate' if lifting else 'pressing down on the plate'}"
    return f"{region}: force of {_text(load.get('total')).strip() or '?'} {labels['force']} along {dof_word(int(load.get('dof') or 0))}"


def region_options(form: dict[str, str], lists: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    """The regions a plate's supports and loads may name (`regionOptions`): the edges, the hole's ring with a hole, the face, the tabs with
    a tab length, and the boxes drawn."""
    plate = form_definition().get("plate", {})
    hole = _text(form.get("hole_diameter")).strip() != ""
    edges = [*plate.get("edges", []), *(plate.get("with_hole", ["Hole"]) if hole else [])]
    areas = [*plate.get("areas", ["Face"]), *(plate.get("with_tabs", ["Tab-Bottom", "Tab-Top"]) if _positive(form.get("tab_length")) else []),
             *[_text(r.get("name")) for r in lists["regions"] if _text(r.get("name"))]]
    return [*({"name": n, "kind": "edge"} for n in edges), *({"name": n, "kind": "area"} for n in areas)]


def _described(option: dict[str, str], form: dict[str, str], lists: dict[str, list[dict[str, Any]]], labels: dict[str, str]) -> dict[str, str]:
    """Where a region lies, in the plate's axes and the rows as written: its length runs along y and its width along x."""
    name, unit = option["name"], labels["length"]
    length, width, tab = (_text(form.get(k)).strip() for k in ("length", "width", "tab_length"))
    across = f"across the width{f' ({width} {unit})' if width else ''}"
    along = f"along the length{f' ({length} {unit})' if length else ''}"
    where = {
        "Edge-Bottom": ("end", f"the bottom end, at y = 0, {across}"),
        "Edge-Top": ("end", f"the top end, at y = {length or 'the length'}, {across}"),
        "Edge-Left": ("side", f"the left side, at x = 0, {along}"),
        "Edge-Right": ("side", f"the right side, at x = {width or 'the width'}, {along}"),
        "Hole": ("hole", "the edge of the hole"),
        "Face": ("area", "the whole face of the plate"),
        "Tab-Bottom": ("end", f"the tab at the bottom end, {tab} {unit} long"),
        "Tab-Top": ("end", f"the tab at the top end, {tab} {unit} long"),
    }.get(name)
    if where is None:
        box = next((r for r in lists["regions"] if _text(r.get("name")) == name), {})
        where = ("area", f"a box drawn on the face: x {_text(box.get('x0'))} to {_text(box.get('x1'))}, y {_text(box.get('y0'))} to "
                         f"{_text(box.get('y1'))} {unit}")
    return {"name": name, "kind": option["kind"], "role": where[0], "where": where[1]}


def regions(content: dict[str, Any], role: str = "all") -> list[dict[str, str]]:
    """A plate's regions with where each lies, all of them or those of one role (`ROLES`). The ends are what a pull along the plate's
    length acts on; the sides run along the length, so a pull there acts across the width."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}; got {role!r}")
    form, lists = form_of(content), lists_of(content)
    labels = unit_labels(form)
    found = [_described(o, form, lists, labels) for o in region_options(form, lists)]
    keep = {"all": lambda r: True, "ends": lambda r: r["role"] == "end", "sides": lambda r: r["role"] == "side",
            "edges": lambda r: r["kind"] == "edge", "areas": lambda r: r["kind"] == "area"}[role]
    return [r for r in found if keep(r)]


def read_setup(content: dict[str, Any]) -> dict[str, Any]:
    """The model as it stands, in its own units, for a reader that sees no page: what it is, its size, its regions with their roles, and
    what is held and loaded, one line each. Values are the rows as written; nothing is computed."""
    form, lists = form_of(content), lists_of(content)
    labels = unit_labels(form)
    test = _text(form.get("test")).strip()
    plate = test == plate_test()
    layup = [form[k].strip() for k in sorted((k for k in form if re.fullmatch(r"ply_\d+", k)), key=lambda k: int(k[4:])) if form[k].strip()]
    reading: dict[str, Any] = {
        "test": test or None, "is_plate": plate, "units": {"system": units_of(form), **{k: labels[k] for k in ("length", "force", "stress")}},
        "size": {k: _text(form.get(k)).strip() or None for k in ("length", "width", "tab_length", "hole_diameter") if _visible(k, form)},
        "material": _text(form.get("library")).strip() or (_text(form.get("own_name")).strip() and "own material") or None,
        "layup": {"plies_bottom_first": layup, "symmetric": _text(form.get("symmetric")).strip() or None},
        "element_size": _text(form.get("element_size")).strip() or None,
        "digest": content_digest(content),
    }
    if plate:
        reading |= {
            "regions": regions(content),
            "held": [support_line(s, labels) for s in lists["supports"]],
            "loaded": [load_line(l, labels) for l in lists["loads"]],
            "note": ("The plate's length runs along y. A pull or push along the length acts on its ends (Edge-Bottom and Edge-Top, or the "
                     "tabs there); Edge-Left and Edge-Right are its long sides, and a force on them acts across the width."),
        }
    else:
        reading["note"] = (f"This model is a {test or 'coupon not yet set up'}: it is held and loaded by its test's grips, through the "
                           "Loading rows. Supports and loads on named regions are a plate's.")
    return reading


# ----------------------------------------------------------------------------------------------------- changing the setup

@dataclass
class Changed:
    """What a set of changes makes of a setup: the content after, the lines of what changed, and the changes refused with the reason. A
    refused change leaves the setup as it was: every change is made, or none."""

    content: dict[str, Any]
    done: list[str] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.refused


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().replace("−", "-")
    if not NUMBER.match(text):
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _converted(value: Decimal, unit: Any, target: str) -> Decimal | str:
    """A value in a unit of the model's own system converted to the row's (`target`), by an exact power of ten; a unit of the other
    system, or of another quantity, is refused in words, as the chat refuses it (ADR-0061)."""
    written = _text(unit).strip()
    if not written:
        return value
    named = unit_named(written)
    if named == target:
        return value
    if named not in COUPON_UNITS or target not in COUPON_UNITS or COUPON_UNITS[named][0] != COUPON_UNITS[target][0]:
        return f"{written} is not a unit of this value, which the model states in {target}"
    if COUPON_UNITS[named][1] != COUPON_UNITS[target][1]:
        return (f"{written} belongs to {SYSTEM_WORDS[COUPON_UNITS[named][1]]}, and this model is stated in "
                f"{SYSTEM_WORDS[COUPON_UNITS[target][1]]}: give it in {target}")
    return value * COUPON_UNITS[named][2] / COUPON_UNITS[target][2]


def _angle(value: Decimal, unit: Any) -> Decimal | str:
    written = _text(unit).strip().lower()
    if not written:
        return value
    if written not in ANGLE_UNITS:
        return f"{_text(unit)} is not an angle's unit: give the turn in rad or degrees"
    factor = ANGLE_UNITS[written]
    if factor is not None:
        return value * factor
    return Decimal(repr(float(value) * math.pi / 180))  # as the page turns degrees into radians


def _js_written(value: Decimal) -> str:
    """A value as the lists keep it: plain digits, at most twelve significant figures, as the page's `written`."""
    return _written(Decimal(f"{value:.12g}") if value != 0 else Decimal(0))


def _row_change(change: dict[str, Any], form: dict[str, str]) -> tuple[str, str] | str:
    """A row set to a value: the row's new text and the line that says so, or why it cannot be set."""
    key = _text(change.get("key")).strip()
    f = _field(key)
    if f is None:
        return f"{key or 'the row'} is not a row of the form"
    if key in FIXED_ROWS or key in HIDDEN_KEYS or key.endswith(HIDDEN_ENDINGS):
        return f"{f['label']} is set on the page, not by a change"
    if not _visible(key, form):
        return f"{f['label']} is not a row of a {_text(form.get('test')) or 'model with no test yet'}"
    raw = change.get("value")
    text = "" if raw is None else _text(raw).strip().replace("−", "-")
    labels = unit_labels(form)
    if text == "":
        if f.get("required"):
            return f"{f['label']} is required and cannot be left blank"
        new = ""
    elif f["kind"] in ("number", "whole", "angle"):
        number = _decimal(text)
        if number is None:
            return f"{text!r} is not a number"
        if f["kind"] == "angle":
            if _text(change.get("unit")).strip() and _text(change.get("unit")).strip().lower() not in ("deg", "degs", "degree", "degrees", "°"):
                return f"a ply's angle is in degrees, not {change.get('unit')}"
            if abs(number) > 90:
                return f"{text} is not an angle from -90 to 90 degrees"
        elif f.get("unit") == "amount" and _text(change.get("unit")).strip():
            # a coupon's Value is a travel under displacement and a force under force (the Loading type row, set first)
            control = _text(form.get("control")).strip()
            quantity = COUPON_UNITS.get(unit_named(_text(change.get("unit"))) or "", ("",))[0]
            wanted = "force" if control == "force" else "length" if control == "displacement" else None
            if wanted is None:
                return f"{f['label']} is a travel or a force by the Loading type, which is not set: set the Loading type first"
            if quantity != wanted:
                return (f"{f['label']} is a {'force' if wanted == 'force' else 'travel'} under {control} loading, and {change.get('unit')} is not: "
                        f"set the Loading type to {'displacement' if wanted == 'force' else 'force'} first, or give the value in {labels[wanted]}")
            converted = _converted(number, change.get("unit"), labels[wanted])
            if isinstance(converted, str):
                return converted
            number = converted
        elif f.get("unit") in labels:
            converted = _converted(number, change.get("unit"), labels[f["unit"]])
            if isinstance(converted, str):
                return converted
            number = converted
        elif _text(change.get("unit")).strip():
            return f"{f['label']} is a pure number and carries no unit"
        if f["kind"] == "whole" and number != number.to_integral_value():
            return f"{f['label']} takes a whole number"
        new = _written(number)
    elif f["kind"] == "list":
        if f.get("words") and text not in f["words"]:
            return f"{text!r} is not one of {f['label']}'s choices: {', '.join(f['words'])}"
        new = text
    else:
        if len(text) > MAX_TEXT:
            return f"{f['label']} takes at most {MAX_TEXT} characters"
        new = text
    label = f.get("labels", {}).get(units_of(form), f["label"])
    before = _text(form.get(key)).strip()
    if before == new:
        return f"{label} is already {new or 'blank'}"
    form[key] = new
    return new, f"{label}: {before or 'blank'} → {new or 'blank'}"


def change_setup(content: dict[str, Any], changes: list[dict[str, Any]]) -> Changed:
    """The setup after the changes, made in order on a copy. Each change is a dict with `action`, one of `ACTIONS`:

    - hold: `region`, `dofs` (1 to 3 along x, y, z; 4 to 6 about them). It takes the place of the region's hold; a set move of another
      direction stays.
    - move: `region`, `dof`, `value` (and `unit`): the region moved along a direction (1 to 3) or turned about one (4 to 6) by a set amount;
      it takes the place of the region's force along that direction.
    - force: `region`, `value` (and `unit`), and `dof` (1 to 3) with the value signed, or `sense` tension or compression on a straight edge,
      which takes its direction and sign from the edge's outward normal. The total over the region; it takes the place of the region's
      force or set move along that direction, and is refused along a direction the region is held in (the support would carry it).
    - pressure: `region` (an area), `value` (and `unit`): positive presses down on the plate. It takes the place of the region's pressure.
    - free: `region`: every hold and move on it removed. unload: `region`: every load on it removed.
    - row: `key`, `value` (and `unit`): a row of the form set, or left blank with an empty value.

    A value is in the model's own units unless a unit of its own system is given; a unit of the other system is refused, never converted.
    """
    after = copy.deepcopy(content)
    form, lists = form_of(after), lists_of(after)
    labels = unit_labels(form)
    plate = form.get("test") == plate_test()
    out = Changed(content=content)
    if not isinstance(changes, list) or not changes:
        out.refused.append({"change": 0, "reason": "no change was given"})
        return out
    if len(changes) > MAX_CHANGES:
        out.refused.append({"change": 0, "reason": f"at most {MAX_CHANGES} changes at a time; {len(changes)} were given"})
        return out
    done: list[str] = []

    for index, change in enumerate(changes, start=1):
        def refuse(reason: str, index: int = index) -> None:
            out.refused.append({"change": index, "reason": reason})

        if not isinstance(change, dict) or change.get("action") not in ACTIONS:
            refuse(f"the action must be one of {', '.join(ACTIONS)}")
            continue
        action = change["action"]
        if action == "row":
            made = _row_change(change, form)
            if isinstance(made, str):
                refuse(made)
            else:
                done.append(made[1])
            continue
        if not plate:
            refuse(f"supports and loads on named regions are a plate's, and this model is a {form.get('test') or 'coupon with no test yet'}: "
                   "its grips and pull are set by its Loading rows")
            continue
        options = {o["name"]: o["kind"] for o in region_options(form, lists)}
        region = _text(change.get("region")).strip()
        if region not in options:
            refuse(f"{region or 'no region'} is not a region of this plate; it has {', '.join(options)}")
            continue

        if action == "free":
            if not any(s.get("region") == region for s in lists["supports"]):
                refuse(f"nothing is held on {region}")
                continue
            lists["supports"] = [s for s in lists["supports"] if s.get("region") != region]
            done.append(f"{region}: no longer held")
            continue
        if action == "unload":
            if not any(l.get("region") == region for l in lists["loads"]):
                refuse(f"no load is on {region}")
                continue
            lists["loads"] = [l for l in lists["loads"] if l.get("region") != region]
            done.append(f"{region}: load removed")
            continue
        if action == "hold":
            dofs = change.get("dofs")
            if not isinstance(dofs, list) or not dofs or any(isinstance(d, bool) or d not in (1, 2, 3, 4, 5, 6) for d in dofs) or len(set(dofs)) != len(dofs):
                refuse("a hold names the directions it holds, each once, from 1 to 6 (1 to 3 along x, y, z; 4 to 6 about them)")
                continue
            dofs = sorted(int(d) for d in dofs)
            moving = [s for s in lists["supports"] if s.get("region") == region and _text(s.get("value")).strip() and (s.get("dofs") or [0])[0] not in dofs]
            lists["supports"] = [*(s for s in lists["supports"] if s.get("region") != region), *moving, {"region": region, "dofs": dofs, "value": ""}]
            done.append(held_line(region, dofs))
            continue

        number = _decimal(change.get("value"))
        if number is None:
            refuse(f"{_text(change.get('value')) or 'no value'} is not a number")
            continue
        if number == 0:
            refuse("a value of zero changes nothing: a move of zero is a hold, and a load of zero is no load")
            continue

        if action == "pressure":
            if options[region] != "area":
                refuse(f"a pressure acts on an area, and {region} is an edge")
                continue
            converted = _converted(number, change.get("unit"), labels["stress"])
            if isinstance(converted, str):
                refuse(converted)
                continue
            pressure = _js_written(converted)
            lists["loads"] = [*(l for l in lists["loads"] if not (l.get("region") == region and l.get("kind") == "pressure")),
                              {"region": region, "kind": "pressure", "pressure": pressure}]
            done.append(load_line({"region": region, "kind": "pressure", "pressure": pressure}, labels))
            continue

        if action == "force":
            sense, dof = change.get("sense"), change.get("dof")
            if sense is not None and dof is not None:
                refuse("a force takes a direction or a sense (tension or compression), not both")
                continue
            if sense is not None:
                if sense not in ("tension", "compression"):
                    refuse("a force's sense is tension or compression")
                    continue
                if region not in EDGE_NORMAL:
                    refuse(f"{sense} has no one direction on {region}: give the direction, 1, 2 or 3 (x, y or z)")
                    continue
                dof, outward = EDGE_NORMAL[region]
                number = abs(number) * (outward if sense == "tension" else -outward)
            elif isinstance(dof, bool) or dof not in (1, 2, 3):
                refuse("a force acts along a direction: 1, 2 or 3 (x, y or z)")
                continue
            dof = int(dof)
            converted = _converted(number, change.get("unit"), labels["force"])
            if isinstance(converted, str):
                refuse(converted)
                continue
            total = _js_written(converted)
            if any(s.get("region") == region and not _text(s.get("value")).strip() and dof in (s.get("dofs") or []) for s in lists["supports"]):
                refuse(f"{region} is held along {dof_word(dof)}, so a force along {dof_word(dof)} there would go into the support: "
                       f"free {region} or hold it along other directions first")
                continue
            # one way of driving a direction of a region: the force takes the place of a set move along it, which would otherwise carry it
            moves = [s for s in lists["supports"] if s.get("region") == region and _text(s.get("value")).strip() and (s.get("dofs") or [0])[0] == dof]
            lists["supports"] = [s for s in lists["supports"] if not any(s is m for m in moves)]
            lists["loads"] = [*(l for l in lists["loads"] if not (l.get("region") == region and l.get("kind") == "force" and l.get("dof") == dof)),
                              {"region": region, "kind": "force", "dof": dof, "total": total}]
            done.append(load_line({"region": region, "kind": "force", "dof": dof, "total": total}, labels) + (f" ({sense})" if sense else "")
                        + (f", in place of its move of {_text(moves[-1].get('value')).strip()} {labels['length']} along {dof_word(dof)}" if moves else ""))
            continue

        # move: a set displacement or turn, a boundary condition with a value
        dof = change.get("dof")
        if isinstance(dof, bool) or dof not in (1, 2, 3, 4, 5, 6):
            refuse("a move names one direction: 1 to 3 along x, y, z, or 4 to 6 about them")
            continue
        dof = int(dof)
        converted = _angle(number, change.get("unit")) if dof >= 4 else _converted(number, change.get("unit"), labels["length"])
        if isinstance(converted, str):
            refuse(converted)
            continue
        moved = _js_written(converted)
        on = [s for s in lists["supports"] if s.get("region") == region and dof in (s.get("dofs") or [])]
        kept = [s for s in lists["supports"] if s.get("region") != region or dof not in (s.get("dofs") or [])]
        kept += [{**s, "dofs": [d for d in s["dofs"] if d != dof]} for s in on if not _text(s.get("value")).strip() and len(s["dofs"]) > 1]
        lists["supports"] = [*kept, {"region": region, "dofs": [dof], "value": moved}]
        # and a set move takes the place of a force of the region along its direction, which the move would carry
        forces = [l for l in lists["loads"] if l.get("region") == region and l.get("kind") == "force" and l.get("dof") == dof]
        lists["loads"] = [l for l in lists["loads"] if not any(l is f for f in forces)]
        done.append(support_line({"region": region, "dofs": [dof], "value": moved}, labels)
                    + (f", in place of its force of {_text(forces[-1].get('total')).strip()} {labels['force']} along {dof_word(dof)}" if forces else ""))

    if out.refused:
        return out
    after["form"] = {**(after.get("form") or {}), **form}
    if plate:
        after["plate"] = {**(after.get("plate") or {}), **lists}
    out.content, out.done = after, done
    return out
