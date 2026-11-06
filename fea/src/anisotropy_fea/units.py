"""Unit systems: what a coupon is stated in, and what a deck is written in (ADR-0002, ADR-0003, ADR-0061).

A coupon is stated in one of `UNIT_SYSTEMS`, and its results, its checklist and its document come back in the same system; the
engine works in SI base units in between (ADR-0002). An Abaqus or CalculiX deck carries no units, so every deck we write is in a
deck system, `deck_units_of` the stated one: the two metric systems a deck may be written in, and mm-MPa for a coupon stated in
inches and pounds. The caller states a deck's system, the reader converts every dimensioned number to SI on entry (`model.to_si`),
and nothing is inferred from the numbers.
"""

from __future__ import annotations

from anisotropy_engine.units import INCH, LBF, PSI  # one set of constants for the whole repository (ADR-0002)


def _system(length: float, stress: float, force: float) -> dict[str, float]:
    """The factors that multiply a stated value to give the SI base value: a section force resultant is a force per length, a
    curvature is one per length. A moment resultant per unit width (N mm/mm, lbf in/in) is numerically a force in every system, so
    it converts with the "force" kind and is labelled "moment"."""
    return {"length": length, "stress": stress, "force": force, "force_per_length": force / length, "per_length": 1.0 / length}


# Force is the product of stress and length squared, so MPa with mm gives newtons and Pa with m gives newtons: the factor is 1 in both.
UNIT_SYSTEMS: dict[str, dict[str, float]] = {
    "mm-MPa": _system(1e-3, 1e6, 1.0),
    "m-Pa": _system(1.0, 1.0, 1.0),
    "in-psi": _system(INCH, PSI, LBF),
    "in-ksi": _system(INCH, 1e3 * PSI, LBF),
}

# The systems an Abaqus deck is written in. A deck is unitless; every deck we write, read back and compare is in one of these two.
DECK_UNIT_SYSTEMS: dict[str, dict[str, float]] = {name: UNIT_SYSTEMS[name] for name in ("mm-MPa", "m-Pa")}
DECK_UNITS = "mm-MPa"  # the deck system of a coupon stated in a system a deck is not written in

KINDS = ("length", "stress", "force", "force_per_length", "per_length")

# How each kind is written for a reader, per system: the documents, the studio and the case pages share one table.
UNIT_LABEL: dict[str, dict[str, str]] = {
    "mm-MPa": {"force": "N", "length": "mm", "stress": "MPa", "force_per_length": "N/mm", "modulus": "GPa", "stiffness": "N/mm",
               "per_length": "1/mm", "moment": "N·mm/mm", "rotation": "rad"},
    "m-Pa": {"force": "N", "length": "m", "stress": "Pa", "force_per_length": "N/m", "modulus": "GPa", "stiffness": "N/m",
             "per_length": "1/m", "moment": "N·m/m", "rotation": "rad"},
    "in-psi": {"force": "lbf", "length": "in", "stress": "psi", "force_per_length": "lbf/in", "modulus": "Msi", "stiffness": "lbf/in",
               "per_length": "1/in", "moment": "lbf·in/in", "rotation": "rad"},
    "in-ksi": {"force": "lbf", "length": "in", "stress": "ksi", "force_per_length": "lbf/in", "modulus": "Msi", "stiffness": "lbf/in",
               "per_length": "1/in", "moment": "lbf·in/in", "rotation": "rad"},
}
assert set(UNIT_LABEL) == set(UNIT_SYSTEMS)


def unit_factors(units: str | None) -> dict[str, float]:
    """The conversion factors for a stated unit system; refuses anything else, including no statement."""
    if units not in UNIT_SYSTEMS:
        known = ", ".join(repr(name) for name in UNIT_SYSTEMS)
        raise ValueError(f"units must be stated as one of {known}; got {units!r}. Nothing is inferred from the numbers.")
    return UNIT_SYSTEMS[units]


def deck_unit_factors(units: str | None) -> dict[str, float]:
    """The conversion factors for the system a deck is stated in; refuses the systems a deck is not written in."""
    if units not in DECK_UNIT_SYSTEMS:
        known = ", ".join(repr(name) for name in DECK_UNIT_SYSTEMS)
        raise ValueError(f"units must be stated as one of {known}; got {units!r}. An Abaqus deck carries no units.")
    return DECK_UNIT_SYSTEMS[units]


def deck_units_of(units: str | None) -> str:
    """The system a deck is written in for a coupon stated in `units`: the stated system when a deck is written in it, else mm-MPa."""
    unit_factors(units)
    return units if units in DECK_UNIT_SYSTEMS else DECK_UNITS


def units_words(units: str | None) -> str:
    """A system as a person reads it: 'mm, MPa and N'."""
    unit_factors(units)
    lab = UNIT_LABEL[units]
    return f"{lab['length']}, {lab['stress']} and {lab['force']}"


def to_si(value: float, kind: str, units: str | None) -> float:
    """One stated value of the given kind, in SI."""
    return value * unit_factors(units)[kind]


def from_si(value: float, kind: str, units: str | None) -> float:
    """One SI value of the given kind, back in the stated units."""
    return value / unit_factors(units)[kind]
