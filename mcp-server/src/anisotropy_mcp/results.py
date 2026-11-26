"""Reading a result the API returned (ADR-0107): the value of a quantity at an element and a ply, and where a quantity is largest.

These are the page's own rules (`lib/result-question.ts` and `lib/studio-fields.ts`, ADR-0099 and ADR-0100), written again here because
a live solve's fields are held by whoever asked for them, the page there and this server here, and the API keeps none. A value is picked
out of the arrays the fea package wrote: nothing is computed, converted, averaged or rounded. Plies are counted from the bottom face,
starting at 1; an element is named by its own number in its part, the number after the last dot of its label; values are the element
centroid's, in each ply's fibre axes. A test holds the extremes found here to the ones the package itself wrote in the summary.
"""

from __future__ import annotations

import math
from typing import Any

# The probe table's columns by their common names, in its order: stresses in the ply's fibre axes, the invariants, the strains.
COLUMNS = ("S11", "S22", "S12", "Mises", "Tresca", "Max. Principal", "Mid. Principal", "Min. Principal", "Pressure", "E11", "E22", "E12")
WORDS = {
    "S11": "stress along the fibres", "S22": "stress across the fibres", "S12": "in-plane shear stress", "Mises": "Mises stress",
    "Tresca": "Tresca stress", "Max. Principal": "largest principal stress", "Mid. Principal": "middle principal stress",
    "Min. Principal": "smallest principal stress", "Pressure": "pressure", "E11": "strain along the fibres",
    "E22": "strain across the fibres", "E12": "engineering shear strain",
}
STRAINS = ("E11", "E22", "E12")
INVARIANTS = {"Tresca": "tresca", "Max. Principal": "max_principal", "Mid. Principal": "mid_principal", "Min. Principal": "min_principal",
              "Pressure": "pressure"}
UNSIGNED = frozenset({"S12", "E12", "Mises", "Tresca"})  # no sign to speak of: the extreme is the largest magnitude, whatever is asked
SENSES = ("largest", "smallest", "magnitude")
NOTE = "Element centroids, no averaging, each ply in its own fibre axes."


class NotInResult(Exception):
    """The question names something these results do not hold; the message says what they do hold."""


def has_faces(fields: dict) -> bool:
    """Whether the package wrote both faces of every ply (a shell solve); a membrane solve has one value per ply."""
    return bool(fields["mesh"].get("faces"))


def on_face(fields: dict, value: Any, face: int) -> Any:
    return value[min(max(face, 0), len(value) - 1)] if has_faces(fields) else value


def number_of(label: str) -> str:
    """An element's own number in its part: "Strip-1.178" is element 178."""
    return label[label.rfind(".") + 1:]


def unit_of(fields: dict, column: str) -> str:
    return "-" if column in STRAINS else fields.get("labels", {}).get("stress", "")


def value_of(fields: dict, column: str, element: int, ply: int, face: int) -> float | None:
    """One stored value: `ply` counted from 1, `element` by its place in the mesh's order. None where the package wrote none."""
    per_ply = fields["element"]["ply"]
    if column in ("S11", "S22", "S12"):
        found = on_face(fields, per_ply["stress_12"][element][ply - 1], face)[("S11", "S22", "S12").index(column)]
    elif column in STRAINS:
        found = on_face(fields, per_ply["strain_12"][element][ply - 1], face)[STRAINS.index(column)]
    elif column == "Mises":
        found = on_face(fields, per_ply["mises"][element][ply - 1], face)
    else:
        table = (per_ply.get("invariants") or {}).get(INVARIANTS[column])
        found = None if table is None else on_face(fields, table[element][ply - 1], face)
    return found if isinstance(found, (int, float)) and not isinstance(found, bool) and math.isfinite(found) else None


def plies_of(fields: dict) -> list[dict]:
    return [{"ply": i + 1, "angle": angle} for i, angle in enumerate(fields["mesh"]["angles"])]


def sets_of(fields: dict, element: int) -> list[str]:
    return [name for name, members in fields["mesh"].get("element_sets", {}).items() if element in members]


def at_grips(fields: dict) -> set[int]:
    """The elements with a gripped node: the row along each tab line, the clamped edge, where stress grows as the mesh is refined (ADR-0066)."""
    gripped = {node for name, nodes in fields["mesh"].get("node_sets", {}).items() if name.startswith("Grip-") for node in nodes}
    return {e for e, quad in enumerate(fields["mesh"]["quads"]) if gripped and any(node in gripped for node in quad[:4])}


def gauge_section(fields: dict) -> list[int] | None:
    """The gauge section as the package reads it: the elements it wrote with the fields (`mesh.gauge_elements`, ADR-0108: the `Gauge`
    set at least the stand-off from each tab line), so nothing is derived here. A result solved before that record holds no list and
    is read by its own rule (ADR-0085): the `Gauge` set less the elements at a gripped node. None for a model without a gauge section."""
    if "gauge_elements" in fields["mesh"]:
        return list(fields["mesh"]["gauge_elements"] or []) or None
    gauge = fields["mesh"].get("element_sets", {}).get("Gauge")
    grips = at_grips(fields)
    return [e for e in gauge if e not in grips] if gauge and grips else None


def asked_plies(fields: dict, plies: list[int] | None) -> list[int]:
    count = fields["mesh"]["plies"]
    for ply in plies or []:
        if isinstance(ply, bool) or not isinstance(ply, int) or ply < 1 or ply > count:
            raise NotInResult(f"This laminate has {count} {'ply' if count == 1 else 'plies'}, counted from the bottom face; there is no ply {ply}.")
    return sorted(set(plies)) if plies else list(range(1, count + 1))


def asked_columns(quantities: list[str] | None) -> list[str]:
    unknown = [q for q in quantities or [] if q not in COLUMNS]
    if unknown:
        raise NotInResult(f"No quantity {', '.join(repr(q) for q in unknown)}. The quantities are: {', '.join(COLUMNS)}.")
    return [c for c in COLUMNS if c in quantities] if quantities else list(COLUMNS)


def element_index(fields: dict, element: int) -> int:
    """An element's place in the mesh from its number; refused when the model has none of that number, or more than one part has it."""
    labels = fields["mesh"]["element_labels"]
    found = [i for i, label in enumerate(labels) if number_of(label) == str(element)]
    if not found:
        numbers = [int(n) for n in map(number_of, labels) if n.isdigit()]
        span = f" Its elements are numbered {min(numbers)} to {max(numbers)}." if numbers else ""
        raise NotInResult(f"This model has no element {element}.{span}")
    if len(found) > 1:
        raise NotInResult(f"More than one part has an element {element}: {', '.join(labels[i] for i in found)}.")
    return found[0]


def failure_at(fields: dict, element: int, ply: int, face: int) -> dict:
    """What each criterion says of one ply at one element, as the package wrote it: the strength ratio R, the failure index and the mode."""
    modes = fields["element"].get("modes", [])
    out = {}
    for criterion, written in fields["element"].get("failure", {}).items():
        mode = on_face(fields, written["mode"][element][ply - 1], face)
        out[criterion] = {"R": on_face(fields, written["ratio"][element][ply - 1], face),
                          "index": on_face(fields, written["index"][element][ply - 1], face),
                          "mode": modes[mode] if isinstance(mode, int) and 0 <= mode < len(modes) else None}
    return out


def values_at(fields: dict, element: int, plies: list[int] | None = None, quantities: list[str] | None = None) -> dict:
    """The quantities asked for at one element, a row per ply (and per face where the package wrote faces)."""
    rows_of = asked_plies(fields, plies)
    columns = asked_columns(quantities)
    at = element_index(fields, element)
    faces = fields["mesh"]["faces"] if has_faces(fields) else [None]
    rows = []
    for ply in rows_of:
        for f, face in enumerate(faces):
            row = {"ply": ply, "angle": fields["mesh"]["angles"][ply - 1], "face": face,
                   "values": {column: value_of(fields, column, at, ply, f) for column in columns}}
            failure = failure_at(fields, at, ply, f)
            if failure:
                row["failure"] = failure
            rows.append(row)
    centroid = fields["element"]["centroids"][at]
    return {"element": number_of(fields["mesh"]["element_labels"][at]), "label": fields["mesh"]["element_labels"][at],
            "centroid": [centroid[0], centroid[1]], "length_unit": fields.get("labels", {}).get("length", ""), "regions": sets_of(fields, at),
            "at_a_grip": at in at_grips(fields), "units": {column: unit_of(fields, column) for column in columns}, "rows": rows,
            "note": NOTE + (" Bottom and top face of each ply." if has_faces(fields) else " The same through each ply's thickness.")
            + (" R is the multiple of the applied loading at which the ply fails here by that criterion; index is the failure index." if rows and "failure" in rows[0] else "")}


def away_from_corners(fields: dict) -> list[int] | None:
    """A plate away from its held corners, as the package reads it (`mesh.away_elements`, ADR-0108 amendment 2): its answer's elements,
    at least the stand-off from each point where a held run on an edge ends. None for a model with a gauge section, without a held corner,
    or solved before it."""
    return list(fields["mesh"].get("away_elements") or []) or None


def region_of(fields: dict, region: str) -> tuple[list[int], str]:
    """The elements a region names and its words: "default" is the gauge section where the model has one, a plate away from its held
    corners where it has one, else the whole model."""
    sets = fields["mesh"].get("element_sets", {})
    gauge = gauge_section(fields)
    if region == "gauge":
        if not gauge:
            raise NotInResult("This model has no gauge section between grips. Ask for the whole model, or name an element.")
        return gauge, "the gauge section"
    if region == "default":
        if gauge:
            return gauge, "the gauge section"
        away = away_from_corners(fields)
        return (away, "the plate away from its held corners") if away else (list(range(len(fields["mesh"]["element_labels"]))), "the whole model")
    if region == "whole":
        return list(range(len(fields["mesh"]["element_labels"]))), "the whole model"
    if region not in sets:
        raise NotInResult(f"This model has no region {region!r}. Ask for default, gauge or whole" + (f", or one of its regions: {', '.join(sets)}." if sets else "."))
    return list(sets[region]), f"the region {region}"


def extremes(fields: dict, quantities: list[str], sense: str = "magnitude", region: str = "default", plies: list[int] | None = None) -> dict:
    """Where each quantity is largest over a region: per quantity, each ply's extreme and the ply that holds the overall one. One stored
    value is picked; the first element in the mesh's order holds a tie between elements, and plies tied at the very same value are named."""
    if sense not in SENSES:
        raise NotInResult(f"No sense {sense!r}. Ask for largest (with its sign, the most tensile), smallest (the most compressive) or magnitude.")
    rows_of = asked_plies(fields, plies)
    columns = asked_columns(quantities)
    members, words = region_of(fields, region)
    faces = fields["mesh"]["faces"] if has_faces(fields) else [None]
    labels = fields["mesh"]["element_labels"]
    grips = at_grips(fields)
    found = []
    for column in columns:
        read_as = "magnitude" if column in UNSIGNED else sense
        score = {"largest": lambda v: v, "smallest": lambda v: -v, "magnitude": abs}[read_as]
        rows = []
        for ply in rows_of:
            hit = None
            for f, face in enumerate(faces):
                for e in members:
                    value = value_of(fields, column, e, ply, f)
                    if value is not None and (hit is None or score(value) > score(hit[0])):
                        hit = (value, e, face)
            if hit is not None:
                rows.append({"ply": ply, "angle": fields["mesh"]["angles"][ply - 1], "face": hit[2], "value": hit[0], "at": hit[1]})
        if not rows:
            continue
        best = max(range(len(rows)), key=lambda i: (score(rows[i]["value"]), -i))  # the first ply holds a tie, as on the page
        top = rows[best]
        centroid = fields["element"]["centroids"][top["at"]]
        found.append({
            "quantity": column, "what": WORDS[column], "sense": read_as, "unit": unit_of(fields, column), "value": top["value"],
            "ply": top["ply"], "angle": top["angle"], "face": top["face"], "element": number_of(labels[top["at"]]),
            "centroid": [centroid[0], centroid[1]], "regions": sets_of(fields, top["at"]), "at_a_grip": top["at"] in grips,
            "tied_plies": [row["ply"] for i, row in enumerate(rows) if i != best and score(row["value"]) == score(top["value"])],
            "per_ply": [{"ply": row["ply"], "angle": row["angle"], "face": row["face"], "value": row["value"], "element": number_of(labels[row["at"]])}
                        for row in rows],
        })
    if not found:
        raise NotInResult("These results hold no value of that quantity.")
    out = {"region": words, "elements": len(members), "length_unit": fields.get("labels", {}).get("length", ""), "extremes": found, "note": NOTE}
    if any(block["at_a_grip"] for block in found):
        out["grip_note"] = ("An extreme marked at_a_grip sits at the clamped edge of a grip, where the stress grows as the mesh is refined: "
                            "report it apart from the gauge section's values.")
    return out


def offer(fields: dict) -> dict:
    """What can be asked of these results: the quantities they hold, the plies and their angles, the regions and how the elements are numbered."""
    labels = fields["mesh"]["element_labels"]
    numbers = [int(n) for n in map(number_of, labels) if n.isdigit()]
    held = [c for c in COLUMNS if c not in INVARIANTS or (fields["element"]["ply"].get("invariants") or {}).get(INVARIANTS[c]) is not None]
    return {"quantities": held, "plies": plies_of(fields), "faces": fields["mesh"].get("faces") or None, "elements": len(labels),
            "element_numbers": [min(numbers), max(numbers)] if numbers else None, "regions": list(fields["mesh"].get("element_sets", {})),
            "gauge_section": gauge_section(fields) is not None, "units": fields.get("labels", {})}
