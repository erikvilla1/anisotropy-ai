"""Unit systems an Abaqus deck may be written in (ADR-0002, ADR-0003).

An Abaqus deck carries no units. The caller states one of the systems below, the reader converts
every dimensioned number to SI base units on entry (`model.to_si`), and results convert back on
exit. Nothing is inferred from the numbers.
"""

from __future__ import annotations

# Factor that multiplies a deck value to give the SI base value. Force is the product of stress and
# length squared, so MPa with mm gives newtons and Pa with m gives newtons: the factor is 1 in both.
DECK_UNIT_SYSTEMS: dict[str, dict[str, float]] = {
    "mm-MPa": {"length": 1e-3, "stress": 1e6, "force": 1.0, "force_per_length": 1e3, "per_length": 1e3},
    "m-Pa": {"length": 1.0, "stress": 1.0, "force": 1.0, "force_per_length": 1.0, "per_length": 1.0},
}

# force_per_length: a section force resultant, N/mm or N/m; per_length: a curvature, 1/mm or 1/m. A moment resultant per unit width
# (N mm/mm or N m/m) is numerically a force in both systems, so it converts with the "force" kind and is labelled "moment".
KINDS = ("length", "stress", "force", "force_per_length", "per_length")

# How each kind is written for a reader, per system: the documents, the studio and the case pages share one table.
UNIT_LABEL: dict[str, dict[str, str]] = {
    "mm-MPa": {"force": "N", "length": "mm", "stress": "MPa", "force_per_length": "N/mm", "modulus": "GPa", "stiffness": "N/mm",
               "per_length": "1/mm", "moment": "N·mm/mm", "rotation": "rad"},
    "m-Pa": {"force": "N", "length": "m", "stress": "Pa", "force_per_length": "N/m", "modulus": "GPa", "stiffness": "N/m",
             "per_length": "1/m", "moment": "N·m/m", "rotation": "rad"},
}


def unit_factors(units: str | None) -> dict[str, float]:
    """The conversion factors for a stated unit system; refuses anything else, including no statement."""
    if units not in DECK_UNIT_SYSTEMS:
        known = ", ".join(repr(name) for name in DECK_UNIT_SYSTEMS)
        raise ValueError(f"units must be stated as one of {known}; got {units!r}. An Abaqus deck carries no units.")
    return DECK_UNIT_SYSTEMS[units]


def to_si(value: float, kind: str, units: str | None) -> float:
    """One deck value of the given kind, in SI."""
    return value * unit_factors(units)[kind]


def from_si(value: float, kind: str, units: str | None) -> float:
    """One SI value of the given kind, back in the deck's units."""
    return value / unit_factors(units)[kind]
