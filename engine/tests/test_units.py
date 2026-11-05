import json
from pathlib import Path

import pytest

from anisotropy_engine.units import PSI, UNIT_SYSTEMS


def test_psi_follows_the_exact_inch_and_pound_force_definitions():
    assert PSI == pytest.approx(6894.757293168361, rel=1e-15)


def test_every_unit_system_covers_the_same_quantities():
    quantities = {name: set(system) for name, system in UNIT_SYSTEMS.items()}
    assert set(quantities) == {"SI", "mm-MPa", "US", "psi"}
    assert quantities["US"] == quantities["SI"] == quantities["psi"] == quantities["mm-MPa"]


@pytest.mark.parametrize("system, kind, value, si_value", [
    ("US", "modulus", 1.0, 6.894757293e9),   # 1 Msi
    ("US", "stress", 1.0, 6.894757293e6),    # 1 ksi
    ("psi", "modulus", 2.13e7, 146.8583e9),  # 21.3 Msi
    ("SI", "A", 60.24, 60.24e6),             # MN/m
    ("US", "N", 1.0, 175.1268),              # lb/in in N/m
    ("US", "alpha", 1.0, 1.8),               # 1/degF in 1/K
    ("psi", "delta_T", 9.0, 5.0),            # a change of 9 degF is 5 K
])
def test_conversions_to_si(system, kind, value, si_value):
    assert value * UNIT_SYSTEMS[system][kind][0] == pytest.approx(si_value, rel=1e-6)


# --------------------------------------------------------------------------- a value with its own unit (ADR-0060)

from anisotropy_engine.units import INCH, LBF, QUANTITY_DIMENSIONS, UNITS, from_si, in_system, to_si, units_of  # noqa: E402

UNITS_JSON = Path(__file__).resolve().parents[1] / "src" / "anisotropy_engine" / "data" / "units.json"


def test_the_mm_mpa_system_is_the_coupon_decks_millimetre_newton_system():
    mm = UNIT_SYSTEMS["mm-MPa"]
    assert mm["stress"] == (1e6, "MPa") and mm["length"] == (1e-3, "mm")
    assert mm["N"] == (1e3, "N/mm") and mm["M"][0] == 1.0 and mm["A"] == (1e3, "N/mm") and mm["D"] == (1e-3, "N*mm")
    assert 100.0 * mm["N"][0] == 100e3  # 100 N/mm is 100 kN/m


@pytest.mark.parametrize("value, unit, kind, si_value", [
    (147.0, "GPa", "modulus", 147e9),
    (10300.0, "MPa", "modulus", 10.3e9),
    (21.3, "Msi", "modulus", 21.3e6 * PSI),
    (57.0, "MPa", "stress", 57e6),
    (8.27, "ksi", "stress", 8.27e3 * PSI),
    (0.125, "mm", "length", 0.125e-3),
    (0.0049, "in", "length", 0.0049 * INCH),
    (100.0, "N/mm", "N", 100e3),
    (571.0, "lb/in", "N", 571.0 * LBF / INCH),
    (2.5, "kN*m/m", "M", 2500.0),
    (3.0, "N*mm/mm", "M", 3.0),
])
def test_a_value_with_its_own_unit_converts_to_si(value, unit, kind, si_value):
    assert to_si(value, unit, kind) == pytest.approx(si_value, rel=1e-12)
    assert from_si(si_value, unit, kind) == pytest.approx(value, rel=1e-12)


def test_a_value_lands_in_a_reporting_systems_unit():
    assert in_system(10300.0, "MPa", "modulus", "SI") == pytest.approx(10.3)  # GPa
    assert in_system(100.0, "N/mm", "N", "SI") == pytest.approx(100e3)  # N/m
    assert in_system(100.0, "N/mm", "N", "US") == pytest.approx(100e3 * INCH / LBF)  # lb/in
    assert in_system(0.125, "mm", "length", "US") == pytest.approx(0.125e-3 / INCH)  # in
    with pytest.raises(ValueError, match="units must be one of"):
        in_system(1.0, "mm", "length", "cgs")


def test_a_unit_of_the_wrong_dimension_or_an_unknown_one_is_refused_by_name():
    with pytest.raises(ValueError, match="mm is not a modulus unit; one of Pa, kPa, MPa, GPa, psi, ksi, Msi"):
        to_si(1.0, "mm", "modulus")
    with pytest.raises(ValueError, match="unknown unit 'bar' for stress"):
        to_si(1.0, "bar", "stress")
    with pytest.raises(ValueError, match="unknown unit 'gpa'"):  # names are exact: the caller normalises, the engine never guesses
        to_si(1.0, "gpa", "modulus")
    with pytest.raises(ValueError, match="no units are listed for 'kappa'"):
        units_of("kappa")


def test_the_websites_unit_names_match_the_engines_table():
    """The site offers the names in data/units.json; the factors live only here."""
    doc = json.loads(UNITS_JSON.read_text(encoding="utf-8"))
    by_dimension: dict[str, list[str]] = {}
    for name, (dimension, _factor) in UNITS.items():
        by_dimension.setdefault(dimension, []).append(name)
    assert doc["units"] == by_dimension
    assert doc["kinds"] == QUANTITY_DIMENSIONS
    for system, labels in doc["systems"].items():
        for kind, label in labels.items():
            assert UNIT_SYSTEMS[system][kind][1] == label, (system, kind)
    assert set(doc["systems"]) == set(UNIT_SYSTEMS)
    for kind in QUANTITY_DIMENSIONS:
        for system in UNIT_SYSTEMS:
            label = UNIT_SYSTEMS[system][kind][1]
            assert label in UNITS and UNITS[label][0] == QUANTITY_DIMENSIONS[kind], (system, kind, label)  # a system's unit is one a value may carry
            assert UNITS[label][1] == pytest.approx(UNIT_SYSTEMS[system][kind][0], rel=1e-15)
