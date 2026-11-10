"""ASTM D3039/D3039M: tensile properties of polymer matrix composites, as a profile (ADR-0072).

Read from the 2017 copy (D3039/D3039M-17), licensed to UC San Diego; the publisher lists D3039/D3039M-17(2025), a reapproval, as the active
edition. Each value below carries its clause; the wording is ours. D3039 states its SI and inch-pound values separately and they are not
exact equivalents (§1.2), so a coupon stated in inches is held to the bracketed inch values, not to converted millimetres.

Our reading, not the standard's words: Table 1's "gripping" in the minimum length is the gripped length at both ends together, which is
what Table 2's lengths allow (a 250 mm, 0° coupon with 56 mm tabs leaves 108 mm for the gauge length after twice its 15 mm width).
"""

from __future__ import annotations

from collections.abc import Callable

from anisotropy_engine.units import INCH

from .profile import (MM, POLYMER_FAMILIES, Finding, Preset, Profile, Requirement, Subject, amount, at_least, at_most, is_balanced, is_symmetric,
                      is_tape, laminate_words, same)

ID = "astm-d3039"
DESIGNATION = "ASTM D3039/D3039M-17"

ZERO_UD = Preset("0-ud", "0° unidirectional", "Table 2",
                 si={"width": 15 * MM, "length": 250 * MM, "tab_length": 56 * MM, "tab_thickness": 1.5 * MM, "tab_bevel": 7.0},
                 inch_pound={"width": 0.5, "length": 10.0, "tab_length": 2.25, "tab_thickness": 0.062, "tab_bevel": 7.0},
                 thickness=1.0 * MM, thickness_inch=0.040, note="bonded tabs with a 7° or a 90° bevel")
NINETY_UD = Preset("90-ud", "90° unidirectional", "Table 2",
                   si={"width": 25 * MM, "length": 175 * MM, "tab_length": 25 * MM, "tab_thickness": 1.5 * MM, "tab_bevel": 90.0},
                   inch_pound={"width": 1.0, "length": 7.0, "tab_length": 1.0, "tab_thickness": 0.062, "tab_bevel": 90.0},
                   thickness=2.0 * MM, thickness_inch=0.080, note="bonded tabs with a 90° bevel")
BALANCED = Preset("balanced", "balanced and symmetric", "Table 2",
                  si={"width": 25 * MM, "length": 250 * MM}, inch_pound={"width": 1.0, "length": 10.0},
                  thickness=2.5 * MM, thickness_inch=0.100,
                  note="gripped through emery cloth without bonded tabs; Table 2 gives no grip length, so the tab length stays yours to state")
CLASSES = (ZERO_UD, NINETY_UD, BALANCED)  # Table 2's fourth class, random-discontinuous, is not a laminate of plies: a coupon here never falls in it


def classify(s: Subject) -> Preset | None:
    """The Table 2 class of the coupon's laminate: 0° or 90° unidirectional for a tape (or the team's own constants, taken as a tape) whose
    plies all lie at 0° or all at 90°, otherwise balanced and symmetric when it is; None when it is neither."""
    tape = is_tape(s)
    if tape is not False and all(same(a, 0.0) for a in s.angles):
        return ZERO_UD
    if tape is not False and all(same(abs(a), 90.0) for a in s.angles):
        return NINETY_UD
    if is_balanced(s.angles) and is_symmetric(s.angles):
        return BALANCED
    return None


def _matrix(s: Subject) -> Finding:
    asked = "a polymer-matrix composite reinforced by high-modulus fibres"
    if s.isotropic:
        return Finding(False, "an isotropic material with no fibres: a plastic's tensile test is ASTM D638", asked)
    if s.family is None:
        return Finding(None, "your own constants: the matrix is not on the form, so state it in the notes", asked)
    return Finding(s.family in POLYMER_FAMILIES, s.family.lower(), asked)


def _laminate(s: Subject) -> Finding:
    ok = is_balanced(s.angles) and is_symmetric(s.angles)
    return Finding(ok, f"{laminate_words(s.angles)}, {len(s.angles)} plies", "balanced and symmetric about the direction of the pull")


def _section(s: Subject) -> Finding:
    words = "a dog-bone" if s.dogbone else ("a plain strip" if s.hole_diameter is None else "a strip with a hole")
    return Finding(s.hole_diameter is None and not s.dogbone, words, "a constant rectangular cross-section")


def _min_length(s: Subject) -> Finding:
    u = s.units
    if s.strain_length is None:
        return Finding(None, "no strain measurement stated", "gripped length + 2 × width + gauge length")
    need = 2 * s.tab_length + 2 * s.width + s.strain_length
    return Finding(at_least(s.length, need), amount(s.length, u),
                   f"at least {amount(need, u)} (2 × {amount(s.tab_length, u)} gripped + 2 × {amount(s.width, u)} wide + {amount(s.strain_length, u)} gauge)")


def _tab_bevel(s: Subject) -> Finding:
    if s.tab_bevel is None:
        return Finding(None, "no bonded tabs", "5° to 90°")
    return Finding(5.0 <= s.tab_bevel <= 90.0, f"{s.tab_bevel:g}°", "5° to 90°, both included")


def _class_finding(s: Subject) -> tuple[Preset | None, Finding | None]:
    preset = classify(s)
    if preset is None:
        return None, Finding(None, f"the laminate ({laminate_words(s.angles)}) falls in no class of Table 2", "")
    return preset, None


def _t2_size(row: str, words: str) -> Callable[[Subject], Finding]:
    def rule(s: Subject) -> Finding:
        preset, none = _class_finding(s)
        if none is not None:
            return none
        values = preset.si_values(s.units)
        if row not in values:
            return Finding(None, f"{preset.label}: Table 2 gives no {words}", "gripped through emery cloth; the grip length is yours to state")
        have = {"width": s.width, "length": s.length, "tab_length": s.tab_length}[row]
        return Finding(same(have, values[row]), amount(have, s.units), f"{amount(values[row], s.units)} for a {preset.label} coupon")
    return rule


def _t2_thickness(s: Subject) -> Finding:
    preset, none = _class_finding(s)
    if none is not None:
        return none
    want = preset.thickness_si(s.units)
    return Finding(same(s.thickness, want), amount(s.thickness, s.units), f"{amount(want, s.units)} for a {preset.label} coupon")


def _t2_tab_thickness(s: Subject) -> Finding:
    preset, none = _class_finding(s)
    if none is not None:
        return none
    if preset is BALANCED:
        return Finding(None, "bonded tabs" if s.tab_thickness is not None else "no bonded tabs",
                       "emery cloth for this class; bonded tabs are allowed (§8.2.1.2)")
    want = preset.si_values(s.units)["tab_thickness"]
    if s.tab_thickness is None:
        return Finding(False, "no bonded tabs", f"{amount(want, s.units)} tabs for a {preset.label} coupon")
    return Finding(same(s.tab_thickness, want), amount(s.tab_thickness, s.units), f"{amount(want, s.units)} for a {preset.label} coupon")


def _t2_tab_bevel(s: Subject) -> Finding:
    preset, none = _class_finding(s)
    if none is not None:
        return none
    if preset is BALANCED:
        return Finding(None, f"{s.tab_bevel:g}°" if s.tab_bevel is not None else "no bonded tabs", "emery cloth for this class")
    allowed = (7.0, 90.0) if preset is ZERO_UD else (90.0,)
    words = " or ".join(f"{a:g}°" for a in allowed)
    if s.tab_bevel is None:
        return Finding(False, "no bonded tabs", f"{words} for a {preset.label} coupon")
    return Finding(any(same(s.tab_bevel, a) for a in allowed), f"{s.tab_bevel:g}°", f"{words} for a {preset.label} coupon")


def _extensometer(s: Subject) -> Finding:
    if s.strain_device != "extensometer":
        return Finding(None, "no extensometer" if s.strain_device is None else f"a {s.strain_device}", "10 to 50 mm [0.5 to 2.0 in]")
    low, high = (0.5 * INCH, 2.0 * INCH) if s.inch_pound else (10 * MM, 50 * MM)
    return Finding(at_least(s.strain_length, low) and at_most(s.strain_length, high), amount(s.strain_length, s.units),
                   f"{amount(low, s.units)} to {amount(high, s.units)}")


def _strain_gauge(s: Subject) -> Finding:
    if s.strain_device != "strain gauge":
        return Finding(None, "no strain gauge" if s.strain_device is None else f"an {s.strain_device}", "at least 3 mm [0.125 in]")
    low, usual = (0.125 * INCH, 0.25 * INCH) if s.inch_pound else (3 * MM, 6 * MM)
    return Finding(at_least(s.strain_length, low), amount(s.strain_length, s.units),
                   f"at least {amount(low, s.units)}; {amount(usual, s.units)} suits most materials")


def _edge_effects(s: Subject) -> Finding:
    off_axis = sorted({abs(a) for a in s.angles if not (same(a, 0.0) or same(abs(a), 90.0))})
    if not off_axis:
        return Finding(True, "no off-axis plies", "")
    return Finding(False, "off-axis plies at " + ", ".join(f"±{a:g}°" for a in off_axis),
                   "edge softening can make the measured strength and stiffness read low; less so with many 0° plies")


REQUIREMENTS = (
    Requirement("scope-matrix", "§1.1", "scope", "The material is a polymer-matrix composite reinforced by high-modulus fibres.", _matrix,
                ("library", "own_name")),
    Requirement("scope-laminate", "§1.1", "scope", "The laminate is balanced and symmetric about the direction of the pull: a −θ ply for every +θ "
                "ply, and the stack a mirror image about its mid-plane.", _laminate, ("ply_1", "symmetric")),
    Requirement("section", "Table 1", "mandatory", "The coupon has a constant rectangular cross-section.", _section, ("test",)),
    Requirement("min-length", "Table 1", "mandatory", "The length is at least the gripped length, plus twice the width, plus the gauge length of the "
                "strain measurement (we read the gripped length as both grips together).", _min_length, ("length", "tab_length", "width", "strain_length")),
    Requirement("tab-bevel", "Table 1", "mandatory", "Bonded tabs are bevelled at 5° to 90°, both included.", _tab_bevel, ("tab_bevel",)),
    Requirement("t2-width", "Table 2", "recommended", "The width suggested for the laminate's class.", _t2_size("width", "width"), ("width",)),
    Requirement("t2-length", "Table 2", "recommended", "The overall length suggested for the laminate's class.", _t2_size("length", "length"), ("length",)),
    Requirement("t2-thickness", "Table 2", "recommended", "The laminate thickness suggested for the laminate's class.", _t2_thickness,
                ("ply_thickness", "ply_1")),
    Requirement("t2-tab-length", "Table 2", "recommended", "The tab length suggested for the laminate's class.", _t2_size("tab_length", "tab length"),
                ("tab_length",)),
    Requirement("t2-tab-thickness", "Table 2", "recommended", "The tab thickness suggested for the laminate's class.", _t2_tab_thickness,
                ("tab_thickness",)),
    Requirement("t2-tab-bevel", "Table 2", "recommended", "The tab bevel suggested for the laminate's class.", _t2_tab_bevel, ("tab_bevel",)),
    Requirement("extensometer", "§7.3.2", "recommended", "An extensometer's gauge length lies between 10 and 50 mm [0.5 and 2.0 in].", _extensometer,
                ("strain_length",)),
    Requirement("strain-gauge", "§7.3.1", "recommended", "A bonded strain gauge's active length is at least 3 mm [0.125 in]; 6 mm [0.25 in] suits most "
                "materials.", _strain_gauge, ("strain_length",)),
    Requirement("edge-effects", "§6.4", "note", "Off-axis plies soften the free edges, so the strength and stiffness of an angle-ply laminate can read "
                "low.", _edge_effects, ("ply_1",)),
    Requirement("tolerance-width", "Table 1", "lab", "The specimen's width is within ±1 % of its width."),
    Requirement("tolerance-thickness", "Table 1", "lab", "The specimen's thickness is within ±4 % of its thickness."),
    Requirement("flatness", "Table 1", "lab", "The specimen lies flat under light finger pressure."),
    Requirement("tab-match", "Table 1", "lab", "Bonded tabs match in thickness within ±1 % and are feathered into the coupon without damaging it."),
    Requirement("measure", "§11.2.2", "lab", "Width and thickness are measured at three places in the gauge section, and the area is their average "
                "width times their average thickness."),
    Requirement("specimens", "§8.1", "lab", "At least five specimens are tested per condition."),
    Requirement("conditioning", "§10", "lab", "The conditioning is reported; without one, the specimens are reported as unconditioned, moisture unknown."),
    Requirement("speed", "§11.3", "lab", "The strain rate gives failure in 1 to 10 minutes: 0.01 per minute in strain control, or 2 mm/min [0.05 in/min] "
                "of the head as a start."),
    Requirement("bending", "§11.6.1", "lab", "Bending is checked with back-to-back transducers on at least one specimen per sample at 2000 microstrain; above "
                "3 % the strains of both faces are averaged."),
    Requirement("alignment", "§7.2.5", "lab", "The load train's alignment is checked; good practice keeps bending to 3 to 5 % above 1000 microstrain."),
    Requirement("failure-mode", "§11.9", "lab", "Each failure is recorded with the three-part code of the failure type, area and location."),
    Requirement("grip-failures", "§12.2", "lab", "When many specimens fail within one width of a tab or grip, the gripping is re-examined."),
)

PROFILE = Profile(
    id=ID, designation=DESIGNATION, title="Tensile properties of polymer matrix composites", kinds=("unnotched_tension",),
    catalog_url="https://store.astm.org/d3039_d3039m-17r25.html",
    edition_note="read from the D3039/D3039M-17 copy licensed to UC San Diego; the publisher lists D3039/D3039M-17(2025), a reapproval, as "
                 "active (that its text is unchanged is UNVERIFIED)",
    systems="SI and inch-pound, each used on its own (§1.2)",
    requirements=REQUIREMENTS, classes=CLASSES, classify=classify, requires_strain=True, aliases=("d3039", "d3039m"),
)
