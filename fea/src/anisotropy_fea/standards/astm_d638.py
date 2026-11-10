"""ASTM D638: tensile properties of plastics, as a profile (ADR-0075).

Read from the D638-14 copy the founder supplied; a later edition, D638-22, is active, and this profile has not been read
against it (UNVERIFIED that its values are unchanged). Each value below carries its clause; the wording is ours. The SI values are the
standard and the inch-pound values in parentheses are for information only (§1.5), so a coupon stated in inches is held to the millimetre
values, converted exactly.

D638 tests a dumbbell specimen (§1.1). Fig. 1 names five types of flat specimen by thickness: Types I and II up to 7 mm, Type III over 7 to
14 mm, Types IV and V up to 4 mm. Each has a narrow section of width W and length L, joined to the overall width WO by a fillet of radius R
(Type IV adds an outer radius RO), an overall length LO, a gage length G and a distance between the grips D. Our model draws exactly that
outline (`dogbone`), grips each end over (LO - D) / 2, and puts its virtual extensometer over G.

Our readings, not the standard's words:
- WO and LO are minimums. Fig. 1 gives WO a plus tolerance (+6.4 mm, +3.18 mm for Type V): we read an overall width from the minimum to the
  minimum plus that tolerance as the width the figure takes. LO has no maximum.
- A stated size inside a tolerance band of Fig. 1 meets the size; Type V's tighter bands are footnote C's.
- A material stated as plies is a reinforced composite (§6.1.3); one stated by E and nu is a plastic. Every library record is a fibre
  composite whose fibres are far stiffer than 20 GPa, which Note 4 sends to D3039/D3039M.

The profile is judged by `conformance.judge` like the others, and joins the registry, and with it the form's Standard list, in part 2 of
ADR-0075, together with the form's rows for the dog-bone and the isotropic material that its requirements and types name.
"""

from __future__ import annotations

from collections.abc import Callable

from .profile import MM, Finding, Preset, Profile, Requirement, Subject, amount, at_least, at_most, within

ID = "astm-d638"
DESIGNATION = "ASTM D638-14"

# Fig. 1, per type, in metres: the narrow section's width W and length L, the least overall width WO and length LO, the gage length G, the
# distance between the grips D, the fillet radius R and Type IV's outer radius RO; then each one's tolerance, and the thickness range.
FIG1 = {
    "I": {"W": 13 * MM, "L": 57 * MM, "WO": 19 * MM, "LO": 165 * MM, "G": 50 * MM, "D": 115 * MM, "R": 76 * MM, "RO": None,
          "tol": {"W": 0.5 * MM, "L": 0.5 * MM, "WO": 6.4 * MM, "G": 0.25 * MM, "D": 5 * MM, "R": 1 * MM}, "t": (0.0, 7 * MM)},
    "II": {"W": 6 * MM, "L": 57 * MM, "WO": 19 * MM, "LO": 183 * MM, "G": 50 * MM, "D": 135 * MM, "R": 76 * MM, "RO": None,
           "tol": {"W": 0.5 * MM, "L": 0.5 * MM, "WO": 6.4 * MM, "G": 0.25 * MM, "D": 5 * MM, "R": 1 * MM}, "t": (0.0, 7 * MM)},
    "III": {"W": 19 * MM, "L": 57 * MM, "WO": 29 * MM, "LO": 246 * MM, "G": 50 * MM, "D": 115 * MM, "R": 76 * MM, "RO": None,
            "tol": {"W": 0.5 * MM, "L": 0.5 * MM, "WO": 6.4 * MM, "G": 0.25 * MM, "D": 5 * MM, "R": 1 * MM}, "t": (7 * MM, 14 * MM)},
    "IV": {"W": 6 * MM, "L": 33 * MM, "WO": 19 * MM, "LO": 115 * MM, "G": 25 * MM, "D": 65 * MM, "R": 14 * MM, "RO": 25 * MM,
           "tol": {"W": 0.5 * MM, "L": 0.5 * MM, "WO": 6.4 * MM, "G": 0.13 * MM, "D": 5 * MM, "R": 1 * MM, "RO": 1 * MM}, "t": (0.0, 4 * MM)},
    "V": {"W": 3.18 * MM, "L": 9.53 * MM, "WO": 9.53 * MM, "LO": 63.5 * MM, "G": 7.62 * MM, "D": 25.4 * MM, "R": 12.7 * MM, "RO": None,
          "tol": {"W": 0.03 * MM, "L": 0.08 * MM, "WO": 3.18 * MM, "G": 0.02 * MM, "D": 5 * MM, "R": 0.08 * MM}, "t": (0.0, 4 * MM)},
}
TYPES = tuple(FIG1)
FIG1_CLAUSE = {"I": "Fig. 1", "II": "Fig. 1", "III": "Fig. 1", "IV": "Fig. 1", "V": "Fig. 1, note C"}  # Type V's bands are footnote C's
MAX_THICKNESS = 14 * MM  # §1.2: thicker material is machined down
THIN_SHEET = 1.0 * MM  # §1.2: below this, D882 is the preferred method
MOLDED_THICKNESS, MOLDED_BAND = 3.2 * MM, 0.4 * MM  # Fig. 1 note A: molded specimens, and Types I and II where possible
PREFERRED = "I"  # §6.1.1: the preferred type where material 7 mm thick or less is at hand


def _preset(key: str, label: str) -> Preset:
    f = FIG1[key]
    si = {"width": f["WO"], "length": f["LO"], "tab_length": (f["LO"] - f["D"]) / 2, "narrow_width": f["W"], "narrow_length": f["L"],
          "radius": f["R"], "strain_length": f["G"]}
    if f["RO"] is not None:
        si["outer_radius"] = f["RO"]
    thickness = MOLDED_THICKNESS if key in ("I", "II") else None
    return Preset(key, label, FIG1_CLAUSE[key], si=si, minimum=("width", "length"), thickness=thickness,
                  note="the overall width and length are the least allowed; the grips leave the distance D between them; the extensometer "
                       "spans the gage length G")


TYPE_I = _preset("I", "Type I: 13 mm wide over 57 mm, for material 7 mm thick or less (the preferred type)")
TYPE_II = _preset("II", "Type II: 6 mm wide over 57 mm, for material 7 mm thick or less that will not break in Type I's narrow section")
TYPE_III = _preset("III", "Type III: 19 mm wide over 57 mm, for material over 7 mm and up to 14 mm thick")
TYPE_IV = _preset("IV", "Type IV: 6 mm wide over 33 mm with two radii, for material 4 mm thick or less, nonrigid or compared across rigidity")
TYPE_V = _preset("V", "Type V: 3.18 mm wide over 9.53 mm, for material 4 mm thick or less when little is at hand")
VARIANTS = (TYPE_I, TYPE_II, TYPE_III, TYPE_IV, TYPE_V)


def _fig1(s: Subject) -> dict | None:
    return FIG1.get(s.variant or "")


def _no_type(s: Subject, asked: str) -> Finding:
    return Finding(None, "no specimen type named", asked)


def _matrix(s: Subject) -> Finding:
    asked = "a plastic, unreinforced or reinforced; a resin-matrix composite with fibres stiffer than 20 GPa is tested by ASTM D3039/D3039M"
    if s.isotropic:
        return Finding(True, "one isotropic material, stated by its modulus and Poisson's ratio", asked)
    if s.family is None:
        return Finding(None, "your own ply constants: state in the notes whether the fibres are stiffer than 20 GPa", asked)
    return Finding(False, f"{s.family.lower()}: fibres far stiffer than 20 GPa, whose tensile test is ASTM D3039/D3039M", asked)


def _max_thickness(s: Subject) -> Finding:
    return Finding(at_most(s.thickness, MAX_THICKNESS), amount(s.thickness, s.units),
                   f"at most {amount(MAX_THICKNESS, s.units)}; thicker material is machined down")


def _thin_sheet(s: Subject) -> Finding:
    return Finding(at_least(s.thickness, THIN_SHEET), amount(s.thickness, s.units),
                   f"at least {amount(THIN_SHEET, s.units)}; thinner sheet and film are better tested by ASTM D882")


def _shape(s: Subject) -> Finding:
    if s.hole_diameter is not None:
        return Finding(False, "a strip with a hole", "a dumbbell specimen of Fig. 1")
    return Finding(s.dogbone, "a dog-bone" if s.dogbone else "a straight strip", "a dumbbell specimen of Fig. 1")


def _type_thickness(s: Subject) -> Finding:
    f = _fig1(s)
    if f is None:
        return _no_type(s, "the thickness range of the type")
    low, high = f["t"]
    ok = at_most(s.thickness, high) and (low == 0.0 or s.thickness > low * (1 + 1e-9))
    asked = (f"over {amount(low, s.units)} and up to {amount(high, s.units)}" if low else f"up to {amount(high, s.units)}") + f" for Type {s.variant}"
    return Finding(ok, amount(s.thickness, s.units), asked)


def _composite_type(s: Subject) -> Finding:
    asked = "Type I for a reinforced composite"
    if s.isotropic:
        return Finding(None, "one isotropic material, not a reinforced composite", asked)
    if s.variant is None:
        return _no_type(s, asked)
    return Finding(s.variant == "I", f"a laminate of plies as Type {s.variant}", asked)


def _band(name: str, words: str, read: Callable[[Subject], float | None]) -> Callable[[Subject], Finding]:
    """A size of Fig. 1 within its tolerance band."""
    def rule(s: Subject) -> Finding:
        f = _fig1(s)
        if f is None:
            return _no_type(s, f"Fig. 1's {words}")
        have = read(s)
        want, tol = f[name], f["tol"][name]
        asked = f"{amount(want, s.units)} ± {amount(tol, s.units)} for Type {s.variant}"
        if have is None:
            return Finding(False, "a straight strip, which has none", asked)
        return Finding(within(have, want, tol), amount(have, s.units), asked)
    return rule


def _overall_width(s: Subject) -> Finding:
    f = _fig1(s)
    if f is None:
        return _no_type(s, "Fig. 1's least overall width")
    low, high = f["WO"], f["WO"] + f["tol"]["WO"]
    return Finding(at_least(s.width, low) and at_most(s.width, high), amount(s.width, s.units),
                   f"at least {amount(low, s.units)}, up to {amount(high, s.units)}, for Type {s.variant}")


def _overall_length(s: Subject) -> Finding:
    f = _fig1(s)
    if f is None:
        return _no_type(s, "Fig. 1's least overall length")
    return Finding(at_least(s.length, f["LO"]), amount(s.length, s.units), f"at least {amount(f['LO'], s.units)} for Type {s.variant}")


def _grip_distance(s: Subject) -> Finding:
    f = _fig1(s)
    if f is None:
        return _no_type(s, "Fig. 1's distance between the grips")
    have = s.length - 2 * s.tab_length
    words = amount(have, s.units) + (" between the grips" if s.tab_length else ": the model holds only the end rows")
    return Finding(within(have, f["D"], f["tol"]["D"]), words, f"{amount(f['D'], s.units)} ± {amount(f['tol']['D'], s.units)} for Type {s.variant}")


def _outer_radius(s: Subject) -> Finding:
    f = _fig1(s)
    if f is None:
        return _no_type(s, "Type IV's outer radius, and none on the other types")
    if f["RO"] is None:
        return Finding(s.outer_radius is None, "none" if s.outer_radius is None else amount(s.outer_radius, s.units),
                       f"none: Type {s.variant} has the fillet alone")
    return _band("RO", "outer radius", lambda x: x.outer_radius)(s)


def _gauge(s: Subject) -> Finding:
    f = _fig1(s)
    asked = "an extensometer over the full gage length" + (f": {amount(f['G'], s.units)} ± {amount(f['tol']['G'], s.units)} for Type {s.variant}"
                                                             if f is not None else "")
    if s.strain_device != "extensometer":
        return Finding(None, "no extensometer" if s.strain_device is None else "a strain gauge (an alternative for Poisson's ratio, Note A3.3)", asked)
    if f is None:
        return _no_type(s, asked)
    return Finding(within(s.strain_length, f["G"], f["tol"]["G"]), amount(s.strain_length, s.units), asked)


def _molded_thickness(s: Subject) -> Finding:
    asked = f"{amount(MOLDED_THICKNESS, s.units)} ± {amount(MOLDED_BAND, s.units)} for Types I and II where possible, and for every molded specimen"
    if s.variant not in ("I", "II"):
        return Finding(None, amount(s.thickness, s.units) + (f" (Type {s.variant}: for a molded specimen only)" if s.variant else ""), asked)
    return Finding(within(s.thickness, MOLDED_THICKNESS, MOLDED_BAND), amount(s.thickness, s.units), asked)


def _preferred(s: Subject) -> Finding:
    asked = "Type I where material 7 mm thick or less is at hand"
    if s.variant is None:
        return _no_type(s, asked)
    if not at_most(s.thickness, FIG1["I"]["t"][1]):
        return Finding(None, f"Type {s.variant}, {amount(s.thickness, s.units)} thick: Type III's range", asked)
    return Finding(s.variant == PREFERRED, f"Type {s.variant}", asked + "; Type II when Type I breaks outside its narrow section, Type V when little "
                                                                       "material is at hand, Type IV to compare nonrigid and semirigid plastics")


def _anisotropy(s: Subject) -> Finding:
    if s.isotropic:
        return Finding(True, "one isotropic material", "")
    return Finding(False, "a laminate of plies", "specimens cut along and across the suspected direction of anisotropy, five of each")


def _narrow(s: Subject) -> float | None:
    return s.narrow_width


def _narrow_length(s: Subject) -> float | None:
    return s.narrow_length


def _radius(s: Subject) -> float | None:
    return s.fillet_radius


REQUIREMENTS = (
    Requirement("scope-material", "§1.1, Note 4", "scope", "The material is a plastic, unreinforced or reinforced. A resin-matrix composite reinforced "
                "by oriented fibres stiffer than 20 GPa is tested by ASTM D3039/D3039M instead.", _matrix, ("library", "own_name")),
    Requirement("scope-thickness", "§1.2", "scope", "The specimen is at most 14 mm thick; thicker material is machined down to 14 mm.", _max_thickness,
                ("thickness",)),
    Requirement("shape", "§6.1, Fig. 1", "mandatory", "The specimen is a dumbbell of Fig. 1: a narrow section joined to wider ends by fillets.", _shape,
                ("test",)),
    Requirement("type-thickness", "§6.1.1, Fig. 1", "mandatory", "The thickness lies in the type's range: up to 7 mm for Types I and II, over 7 mm "
                "and up to 14 mm for Type III, up to 4 mm for Types IV and V.", _type_thickness, ("thickness", "specimen")),
    Requirement("composite-type", "§6.1.3", "mandatory", "A reinforced composite, a highly orthotropic laminate included, is tested as Type I.",
                _composite_type, ("specimen",)),
    Requirement("narrow-width", "Fig. 1", "mandatory", "The narrow section's width W is the type's, within its band.", _band("W", "narrow width", _narrow),
                ("narrow_width",)),
    Requirement("narrow-length", "Fig. 1", "mandatory", "The narrow section's length L is the type's, within its band.",
                _band("L", "narrow length", _narrow_length), ("narrow_length",)),
    Requirement("fillet-radius", "Fig. 1", "mandatory", "The fillet radius R is the type's, within its band.", _band("R", "fillet radius", _radius),
                ("radius",)),
    Requirement("outer-radius", "Fig. 1", "mandatory", "Type IV's outer radius RO is 25 mm within its band; the other types have none.", _outer_radius,
                ("outer_radius",)),
    Requirement("overall-width", "Fig. 1", "mandatory", "The overall width WO is at least the type's, and at most that plus its tolerance (our reading "
                "of the plus tolerance).", _overall_width, ("width",)),
    Requirement("overall-length", "Fig. 1", "mandatory", "The overall length LO is at least the type's; longer is allowed.", _overall_length, ("length",)),
    Requirement("grip-distance", "§10.2, Fig. 1", "mandatory", "The distance D between the grips is the type's, within 5 mm.", _grip_distance,
                ("tab_length", "length")),
    Requirement("gauge-length", "§5.2, Fig. 1", "recommended", "An extensometer spans the full gage length G, within its band; for referee tests it "
                "must.", _gauge, ("strain_length",)),
    Requirement("molded-thickness", "Fig. 1, note A", "recommended", "A molded specimen, and a Type I or II specimen where possible, is 3.2 mm thick "
                "within 0.4 mm.", _molded_thickness, ("thickness",)),
    Requirement("preferred-type", "§6.1.1", "recommended", "Type I is the preferred specimen where material 7 mm thick or less is at hand.", _preferred,
                ("specimen",)),
    Requirement("thin-sheet", "§1.2", "recommended", "Sheet or film thinner than 1.0 mm is better tested by ASTM D882.", _thin_sheet, ("thickness",)),
    Requirement("anisotropy", "§6.6, §7.2", "note", "A material suspected of anisotropy is tested with specimens cut along and across its suspected "
                "direction, five of each.", _anisotropy, ("library", "own_name")),
    Requirement("centre-width", "Fig. 1, note E", "lab", "The width at the centre is W to 0.10 mm less, any narrowing gradual and equal on both sides."),
    Requirement("die-width", "Fig. 1, note B", "lab", "A Type IV die's narrow section is 6.00 mm wide within 0.05 mm."),
    Requirement("surfaces", "§6.4", "lab", "Surfaces are free of visible flaws; machining marks are filed and sanded away along the long axis; molded "
                "flash is removed."),
    Requirement("gage-marks", "§6.5", "lab", "Gage marks are drawn in wax crayon or India ink, never scratched, punched or pressed in."),
    Requirement("grips", "§5.1.3", "lab", "The grips are fixed or self-aligning, hold the specimen without slipping, and align its long axis with the "
                "pull."),
    Requirement("extensometer-class", "§5.2.1, §10.3", "lab", "A modulus is measured with an extensometer of Class B-2 or better (ASTM E83) that "
                "records continuously; elongation up to 20 % needs at least Class C."),
    Requirement("specimens", "§7.1, §7.2", "lab", "At least five specimens per sample; for an anisotropic material, five along and five across its "
                "principal direction."),
    Requirement("breaks", "§7.3", "lab", "A specimen that breaks at a flaw or outside the narrow section is discarded and retested."),
    Requirement("speed", "§8, Table 1", "lab", "The speed is the lowest in Table 1 for the specimen and rigidity that breaks it in 0.5 to 5 minutes: "
                "5 mm/min (±25 %) is the lowest for rigid and semirigid Types I to IV, 1 mm/min for Type V."),
    Requirement("conditioning", "§9", "lab", "Specimens are conditioned by Procedure A of ASTM D618 and tested in the same atmosphere."),
    Requirement("measure", "§10.1", "lab", "Width and thickness are measured to 0.025 mm at the centre and within 5 mm of each end of the gage length."),
    Requirement("jaw-separation", "Note 11", "lab", "The separation of the jaws is never used for the modulus or the elongation."),
    Requirement("toe", "§11.1, Annex A1", "lab", "The toe of the curve is compensated unless it is the material's own response."),
    Requirement("strength", "§11.2", "lab", "The tensile strength is the greatest force over the average original cross-section in the gage length, "
                "to three significant figures."),
    Requirement("modulus", "§11.4, §11.5", "lab", "The modulus is the slope of the initial straight part of the curve over the average original "
                "cross-section; with no straight part, a secant modulus at a stated strain."),
    Requirement("poisson", "Annex A3", "lab", "Poisson's ratio is measured at 5 mm/min after a preload under 5 N, to at least 0.5 % strain, with a "
                "transverse extensometer across the width; with no straight part, over 0.05 % to 0.25 % axial strain."),
)

PROFILE = Profile(
    id=ID, designation=DESIGNATION, title="Tensile properties of plastics", kinds=("unnotched_tension",),
    catalog_url="https://store.astm.org/d0638-14.html",
    edition_note="read from the D638-14 copy the founder supplied; a later edition, D638-22, is active and was not read (that its values are unchanged is UNVERIFIED)",
    systems="SI; the inch-pound values are for information only (§1.5)",
    requirements=REQUIREMENTS, variants=VARIANTS, variant_words=TYPES, variant_noun="Type", aliases=("d638",),
)
