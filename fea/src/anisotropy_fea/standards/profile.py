"""What a test standard asks of a coupon, written as data our checks read (ADR-0072).

A `Profile` holds one standard: its designation and edition, the tests it covers, the specimens or classes it names with their sizes, and
its `Requirement`s. A requirement names its clause, its level and what it asks, in our words: never the standard's text, tables or
figures (ADR-0018 amendment 1: individual values, each with its clause). A requirement with a rule is judged on a `Subject`, the coupon as
the spec states it, in SI; one without a rule is the laboratory's and is listed, never judged.

Levels:
- `scope`: what the standard covers (the material, the laminate). A miss means the coupon lies outside the standard.
- `mandatory`: what the standard requires of the specimen. A miss is a deviation the report must state.
- `recommended`: what the standard suggests. A miss is an advisory.
- `note`: a caution the standard gives; shown when it applies, never counted.
- `lab`: a clause of the procedure (specimens, conditioning, speed, alignment, failure mode): the laboratory's, listed for its report.

A coupon that misses a requirement still runs; it is labelled a deviation and never said to conform (ADR-0072).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any
from dataclasses import dataclass, field

from anisotropy_engine.units import INCH

from ..units import UNIT_LABEL, from_si

LEVELS = ("scope", "mandatory", "recommended", "note", "lab")
STATES = ("met", "deviation", "advisory", "note", "lab", "na")  # na: the requirement does not apply to this coupon, or cannot be judged
INCH_POUND_SYSTEMS = ("in-psi", "in-ksi")  # the systems a standard's inch-pound values are read in
MM = 1e-3
RELATIVE = 1e-9  # numerical noise allowed in a comparison of two SI values


@dataclass(frozen=True)
class Subject:
    """The coupon a profile judges, as its spec states it, in SI (lengths in metres, angles in degrees)."""

    kind: str
    units: str  # the system the coupon is stated in: how a value is shown, and which of a standard's systems it is held to
    length: float
    width: float
    tab_length: float  # the gripped length at each end; 0 when only the end rows are held
    hole_diameter: float | None
    angles: tuple[float, ...]  # every ply, bottom first, from the length axis, in (-90, 90] (ADR-0065)
    ply_thickness: float
    family: str | None  # the library record's family ("Carbon / epoxy"); None for the team's own constants
    architecture: str | None  # the library record's architecture ("Unidirectional ...", "Woven ..."); None for own constants
    variant: str | None = None  # the standard's specimen, when it names more than one
    strain_device: str | None = None  # "extensometer" or "strain gauge"
    strain_length: float | None = None  # the extensometer's gauge length or the strain gauge's active length
    tab_thickness: float | None = None  # bonded tabs, when given
    tab_bevel: float | None = None  # degrees
    tab_material: str | None = None

    @property
    def thickness(self) -> float:
        return len(self.angles) * self.ply_thickness

    @property
    def gauge_length(self) -> float:
        """The free length between the grips."""
        return self.length - 2 * self.tab_length

    @property
    def inch_pound(self) -> bool:
        return self.units in INCH_POUND_SYSTEMS


@dataclass(frozen=True)
class Finding:
    """What a rule found: whether the coupon meets the requirement (None: it does not apply, or cannot be judged), this coupon's value
    and what the clause asks, both in words in the coupon's units."""

    ok: bool | None
    value: str
    limit: str


@dataclass(frozen=True)
class Requirement:
    id: str
    clause: str  # "Table 1", "§6.4": where the reader finds it in their own copy
    level: str
    text: str  # what it asks, in our words
    rule: Callable[[Any], Finding] | None = None  # judged on a Subject (a coupon) or a TowSubject (ADR-0074); None for the laboratory's clauses
    rows: tuple[str, ...] = ()  # the form rows it concerns, by key

    def __post_init__(self) -> None:
        assert self.level in LEVELS, self.level
        assert (self.rule is None) == (self.level == "lab"), f"{self.id}: a laboratory clause has no rule, every other level has one"


@dataclass(frozen=True)
class Preset:
    """A size the standard names: a specimen (C1869 A and B) or a class of laminate (D3039 Table 2), by form row.

    `si` holds the values in SI (lengths in metres, angles in degrees). `inch_pound` holds the standard's own inch-pound values (lengths in
    inches) when it states them separately (D3039 §1.2); a coupon stated in inches is held to those, not to converted millimetres.
    `minimum` names the rows whose value is the least the standard allows; `thickness` is the laminate thickness it suggests.
    """

    key: str
    label: str
    clause: str
    si: dict[str, float]
    inch_pound: dict[str, float] | None = None
    minimum: tuple[str, ...] = ()
    thickness: float | None = None  # SI
    thickness_inch: float | None = None
    note: str = ""

    def values_in(self, units: str) -> dict[str, float]:
        """The preset's rows in the stated system: the standard's inch values for a coupon stated in inches when it has them, else SI converted."""
        if units in INCH_POUND_SYSTEMS and self.inch_pound is not None:
            return {key: value if key in ANGLE_ROWS else from_si(value * INCH, "length", units) for key, value in self.inch_pound.items()}
        return {key: value if key in ANGLE_ROWS else from_si(value, "length", units) for key, value in self.si.items()}

    def si_values(self, units: str) -> dict[str, float]:
        """The preset's rows in SI for a coupon stated in `units` (the inch values converted for an inch-stated coupon)."""
        if units in INCH_POUND_SYSTEMS and self.inch_pound is not None:
            return {key: value if key in ANGLE_ROWS else value * INCH for key, value in self.inch_pound.items()}
        return dict(self.si)

    def thickness_si(self, units: str) -> float | None:
        if units in INCH_POUND_SYSTEMS and self.thickness_inch is not None:
            return self.thickness_inch * INCH
        return self.thickness


ANGLE_ROWS = ("tab_bevel",)  # preset rows in degrees, never converted


@dataclass(frozen=True)
class Profile:
    id: str  # what a spec's [test_method] names
    designation: str  # what the form's Standard row and the spec's coupon.standard carry
    title: str  # the standard's subject, in our words
    kinds: tuple[str, ...]  # the spec kinds it covers; "fibre_tow" for the tow test, which is no spec kind (ADR-0074)
    catalog_url: str  # the publisher's page for the standard; the text itself is never in this repository
    edition_note: str  # which copy was read, and what is known of the active edition
    systems: str  # "SI" or "SI and inch-pound, separately (§1.2)"
    requirements: tuple[Requirement, ...]
    variants: tuple[Preset, ...] = ()  # specimens the form's Specimen row names
    variant_words: tuple[str, ...] = ()  # the words the Specimen row takes for this standard (the variants' keys, and "other" when allowed)
    classes: tuple[Preset, ...] = ()  # sizes recommended per class of laminate, the class read from the layup
    classify: Callable[[Subject], Preset | None] | None = None
    requires_strain: bool = False  # the standard counts the strain measurement in its rules, so the form requires it
    aliases: tuple[str, ...] = ()  # short names a person types: "d3039"
    rights: str = "licensed-reference"  # ADR-0018: individual values with their clause; readers consult their own copy
    organisation: str = "ASTM International"
    notes: tuple[str, ...] = field(default=())


# --- helpers the rules share --------------------------------------------------------------------


def amount(value_si: float, units: str, kind: str = "length") -> str:
    """An SI value in the coupon's units, as a reader reads it: '36 mm', '1.42 in'."""
    return f"{from_si(value_si, kind, units):.4g} {UNIT_LABEL[units][kind]}"


def ratio(value: float) -> str:
    """A ratio to three significant figures, as the standards report them."""
    return f"{value:.3g}"


def at_least(value: float, limit: float) -> bool:
    return value >= limit * (1 - RELATIVE)


def at_most(value: float, limit: float) -> bool:
    return value <= limit * (1 + RELATIVE)


def within(value: float, nominal: float, tolerance: float) -> bool:
    """A nominal value inside the band the standard gives for the specimen: a model stated anywhere in it is a specimen the standard takes."""
    return abs(value - nominal) <= tolerance * (1 + RELATIVE) + RELATIVE * abs(nominal)


def same(value: float, nominal: float) -> bool:
    return math.isclose(value, nominal, rel_tol=1e-6, abs_tol=1e-12)


def is_symmetric(angles: tuple[float, ...]) -> bool:
    """The stack is a mirror image of itself about the mid-plane (the definition ASTM D3878 gives, as C1869 A2.2.1.20 quotes it); every
    ply of a coupon has one thickness."""
    return all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(angles, reversed(angles)))


def is_balanced(angles: tuple[float, ...]) -> bool:
    """For every ply at +theta an identical ply at -theta, 0 and 90 needing none (D3878's definition, as C1869 A2.2.1.3 quotes it). A
    fabric ply is counted by its stated angle like a tape ply, as the definition counts plies."""
    off_axis = [round(a, 9) for a in angles if not (math.isclose(a, 0.0, abs_tol=1e-9) or math.isclose(abs(a), 90.0, abs_tol=1e-9))]
    return all(off_axis.count(a) == off_axis.count(-a) for a in off_axis)


def laminate_words(angles: tuple[float, ...]) -> str:
    balanced, symmetric = is_balanced(angles), is_symmetric(angles)
    if balanced and symmetric:
        return "balanced and symmetric"
    return ", ".join(w for w in ("balanced" if balanced else "not balanced", "symmetric" if symmetric else "not symmetric"))


def is_tape(subject: Subject) -> bool | None:
    """Whether the material is a unidirectional tape, from the library record's architecture; None for the team's own constants."""
    if subject.architecture is None:
        return None
    return subject.architecture.lower().startswith("unidirectional")


# The library's families by matrix: every family a record carries must be in one of the two (tests/test_standards.py holds it).
POLYMER_FAMILIES = ("Carbon / epoxy", "Glass / epoxy", "Carbon / PEEK", "Carbon / cyanate ester")
OTHER_FAMILIES = ("Sandwich cores",)
