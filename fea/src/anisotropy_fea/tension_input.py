"""The tension coupon from its material and layup: the standard and our rules choose the rest, and say so (ADR-0090).

The studio's tension screen asks the engineer for two things, the material and the layup, and offers four to change (their own
material constants, the pull or force, the coupon's size and tabs, the element size), and G13 and G23 for a library material, which
the library does not give (ADR-0111 amendment 5). Every other row of the form is chosen here,
each with the reason it was chosen, so the values file the setup check reads is complete and the page can show "How we built it".
A row the engineer gave is never changed. Nothing is chosen silently (ADR-0003): each choice is in the list this returns, which the
checklist, the job's result and the package carry.

    values, built = complete_tension({"input": "tension", "library": "im7-8552", "angles": [45, 0, -45, 90], "symmetric": "yes"})

Only a values file that says `"input": "tension"` is completed; the Excel form and the full panels keep their own strict rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from anisotropy_engine.library import find_dataset, library_material

from .spec import normalised_angle
from .standards import astm_d3039
from .standards.profile import Subject
from .units import UNIT_LABEL, UNIT_SYSTEMS, from_si

INPUT = "tension"  # the values file's "input" word for the tension screen
PLATE_INPUT = "plate"  # the same for a plate set up on the model tree: its size and what holds and loads it are the engineer's (ADR-0089 amendment 8)
PLATE_TEST = "plate"
PLATE_LONG, PLATE_SHORT, PLATE_MOST = 50, 12, 20_000  # the element size chosen for a plate: elements along its longer side, across its shorter, and at most
TEST = "unnotched tension"
UNITS = "mm-MPa"
D3039 = astm_d3039.DESIGNATION
GRIP_LENGTH_MM = 56.0  # D3039 Table 2 gives no grip length for a balanced and symmetric laminate; ours, as in fea/checks/d3039-im7-8552
EXTENSOMETER_MM = 25.0  # within D3039 §7.3.2's 10 to 50 mm, as in the check
PULL_MM = 1.0
ELEMENT_SIZE_MM = 2.0
MM = 1e-3
SIZE_ROWS = ("length", "width", "tab_length")  # the size Table 2 gives, row by row
SIZE_WORDS = {"length": "the length", "width": "the width", "tab_length": "the tab length"}


@dataclass(frozen=True)
class Built:
    """One row the software chose: the row's key, the value written, and why."""

    row: str
    value: Any
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


@dataclass(frozen=True)
class Transverse:
    """G13 and G23 estimated for a library material, in MPa to 0.01 MPa, each with why, and the rule in one line for the page."""

    G13: float
    G23: float
    reasons: dict[str, str]
    rule: str


def transverse_estimates(material_id: str) -> Transverse:
    """G13 and G23 for a library material, which the library does not give: G13 = G12, and for a tape G23 = E2 / 3, for a fabric
    G23 = G12. Only CalculiX's brick and the shell's transverse shear read them; an in-plane pull of a symmetric layup does not load them.
    The tension coupon writes them where the engineer gives none, and the Material step shows them as estimates before any check
    (ADR-0111 amendment 5)."""
    lamina = library_material(material_id).lamina
    g12, e2 = lamina.G12 / 1e6, lamina.E2 / 1e6  # Pa to MPa, written to 0.01 MPa
    record = find_dataset(material_id, None)
    if str(record.get("architecture") or "").lower().startswith("unidirectional"):
        return Transverse(round(g12, 2), round(e2 / 3.0, 2), {
            "G13": "not in the library: G13 = G12, a usual estimate; an in-plane pull does not load it",
            "G23": "not in the library: G23 = E2 / 3, a usual estimate for a tape; an in-plane pull does not load it"},
            "G13 = G12 and G23 = E2 / 3, the usual estimates for a tape")
    return Transverse(round(g12, 2), round(g12, 2), {
        "G13": "not in the library: G13 = G12, a usual estimate; an in-plane pull does not load it",
        "G23": "not in the library, and no estimate holds for a fabric: taken equal to G12 so the model builds; an in-plane pull does not load it"},
        "G13 = G12, the usual estimate, and G23 = G12 so the model builds, as no estimate holds for a fabric")


def _angles(data: dict) -> list[float] | None:
    """Every ply's angle, bottom first, both halves of a symmetric stack; None when the layup is not readable here (the check names it)."""
    listed = data.get("angles")
    if listed is None:
        listed = [data[f"ply_{i}"] for i in range(1, 33) if not _blank(data.get(f"ply_{i}"))]
    try:
        angles = [float(a) for a in listed]
    except (TypeError, ValueError):
        return None
    symmetric = str(data.get("symmetric", "")).strip().lower()
    if symmetric in ("yes", "true") or data.get("symmetric") is True:
        angles = angles + angles[::-1]
    return angles or None


def _record(data: dict) -> dict | None:
    """The library record of the material picked, or None for the engineer's own constants or a name the check will refuse."""
    material_id = data.get("library")
    if _blank(material_id):
        return None
    try:
        return find_dataset(str(material_id).strip(), None)
    except (KeyError, ValueError):
        return None


def d3039_class(data: dict) -> astm_d3039.Preset | None:
    """The D3039 Table 2 class of the layup (0° or 90° unidirectional, balanced and symmetric), or None when it is in none of them."""
    angles = _angles(data)
    if not angles:
        return None
    record = _record(data)
    subject = Subject(kind="unnotched_tension", units=UNITS, length=0.0, width=0.0, tab_length=0.0, hole_diameter=None,
                      angles=tuple(normalised_angle(a) for a in angles), ply_thickness=0.0,
                      family=record.get("family") if record else None, architecture=record.get("architecture") if record else None)
    return astm_d3039.classify(subject)


def _in_units(value: float, kind: str, units: str) -> float:
    """A choice of ours, made in mm and MPa, in the coupon's units: the same value converted, to six significant figures in another system
    (56 mm is 2.20472 in), so the coupon is the one it would be in mm (ADR-0090 amendment 2)."""
    if units == UNITS:
        return value
    return float(f"{from_si(value * (MM if kind == 'length' else 1e6), kind, units):.6g}")


def _length_words(mm: float, units: str) -> str:
    """A length of ours in words, in the coupon's units with the millimetres it was chosen in: "56 mm", or "2.20472 in (56 mm)"."""
    if units == UNITS:
        return f"{mm:g} mm"
    return f"{_in_units(mm, 'length', units):g} {UNIT_LABEL[units]['length']} ({mm:g} mm)"


def complete_tension(data: dict, today: date | None = None) -> tuple[dict, tuple[Built, ...]]:
    """The values of a tension coupon with every row the engineer was not asked for chosen, and the list of those choices.

    `data` is the values file without its "input" key; the rows it holds are kept as they are. Under D3039, each size row left blank comes
    from Table 2 on its own (ADR-0090 amendment 1). A layup in no D3039 Table 2 class, or a coupon under no standard, gets no size: the
    check then asks for the length, width and tab length by row. Every number chosen is in the coupon's units, the ones the screen sent
    or mm-MPa (ADR-0090 amendment 2): a coupon stated in inches gets Table 2's own inch sizes, and our choices converted."""
    out = dict(data)
    built: list[Built] = []
    stated = str(out.get("units") or "").strip()
    units = stated if stated in UNIT_SYSTEMS else UNITS  # a system the form does not know is refused by the check, by its row

    def choose(key: str, value: Any, reason: str) -> None:
        if _blank(out.get(key)):
            out[key] = value
            built.append(Built(key, value, reason))

    choose("test", TEST, "the test this workspace runs")
    choose("units", UNITS, "results and files use these units")
    choose("standard", D3039, "the standard of the unnotched tension test of a polymer-matrix composite")
    under_d3039 = str(out["standard"]).strip().lower() == D3039.lower()
    choose("filled_by", "workspace", "the coupon was set up in the workspace")
    choose("date", (today or date.today()).isoformat(), "the day the coupon was set up")

    # Each size row left blank is chosen on its own (ADR-0090 amendment 1): a width typed under Change settings keeps Table 2's length and
    # the grip length, where any one typed row once dropped all three and the check then asked for the other two.
    given = [key for key in SIZE_ROWS if not _blank(out.get(key))]
    size_given = bool(given)
    preset = d3039_class(out) if under_d3039 and len(given) < len(SIZE_ROWS) else None
    if preset is not None:
        sizes = {row: value for row, value in preset.values_in(units).items() if row in SIZE_ROWS}
        tab = sizes.get("tab_length", _in_units(GRIP_LENGTH_MM, "length", units))
        why = f"{D3039}, Table 2, {preset.label}"
        choose("width", sizes["width"], why)
        choose("length", sizes["length"], why)
        choose("tab_length", tab, why if "tab_length" in sizes else
               f"{why}: gripped through emery cloth, with no tab length given; {_length_words(GRIP_LENGTH_MM, units)} is the software's choice")
        grip = "" if "tab_length" in sizes or "tab_length" in given else (f"; the {_length_words(GRIP_LENGTH_MM, units)} grip length is the "
                                                                          "software's choice, since Table 2 gives none for this class")
        if given:
            yours = " and ".join(SIZE_WORDS[key] for key in given)
            choose("size_from", f"{yours} as you gave, the rest from {why}{grip}; a deviation from {D3039} Table 2 is reported, never refused",
                   "the rest of the size was chosen from the standard")
        else:
            choose("size_from", why + grip, "where the size comes from")
    elif size_given:
        choose("size_from", "the dimensions you gave" + (f": a deviation from {D3039} Table 2 is reported, never refused" if under_d3039 else ""),
               "the size was given under Change settings")
    else:  # a layup in no Table 2 class, or no standard: the size is the engineer's to give, and the check asks for it by row
        choose("size_from", "the dimensions you give" + (f": the layup is in no {D3039} Table 2 class" if under_d3039 else ""),
               "no size could be chosen, so the length, width and tab length are asked for under Change settings")

    choose("strain_device", "extensometer", f"strain is measured over a gauge length at mid-length ({D3039} §7.3)")
    choose("strain_length", _in_units(EXTENSOMETER_MM, "length", units),
           f"{_length_words(EXTENSOMETER_MM, units)}, within {D3039} §7.3.2's 10 to 50 mm, centred on the coupon")
    choose("grips", "nodal", "every node of each tab is held; the top tab moves")  # the screen shows the value as "Clamped"
    choose("region", "tabs", "the grips hold the whole tab")
    if _blank(out.get("value")):
        choose("control", "displacement", "the top grip moves; the bottom one is held")
        choose("value", _in_units(PULL_MM, "length", units), "the model is linear, so R, the loading at first-ply failure, does not depend on it")
    choose("element_size", _in_units(ELEMENT_SIZE_MM, "length", units), "a structured mesh, with node rows at the tab lines and at the extensometer's ends; the analysis "
           "also checks the result on finer meshes")
    record = _record(out)
    if record is not None:  # the library gives no G13 or G23 (only CalculiX's brick and the Abaqus shell's transverse shear read them)
        estimate = transverse_estimates(str(out["library"]).strip())
        choose("G13", _in_units(estimate.G13, "stress", units), estimate.reasons["G13"])
        choose("G23", _in_units(estimate.G23, "stress", units), estimate.reasons["G23"])
    elif not _blank(out.get("own_G12")):
        choose("G13", out["own_G12"], "not given: G13 = G12, a usual estimate; an in-plane pull does not load it")
        choose("G23", out["own_G12"], "not given: taken equal to G12 so the model builds; an in-plane pull does not load it")
    strengths = ("own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6")
    if record is None and any(_blank(out.get(key)) for key in strengths):
        choose("criteria", "none", "not all five strengths are given, so no first-ply failure criterion can be judged")
    else:
        choose("criteria", "all", "all criteria the material's strengths allow")
    return out, tuple(built)


def _plate_element_size(length: Any, width: Any) -> float | None:
    """The element size chosen for a plate, in the plate's own units, to two significant figures: PLATE_LONG elements along the longer
    side or PLATE_SHORT across the shorter, whichever is finer, and coarser where that would pass PLATE_MOST elements. None when the size
    is not two positive numbers (the check names the row)."""
    try:
        long, short = max(float(length), float(width)), min(float(length), float(width))
    except (TypeError, ValueError):
        return None
    if not short > 0.0:
        return None
    size = min(long / PLATE_LONG, short / PLATE_SHORT)
    size = max(size, (long * short / PLATE_MOST) ** 0.5)
    return float(f"{size:.2g}")


def complete_plate(data: dict, today: date | None = None) -> tuple[dict, tuple[Built, ...]]:
    """The values of a plate set up on the model tree with the rows the engineer is not asked for chosen, and the list of those choices
    (ADR-0089 amendment 8). The engineer gives the material, the layup, the size and what holds and loads it; chosen here, each with its
    reason, are who set it up and when, where the size comes from, the element size, G13 and G23 for a library material, and the
    criteria. A row the engineer gave is never changed, and nothing about the supports or the loads is chosen: a plate with none is
    refused by the check, by name."""
    out = dict(data)
    built: list[Built] = []
    stated = str(out.get("units") or "").strip()
    units = stated if stated in UNIT_SYSTEMS else UNITS

    def choose(key: str, value: Any, reason: str) -> None:
        if _blank(out.get(key)):
            out[key] = value
            built.append(Built(key, value, reason))

    choose("test", PLATE_TEST, "a plate, held and loaded where the engineer says")
    choose("units", UNITS, "results and files use these units")
    choose("filled_by", "workspace", "the plate was set up in the workspace")
    choose("date", (today or date.today()).isoformat(), "the day the plate was set up")
    choose("size_from", "the dimensions you gave", "a plate follows no test standard: its size is the engineer's")
    size = _plate_element_size(out.get("length"), out.get("width"))
    if size is not None:
        choose("element_size", size, f"about {PLATE_LONG} elements along the longer side or {PLATE_SHORT} across the shorter, whichever is finer, "
               f"and at most about {PLATE_MOST:,} elements")
    record = _record(out)
    bends = "it matters where the plate bends and is thick for its span"
    if record is not None:
        estimate = transverse_estimates(str(out["library"]).strip())
        tape = str(record.get("architecture") or "").lower().startswith("unidirectional")  # as `transverse_estimates` tells a tape
        choose("G13", _in_units(estimate.G13, "stress", units), f"not in the library: G13 = G12, a usual estimate; {bends}")
        choose("G23", _in_units(estimate.G23, "stress", units), ("not in the library: G23 = E2 / 3, a usual estimate for a tape; " if tape
               else "not in the library, and no estimate holds for a fabric: taken equal to G12 so the model builds; ") + bends)
    elif not _blank(out.get("own_G12")):
        choose("G13", out["own_G12"], f"not given: G13 = G12, a usual estimate; {bends}")
        choose("G23", out["own_G12"], f"not given: taken equal to G12 so the model builds; {bends}")
    strengths = ("own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6")
    if record is None and any(_blank(out.get(key)) for key in strengths):
        choose("criteria", "none", "not all five strengths are given, so no first-ply failure criterion can be judged")
    else:
        choose("criteria", "all", "all criteria the material's strengths allow")
    return out, tuple(built)


__all__ = ["Built", "INPUT", "PLATE_INPUT", "complete_plate", "complete_tension", "Transverse", "d3039_class", "transverse_estimates"]
