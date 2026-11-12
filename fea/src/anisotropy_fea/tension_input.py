"""The tension coupon from its material and layup: the standard and our rules choose the rest, and say so (ADR-0090).

The studio's tension screen asks the engineer for two things, the material and the layup, and offers four to change (their own
material constants, the pull or force, the coupon's size and tabs, the element size). Every other row of the form is chosen here,
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

INPUT = "tension"  # the values file's "input" word for the tension screen
TEST = "unnotched tension"
UNITS = "mm-MPa"
D3039 = astm_d3039.DESIGNATION
GRIP_LENGTH_MM = 56.0  # D3039 Table 2 gives no grip length for a balanced and symmetric laminate; ours, as in fea/checks/d3039-im7-8552
EXTENSOMETER_MM = 25.0  # within D3039 §7.3.2's 10 to 50 mm, as in the check
PULL_MM = 1.0
ELEMENT_SIZE_MM = 2.0
MM = 1e-3


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


def complete_tension(data: dict, today: date | None = None) -> tuple[dict, tuple[Built, ...]]:
    """The values of a tension coupon with every row the engineer was not asked for chosen, and the list of those choices.

    `data` is the values file without its "input" key; the rows it holds are kept as they are. A layup in no D3039 Table 2 class, or a
    coupon under no standard, gets no size: the check then asks for the length, width and tab length by row."""
    out = dict(data)
    built: list[Built] = []

    def choose(key: str, value: Any, reason: str) -> None:
        if _blank(out.get(key)):
            out[key] = value
            built.append(Built(key, value, reason))

    choose("test", TEST, "the one test the studio offers until its comparison with Abaqus is validated")
    choose("units", UNITS, "millimetres, megapascals and newtons: the units the Abaqus and CalculiX decks are written in")
    choose("standard", D3039, "the standard of the unnotched tension test of a polymer-matrix composite")
    under_d3039 = str(out["standard"]).strip().lower() == D3039.lower()
    choose("filled_by", "studio", "the coupon was set up on the studio's tension screen")
    choose("date", (today or date.today()).isoformat(), "the day the coupon was set up")

    size_given = any(not _blank(out.get(key)) for key in ("length", "width", "tab_length"))
    preset = d3039_class(out) if under_d3039 and not size_given else None
    if preset is not None:
        sizes = {row: value / MM for row, value in preset.si.items() if row in ("width", "length", "tab_length")}
        tab = sizes.get("tab_length", GRIP_LENGTH_MM)
        why = f"{D3039}, Table 2, {preset.label}"
        choose("width", sizes["width"], why)
        choose("length", sizes["length"], why)
        choose("tab_length", tab, why if "tab_length" in sizes else
               f"{why} grips through emery cloth and sets no grip length: {GRIP_LENGTH_MM:g} mm by default")
        choose("size_from", why + ("" if "tab_length" in sizes else f"; the {GRIP_LENGTH_MM:g} mm grip length by default"),
               "where the size comes from, for the coupon's identity card")
    elif size_given:
        choose("size_from", "the engineer's own size" + (f": a deviation from {D3039} Table 2 is reported, never refused" if under_d3039 else ""),
               "the size was given under Change a choice")
    else:  # a layup in no Table 2 class, or no standard: the size is the engineer's to give, and the check asks for it by row
        choose("size_from", "the engineer's own size" + (f": the layup is in no {D3039} Table 2 class" if under_d3039 else ""),
               "no size could be chosen, so the length, width and tab length are asked for under Change a choice")

    choose("strain_device", "extensometer", f"strain is measured over a gauge length at mid-length ({D3039} §7.3)")
    choose("strain_length", EXTENSOMETER_MM, f"{EXTENSOMETER_MM:g} mm, within {D3039} §7.3.2's 10 to 50 mm, centred on the coupon")
    choose("grips", "nodal", "clamped: every node of each tab held, the top one pulled, as the D3039 check and its CalculiX twin are")
    choose("region", "tabs", "the grips hold the whole tab")
    if _blank(out.get("value")):
        choose("control", "displacement", "the top grip moves; the bottom one is held")
        choose("value", PULL_MM, f"{PULL_MM:g} mm: the model is linear, so the answer, the loading at first-ply failure, does not depend on it")
    choose("element_size", ELEMENT_SIZE_MM, f"{ELEMENT_SIZE_MM:g} mm, structured, with node rows at the tab lines and at the extensometer's "
           "ends; the full run adds a mesh study")
    record = _record(out)
    if record is not None:  # the library gives no G13 or G23 (only CalculiX's brick and the Abaqus shell's transverse shear read them)
        lamina = library_material(str(out["library"]).strip()).lamina
        g12, e2 = lamina.G12 / 1e6, lamina.E2 / 1e6  # Pa to MPa, written to 0.01 MPa
        tape = str(record.get("architecture") or "").lower().startswith("unidirectional")
        choose("G13", round(g12, 2), "not in the library: G13 = G12, the usual estimate (the form's Definitions); a pull in the plane does not load it")
        if tape:
            choose("G23", round(e2 / 3.0, 2), "not in the library: G23 = E2 / 3, the usual estimate for a tape (the form's Definitions); a pull in the "
                                               "plane does not load it")
        else:
            choose("G23", round(g12, 2), "not in the library, and no estimate holds for a fabric: taken equal to G12 so the model builds; a pull in "
                                          "the plane does not load it")
    elif not _blank(out.get("own_G12")):
        choose("G13", out["own_G12"], "not given: G13 = G12, the usual estimate (the form's Definitions); a pull in the plane does not load it")
        choose("G23", out["own_G12"], "not given: taken equal to G12 so the model builds; a pull in the plane does not load it")
    strengths = ("own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6")
    if record is None and any(_blank(out.get(key)) for key in strengths):
        choose("criteria", "none", "the own material gives not all five strengths, so no first-ply failure criterion can be judged")
    else:
        choose("criteria", "all", "every first-ply failure criterion we compute is reported")
    return out, tuple(built)


__all__ = ["Built", "INPUT", "complete_tension", "d3039_class"]
