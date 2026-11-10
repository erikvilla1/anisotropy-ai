"""ASTM C1869: open-hole tensile strength of fibre-reinforced advanced ceramic composites, as a profile (ADR-0072).

Read from the C1869-18 (reapproved 2023) copy licensed to UC San Diego. Each value below carries its clause; the wording is ours. The
standard is in SI only (§1.8), so a coupon stated in inches is held to the millimetre values, converted exactly.

C1869 covers ceramic matrix composites (§1.1, §1.4). Every material in our library has a polymer matrix, whose open-hole standard is ASTM
D5766/D5766M (not in our list until its copy is read); a library material is therefore outside the scope of C1869, and the check says so.

Two baseline specimens (Tables 1 and 2): A, a 6 mm hole in a 36 mm wide strip, and B, a 3 mm hole in a 10 mm wide strip. Any other size
follows Annex A1 and Appendix X1 and is reported as a variation (§9.2.6). Our model always centres the hole, so the position tolerance of
the tables is met by construction. The width and hole tolerances are bands on the specimen; a nominal size anywhere inside the band is a
specimen the standard takes (our reading).
"""

from __future__ import annotations

from .profile import (MM, POLYMER_FAMILIES, Finding, Preset, Profile, Requirement, Subject, amount, at_least, at_most, is_balanced, is_symmetric,
                      laminate_words, ratio, same, within)

ID = "astm-c1869"
DESIGNATION = "ASTM C1869-18(2023)"

SPECIMEN_A = Preset("A", "Specimen A: a 6 mm hole in a 36 mm wide strip", "Table 1",
                    si={"width": 36 * MM, "hole_diameter": 6 * MM, "length": 120 * MM, "tab_length": 30 * MM}, minimum=("length", "tab_length"),
                    thickness=3 * MM, note="the least length and grip length; longer is allowed")
SPECIMEN_B = Preset("B", "Specimen B: a 3 mm hole in a 10 mm wide strip", "Table 2",
                    si={"width": 10 * MM, "hole_diameter": 3 * MM, "length": 60 * MM, "tab_length": 15 * MM}, minimum=("length", "tab_length"),
                    thickness=3 * MM, note="the least length and grip length; longer is allowed")
OTHER = "other"  # a size of Annex A1, reported as a variation (§9.2.6)

# Per specimen: the hole and its band, the width and its band, the least width-to-hole ratio (§6.4), the least overall, gauge and grip
# lengths, and the nominal hole-to-thickness ratio (§6.4); lengths in metres.
LIMITS = {
    "A": {"D": 6.0 * MM, "D_band": 0.2 * MM, "w": 36 * MM, "w_band": 0.5 * MM, "w_over_D": 6.0, "L": 120 * MM, "L_gage": 60 * MM, "L_grip": 30 * MM,
          "D_over_h": 2.0, "table": "Table 1"},
    "B": {"D": 3.0 * MM, "D_band": 0.1 * MM, "w": 10 * MM, "w_band": 0.2 * MM, "w_over_D": 3.0, "L": 60 * MM, "L_gage": 30 * MM, "L_grip": 15 * MM,
          "D_over_h": 1.0, "table": "Table 2"},
}
THICKNESS_RANGE = (2 * MM, 10 * MM)  # §9.2 and both tables: 2 to 10 mm, both included
NOMINAL_THICKNESS = 3 * MM  # §9.2
SMALL_HOLE = 4 * MM  # A1.3: a hole under 4 mm is at most 30 % of the width; a larger hole may need w/D above 5
LARGE_HOLE = 5 * MM  # X1.3: w/D at least 6 for a hole above 5 mm


def _limits(s: Subject) -> dict | None:
    return LIMITS.get(s.variant or "")


def _not_baseline(s: Subject, asked: str) -> Finding:
    return Finding(None, f"Specimen {s.variant}: judged by Annex A1 instead" if s.variant == OTHER else "no specimen named", asked)


def _matrix(s: Subject) -> Finding:
    asked = "a ceramic matrix composite with continuous fibres"
    if s.family is None:
        return Finding(None, "your own constants: state in the notes that the material is a ceramic matrix composite", asked)
    words = s.family.lower()
    if s.family in POLYMER_FAMILIES:
        words += ": a polymer matrix, whose open-hole standard is ASTM D5766/D5766M (not in our list yet)"
    return Finding(False, words, asked)


def _architecture(s: Subject) -> Finding:
    ok = is_balanced(s.angles) and is_symmetric(s.angles)
    return Finding(ok, laminate_words(s.angles), "a balanced, symmetric two-dimensional laminate; others are allowed and described in the report")


def _hole(s: Subject) -> Finding:
    lim = _limits(s)
    if lim is None:
        return _not_baseline(s, "the hole of Specimen A or B")
    return Finding(within(s.hole_diameter, lim["D"], lim["D_band"]), amount(s.hole_diameter, s.units),
                   f"{amount(lim['D'], s.units)} ± {amount(lim['D_band'], s.units)} for Specimen {s.variant}")


def _width(s: Subject) -> Finding:
    lim = _limits(s)
    if lim is None:
        return _not_baseline(s, "the width of Specimen A or B")
    return Finding(within(s.width, lim["w"], lim["w_band"]), amount(s.width, s.units),
                   f"{amount(lim['w'], s.units)} ± {amount(lim['w_band'], s.units)} for Specimen {s.variant}")


def _width_to_hole(s: Subject) -> Finding:
    have = s.width / s.hole_diameter
    lim = _limits(s)
    if lim is not None:
        return Finding(at_least(have, lim["w_over_D"]), ratio(have), f"at least {lim['w_over_D']:g} for Specimen {s.variant}")
    if s.variant == OTHER and s.hole_diameter < SMALL_HOLE:
        return Finding(at_least(have, 1 / 0.3), ratio(have), "a hole under 4 mm takes at most 30 % of the width (A1.3)")
    return Finding(None, ratio(have), "see the larger-hole recommendation (A1.3, X1.3)")


def _length(s: Subject) -> Finding:
    lim = _limits(s)
    if lim is None:
        return _not_baseline(s, "the least length of Specimen A or B")
    return Finding(at_least(s.length, lim["L"]), amount(s.length, s.units), f"at least {amount(lim['L'], s.units)} for Specimen {s.variant}")


def _gauge(s: Subject) -> Finding:
    lim = _limits(s)
    if lim is None:
        return _not_baseline(s, "the least gauge length of Specimen A or B")
    return Finding(at_least(s.gauge_length, lim["L_gage"]), amount(s.gauge_length, s.units) + " between the grips",
                   f"at least {amount(lim['L_gage'], s.units)} for Specimen {s.variant}")


def _grip(s: Subject) -> Finding:
    lim = _limits(s)
    if lim is None:
        return _not_baseline(s, "the least grip length of Specimen A or B")
    value = amount(s.tab_length, s.units) if s.tab_length else "0: the model holds only the end rows"
    return Finding(at_least(s.tab_length, lim["L_grip"]), value, f"at least {amount(lim['L_grip'], s.units)} at each end for Specimen {s.variant}")


def _thickness(s: Subject) -> Finding:
    low, high = THICKNESS_RANGE
    return Finding(at_least(s.thickness, low) and at_most(s.thickness, high), amount(s.thickness, s.units),
                   f"{amount(low, s.units)} to {amount(high, s.units)}")


def _centred(s: Subject) -> Finding:
    return Finding(True, "at the centre: the model always places the hole there", "centred within ±0.5 mm across and ±2 mm along")


def _variation(s: Subject) -> Finding:
    if s.variant != OTHER:
        return Finding(True, f"Specimen {s.variant}" if s.variant else "no specimen named", "")
    return Finding(False, "a size other than Specimen A or B", "the hole and the strip's size are reported as a variation")


def _nominal_thickness(s: Subject) -> Finding:
    return Finding(same(s.thickness, NOMINAL_THICKNESS), amount(s.thickness, s.units), f"{amount(NOMINAL_THICKNESS, s.units)} nominal")


def _hole_to_thickness(s: Subject) -> Finding:
    have = s.hole_diameter / s.thickness
    lim = _limits(s)
    if lim is None:
        return _not_baseline(s, "the nominal ratio of Specimen A or B")
    return Finding(same(float(ratio(have)), lim["D_over_h"]), ratio(have), f"{lim['D_over_h']:g} nominal for Specimen {s.variant}")


def _gauge_to_hole(s: Subject) -> Finding:
    have = s.gauge_length / s.hole_diameter
    return Finding(at_least(have, 10.0), ratio(have), "10 or more")


def _large_hole(s: Subject) -> Finding:
    have = s.width / s.hole_diameter
    if s.variant != OTHER or s.hole_diameter <= SMALL_HOLE:
        return Finding(None, ratio(have), "applies to a hole above 4 mm in a size other than A or B")
    if s.hole_diameter > LARGE_HOLE:
        return Finding(at_least(have, 6.0), ratio(have), "at least 6 for a hole above 5 mm (X1.3)")
    return Finding(have > 5.0, ratio(have), "above 5 for a hole above 4 mm (A1.3)")


def _extensometer(s: Subject) -> Finding:
    if s.strain_device != "extensometer":
        return Finding(None, "no extensometer" if s.strain_device is None else f"a {s.strain_device}", "at least three hole diameters")
    need = 3 * s.hole_diameter
    return Finding(at_least(s.strain_length, need), amount(s.strain_length, s.units), f"at least {amount(need, s.units)}, centred over the hole")


def _strain_gauge(s: Subject) -> Finding:
    if s.strain_device != "strain gauge":
        return Finding(None, "no strain gauge" if s.strain_device is None else f"an {s.strain_device}", "at least 9 mm along the coupon")
    return Finding(at_least(s.strain_length, 9 * MM), amount(s.strain_length, s.units), f"at least {amount(9 * MM, s.units)} along the coupon")


REQUIREMENTS = (
    Requirement("scope-matrix", "§1.1, §1.4", "scope", "The material is a ceramic matrix composite with continuous fibres.", _matrix,
                ("library", "own_name")),
    Requirement("architecture", "§1.4, §9.2.4", "recommended", "The laminate is usually balanced and symmetric in two dimensions; another "
                "architecture is allowed and described in the report (§9.2.5).", _architecture, ("ply_1", "symmetric")),
    Requirement("hole", "Tables 1 and 2", "mandatory", "The hole of the named specimen: 6.0 mm ± 0.2 mm for A, 3.0 mm ± 0.1 mm for B.", _hole,
                ("hole_diameter",)),
    Requirement("width", "Tables 1 and 2", "mandatory", "The width of the named specimen: 36 mm ± 0.5 mm for A, 10 mm ± 0.2 mm for B.", _width,
                ("width",)),
    Requirement("width-to-hole", "§6.4, A1.3", "mandatory", "The width is at least 6 hole diameters for A and 3 for B; a hole under 4 mm in another size "
                "takes at most 30 % of the width.", _width_to_hole, ("width", "hole_diameter")),
    Requirement("length", "Tables 1 and 2", "mandatory", "The overall length is at least 120 mm for A and 60 mm for B.", _length, ("length",)),
    Requirement("gauge-length", "Tables 1 and 2", "mandatory", "The gauge length between the grips is at least 60 mm for A and 30 mm for B.", _gauge,
                ("length", "tab_length")),
    Requirement("grip-length", "Tables 1 and 2", "mandatory", "Each grip section is at least 30 mm long for A and 15 mm for B.", _grip, ("tab_length",)),
    Requirement("thickness", "§9.2, Tables 1 and 2", "mandatory", "The thickness lies between 2 and 10 mm, both included.", _thickness,
                ("ply_thickness", "ply_1")),
    Requirement("hole-centred", "Tables 1 and 2", "mandatory", "The hole is centred within ±0.5 mm across the width and ±2 mm along the length.",
                _centred, ("hole_diameter",)),
    Requirement("variation", "§9.2.6", "note", "A hole or strip of another size than A or B is reported as a variation.", _variation, ("specimen",)),
    Requirement("nominal-thickness", "§9.2", "recommended", "The nominal thickness is 3 mm.", _nominal_thickness, ("ply_thickness", "ply_1")),
    Requirement("hole-to-thickness", "§6.4", "recommended", "The hole diameter is nominally 2 thicknesses for A and 1 for B.", _hole_to_thickness,
                ("hole_diameter", "ply_thickness")),
    Requirement("gauge-to-hole", "§9.2.2, A1.3", "recommended", "The gauge length is 10 hole diameters or more.", _gauge_to_hole,
                ("length", "tab_length", "hole_diameter")),
    Requirement("larger-hole", "A1.3, X1.3", "recommended", "In a size other than A or B, a hole above 4 mm takes a width above 5 diameters, and a hole "
                "above 5 mm at least 6.", _large_hole, ("width", "hole_diameter")),
    Requirement("extensometer", "X3.1", "recommended", "An extensometer spans at least three hole diameters, centred over the hole.", _extensometer,
                ("strain_length",)),
    Requirement("strain-gauge", "X3.4.1", "recommended", "A bonded strain gauge along the coupon is at least 9 mm long.", _strain_gauge,
                ("strain_length",)),
    Requirement("tolerances", "Tables 1 and 2", "lab", "The specimen holds the hole's circularity (±0.2 mm for A, ±0.1 mm for B), a uniform width "
                "(±0.5 mm for A, ±0.2 mm for B, and ±2 %) and the gauge length within ±2 mm."),
    Requirement("hole-preparation", "§9.3.3", "lab", "The hole is drilled undersize and reamed to its diameter without delaminating the material."),
    Requirement("measure", "§12.2.5 to §12.2.7", "lab", "The width is measured at the hole and 10 mm either side, the thickness at eight points, the hole "
                "at two diameters 90° apart, and the gauge length."),
    Requirement("specimens", "§9.10", "lab", "At least five valid specimens are tested."),
    Requirement("failure-at-hole", "§9.11, §12.5, §13.1", "lab", "Only a failure through the centre hole is valid: lateral, angled or multi-mode at the "
                "gauge middle."),
    Requirement("bending", "§7.3, X4", "lab", "The load train bends an alignment specimen by at most 5 %, and a gauged specimen by less than 10 %."),
    Requirement("rate", "§12.1.7", "lab", "Displacement control, at a rate that breaks the specimen in 5 to 10 seconds."),
    Requirement("unnotched", "§4.7, §9.5", "lab", "Unnotched specimens of the same geometry are tested to compare the open-hole strength with."),
    Requirement("fractography", "§12.5.2", "lab", "Each failed specimen is examined and the fracture described, or the report says it was not."),
)

PROFILE = Profile(
    id=ID, designation=DESIGNATION, title="Open-hole tensile strength of fibre-reinforced advanced ceramic composites", kinds=("open_hole_tension",),
    catalog_url="https://store.astm.org/c1869-18.html",
    edition_note="read from the C1869-18 (reapproved 2023) copy licensed to UC San Diego",
    systems="SI only (§1.8)",
    requirements=REQUIREMENTS, variants=(SPECIMEN_A, SPECIMEN_B), variant_words=("A", "B", OTHER), aliases=("c1869",),
)
