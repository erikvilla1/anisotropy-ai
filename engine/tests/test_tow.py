"""The fibre tow calculations of ASTM D4018-23 (ADR-0074), checked against values worked by hand in the standard's own units.

The tow is a constructed one with round numbers (a 12K carbon tow of 0.800 g/m and 1.80 g/cm^3); no published test record is reproduced.
Each expected value is worked in the comment beside it, so the check does not repeat the engine's code.
"""

import math

import pytest

from anisotropy_engine.tow import (CHORD_LIMITS, PRELOAD_LIMITS, chord_strains, fibre_area, fibre_density, mass_per_unit_length, planning_loads,
                                   preload_strain, resin_content, sample_statistics, tow_chord_modulus, tow_strength)

G, M, G_PER_CM3 = 1e-3, 1.0, 1000.0  # kg per g; m; kg/m^3 per g/cm^3
MUL = 0.800 * G / M  # 0.800 g/m in kg/m
RHO = 1.80 * G_PER_CM3  # kg/m^3


def test_eq_1_mass_per_unit_length():
    assert mass_per_unit_length(0.800 * G, 1.000) == pytest.approx(MUL, rel=1e-15)  # 0.800 g over 1.000 m
    assert mass_per_unit_length(1.2345 * G, 1.5) == pytest.approx(0.823e-3, rel=1e-15)  # 1.2345 g / 1.5 m = 0.823 g/m


def test_eq_2_fibre_density_and_its_correction():
    assert fibre_density(1.80 * G_PER_CM3) == 1800.0  # no correction
    assert fibre_density(1.81 * G_PER_CM3, 0.01 * G_PER_CM3) == pytest.approx(1800.0, rel=1e-12)  # 1.81 - 0.01 = 1.80 g/cm^3
    with pytest.raises(ValueError, match="no positive fibre density"):
        fibre_density(1.8, 1.8)


def test_eq_3_resin_content():
    assert resin_content(0.800, 1.600) == pytest.approx(50.0, rel=1e-15)  # 100 (1 - 0.8/1.6)
    assert resin_content(0.800, 1.400) == pytest.approx(100 * (1 - 0.8 / 1.4), rel=1e-15)  # 42.857 %
    with pytest.raises(ValueError, match="must exceed the fibre's"):
        resin_content(0.8, 0.8)


def test_eq_4_strength_is_the_force_over_the_fibre_area():
    # In the standard's units: A P rho_f / MUL = 1 x 2200 N x 1.80 g/cm^3 / 0.800 g/m = 4950 MPa.
    assert tow_strength(2200.0, RHO, MUL) == pytest.approx(4950e6, rel=1e-12)
    assert fibre_area(MUL, RHO) == pytest.approx(0.8e-3 / 1800.0, rel=1e-15)  # 4.444e-7 m^2 = 0.4444 mm^2


def test_eq_5_chord_modulus_with_absolute_strains():
    # (P_u - P_l) rho_f / ((eps_u - eps_l) MUL) = 470 N x 1.80 / (0.005 x 0.800) = 211 500 MPa = 211.5 GPa.
    assert tow_chord_modulus(104.0, 574.0, 1000e-6, 6000e-6, RHO, MUL) == pytest.approx(211.5e9, rel=1e-12)


def test_eq_5_as_printed_gives_gpa_only_with_absolute_strains():
    """The finding ADR-0074 records: B = 1e-3 with P in N, rho_f in g/cm^3 and MUL in g/m gives GPa when the strains are absolute; with
    the strains in microstrain, as the standard lists them, the same arithmetic is off by a factor of 1e6."""
    B, dP, rho, mul = 1e-3, 470.0, 1.80, 0.800
    absolute = B * dP * rho / ((6000e-6 - 1000e-6) * mul)
    microstrain = B * dP * rho / ((6000 - 1000) * mul)
    engine_gpa = tow_chord_modulus(104.0, 574.0, 1000e-6, 6000e-6, RHO, MUL) / 1e9
    assert absolute == pytest.approx(engine_gpa, rel=1e-12)
    assert absolute / microstrain == pytest.approx(1e6, rel=1e-12)


def test_eq_5_refuses_an_empty_or_reversed_chord():
    with pytest.raises(ValueError, match="lower < upper"):
        tow_chord_modulus(100, 500, 3000e-6, 1000e-6, RHO, MUL)
    with pytest.raises(ValueError, match="must exceed the force at the lower strain"):
        tow_chord_modulus(500, 100, 1000e-6, 3000e-6, RHO, MUL)


@pytest.mark.parametrize("strain, preload, chord", [
    (21000e-6, 200e-6, (1000e-6, 6000e-6)),  # a standard-modulus fibre, 2.1 %
    (12000e-6, 200e-6, (1000e-6, 6000e-6)),  # the bound belongs to the upper row
    (11999e-6, 100e-6, (1000e-6, 3000e-6)),
    (6000e-6, 100e-6, (1000e-6, 3000e-6)),
    (5999e-6, 100e-6, (500e-6, 1500e-6)),  # an ultra-high-modulus fibre
])
def test_tables_1_and_2_by_the_typical_failure_strain(strain, preload, chord):
    assert preload_strain(strain) == preload
    assert chord_strains(strain) == chord


def test_tables_hold_the_standards_rows():
    assert [bound for bound, _ in PRELOAD_LIMITS] == [bound for bound, _ in CHORD_LIMITS] == [12000e-6, 6000e-6, 0.0]
    with pytest.raises(ValueError, match="typical strain at failure"):
        chord_strains(0.0)


def test_eqs_6_to_8_statistics():
    found = sample_statistics([10.0, 12.0, 14.0])  # mean 12; s = sqrt((4 + 0 + 4) / 2) = 2; CV = 100 x 2 / 12
    assert (found.n, found.mean, found.standard_deviation) == (3, 12.0, 2.0)
    assert found.cv_percent == pytest.approx(100 * 2 / 12, rel=1e-15)
    # Eq 7 as printed: sqrt((sum x^2 - n mean^2) / (n - 1)) = sqrt((440 - 432) / 2) = 2
    assert math.sqrt((sum(x * x for x in (10, 12, 14)) - 3 * 12**2) / 2) == found.standard_deviation
    with pytest.raises(ValueError, match="at least two values"):
        sample_statistics([4950e6])


def test_planning_loads_from_a_datasheet():
    found = planning_loads(MUL, RHO, 21000e-6, modulus=230e9, strength=4900e6)
    area = 0.8e-3 / 1800.0  # 4.444e-7 m^2
    assert found.area == pytest.approx(area, rel=1e-15)
    assert found.preload_force == pytest.approx(200e-6 * 230e9 * area, rel=1e-12)  # 20.44 N
    assert found.force_lower == pytest.approx(1000e-6 * 230e9 * area, rel=1e-12)  # 102.2 N
    assert found.force_upper == pytest.approx(6000e-6 * 230e9 * area, rel=1e-12)  # 613.3 N
    assert found.failure_force == pytest.approx(4900e6 * area, rel=1e-12)  # 2178 N
    bare = planning_loads(MUL, RHO, 21000e-6)
    assert (bare.preload_force, bare.force_lower, bare.force_upper, bare.failure_force) == (None, None, None, None)
    assert bare.chord_strains == (1000e-6, 6000e-6)


@pytest.mark.parametrize("call", [
    lambda: mass_per_unit_length(0.0, 1.0),
    lambda: mass_per_unit_length(1.0, float("nan")),
    lambda: tow_strength(-1.0, RHO, MUL),
    lambda: fibre_area(MUL, float("inf")),
    lambda: planning_loads(MUL, RHO, 0.02, modulus=0.0),
])
def test_invalid_input_is_refused_never_defaulted(call):
    with pytest.raises(ValueError):
        call()
