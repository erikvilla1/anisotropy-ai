"""Maximum strain and Tsai-Hill: against closed forms, against each other, and against bisection."""

import math
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.cases import disagreements, load_case, validate_case_inputs
from anisotropy_engine.failure import (
    first_ply_failure, first_ply_failure_combined, max_strain_ratio, max_strain_ratio_combined,
    max_stress_ratio, tsai_hill_index, tsai_hill_ratio, tsai_hill_ratio_combined,
)
from anisotropy_engine.lamina import Lamina, StrainLimits, Strengths, ThermalExpansion, reduced_compliance, strain_limits_from_strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads

CASES = Path(__file__).parents[1] / "validation" / "cases"
STRENGTHS = Strengths(F1t=2280e6, F1c=1725e6, F2t=57e6, F2c=228e6, F6=76e6)  # Daniel & Ishai Table A.4, AS4/3501-6
BARE = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27, strengths=STRENGTHS,
              thermal_expansion=ThermalExpansion(alpha1=-0.9e-6, alpha2=27e-6))
AS4 = BARE.model_copy(update={"strain_limits": strain_limits_from_strengths(BARE)})


def stack(angles, material=AS4, t=0.25e-3):
    return [Ply(material=material, angle_deg=a, thickness_m=t) for a in angles]


def test_strain_limits_from_strengths_are_strength_over_modulus():
    limits = AS4.strain_limits
    assert limits.eps1t == pytest.approx(2280e6 / 147e9)
    assert limits.eps1c == pytest.approx(1725e6 / 147e9)
    assert limits.eps2t == pytest.approx(57e6 / 10.3e9)
    assert limits.eps2c == pytest.approx(228e6 / 10.3e9)
    assert limits.gamma12 == pytest.approx(76e6 / 7e9)
    with pytest.raises(ValueError, match="need all five strengths"):
        strain_limits_from_strengths(Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27))


def test_uniaxial_fiber_stress_gives_the_same_ratio_by_stress_and_strain():
    stress = np.array([1000e6, 0, 0])
    strain = reduced_compliance(AS4) @ stress
    assert max_strain_ratio(strain, AS4.strain_limits)[0] == pytest.approx(2.28)
    assert max_stress_ratio(stress, STRENGTHS)[0] == pytest.approx(2.28)


def test_poisson_coupling_separates_maximum_strain_from_maximum_stress():
    # Analytical: eps1 = (s1 - nu12 s2)/E1, so the strain ratio is F1t/(s1 - nu12 s2) > F1t/s1.
    stress = np.array([1000e6, 20e6, 0])
    ratio, mode = max_strain_ratio(reduced_compliance(AS4) @ stress, AS4.strain_limits)
    assert ratio == pytest.approx(2280 / (1000 - 0.27 * 20))
    assert mode == "longitudinal tensile strain"
    assert max_stress_ratio(stress, STRENGTHS)[0] == pytest.approx(2.28)


def test_maximum_strain_combined_reduces_to_the_simple_form_and_handles_fixed_strain():
    limits = AS4.strain_limits
    v = np.array([0.004, 0.001, 0.002])
    assert max_strain_ratio_combined(np.zeros(3), v, limits) == max_strain_ratio(v, limits)
    fixed = np.array([0, -0.01, 0])  # transverse compressive strain held
    ratio, mode = max_strain_ratio_combined(fixed, np.array([0, -0.005, 0]), limits)
    assert ratio == pytest.approx((limits.eps2c - 0.01) / 0.005) and mode == "transverse compressive strain"
    assert max_strain_ratio_combined(np.array([0.02, 0, 0]), v, limits) == (0.0, "longitudinal tensile strain")


def test_tsai_hill_index_follows_the_textbook_sign_selection():
    s = np.array([1000e6, 20e6, 0])
    expected = (1000 / 2280) ** 2 - 1000 * 20 / 2280**2 + (20 / 57) ** 2
    assert tsai_hill_index(s, STRENGTHS) == pytest.approx(expected)
    assert tsai_hill_ratio(s, STRENGTHS) == pytest.approx(1 / math.sqrt(expected))
    c = np.array([-500e6, -30e6, 10e6])
    expected = (500 / 1725) ** 2 - 500 * 30 / 1725**2 + (30 / 228) ** 2 + (10 / 76) ** 2
    assert tsai_hill_index(c, STRENGTHS) == pytest.approx(expected)
    assert tsai_hill_ratio(np.zeros(3), STRENGTHS) == math.inf


def test_tsai_hill_shear_strength_at_45_degrees_is_the_textbook_sample_problem():
    # Daniel & Ishai Sample Problem 6.1: s1 = tau, s2 = -tau, tau12 = 0 at 45 degrees, so
    # 1/F^2 = 2/F1t^2 + 1/F2c^2, which is close to F2c for a high-fiber-strength composite.
    expected = 1 / math.sqrt(2 / 2280**2 + 1 / 228**2)
    plies = stack([45])
    result = first_ply_failure(plies, Loads(Nx=0, Ny=0, Nxy=0.25e-3 * 1e6, Mx=0, My=0, Mxy=0), "tsai_hill")
    assert result.strength_ratio == pytest.approx(expected, rel=1e-9)
    assert expected == pytest.approx(225.7, abs=0.1)


def _bisect_tsai_hill(fixed, variable, strengths, upper=50.0):
    """Independent root of index(fixed + R variable) = 1 by bisection on the first crossing."""
    f = lambda r: tsai_hill_index(fixed + r * variable, strengths) - 1
    lo, hi = 0.0, upper
    assert f(lo) < 0 < f(hi)
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@pytest.mark.parametrize("fixed, variable", [
    ([0, 0, 0], [300e6, 20e6, 10e6]),
    ([-200e6, -40e6, 0], [500e6, 30e6, 20e6]),   # sigma1 and sigma2 both change sign along the path
    ([100e6, 30e6, -20e6], [-400e6, -10e6, 5e6]),
    ([0, -100e6, 0], [0, 60e6, 0]),               # transverse stress crosses zero
])
def test_tsai_hill_combined_matches_bisection_and_the_simple_form(fixed, variable):
    fixed, variable = np.array(fixed, dtype=float), np.array(variable, dtype=float)
    r = tsai_hill_ratio_combined(fixed, variable, STRENGTHS)
    assert r == pytest.approx(_bisect_tsai_hill(fixed, variable, STRENGTHS), rel=1e-9)
    assert tsai_hill_index(fixed + r * variable, STRENGTHS) == pytest.approx(1.0, rel=1e-9)
    if not np.any(fixed):
        assert r == pytest.approx(tsai_hill_ratio(variable, STRENGTHS))


def test_tsai_hill_combined_returns_zero_when_the_fixed_stress_already_fails():
    assert tsai_hill_ratio_combined(np.array([2300e6, 0, 0]), np.array([1e6, 0, 0]), STRENGTHS) == 0.0


def test_first_ply_failure_dispatches_every_criterion_and_names_missing_inputs():
    plies = stack(QUASI := [0, 45, -45, 90, 90, -45, 45, 0])
    loads = Loads(Nx=100e3, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0)
    ratios = {c: first_ply_failure(plies, loads, c, f12_star=-0.5).strength_ratio for c in ("max_stress", "max_strain", "tsai_hill", "tsai_wu")}
    assert all(r > 0 for r in ratios.values()) and len(set(ratios.values())) == 4
    assert first_ply_failure(plies, loads, "max_strain").governing.mode.endswith("strain")
    with pytest.raises(ValueError, match="no strain limits"):
        first_ply_failure(stack(QUASI, material=BARE), loads, "max_strain")
    with pytest.raises(ValueError, match="Unknown criterion"):
        first_ply_failure(plies, loads, "hashin")
    # Combined with a temperature change: the mechanical strain excludes the free thermal strain.
    fixed = Loads(Nx=0, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0)
    with_dT = first_ply_failure_combined(plies, fixed, loads, -100.0, "max_strain")
    without = first_ply_failure_combined(plies, fixed, loads, None, "max_strain")
    assert with_dT.strength_ratio != pytest.approx(without.strength_ratio)
    assert without.strength_ratio == pytest.approx(first_ply_failure(plies, loads, "max_strain").strength_ratio)


def test_cases_accept_explicit_limits_or_the_stated_choice_but_not_half_sets():
    case = load_case(CASES / "constructed-max-strain-biaxial-lamina.toml")
    assert not disagreements(case)
    explicit = {**case, "material": {**{k: v for k, v in case["material"].items() if k != "strain_limits"},
                                      "eps1t": 0.0155, "eps1c": 0.0117, "eps2t": 0.0055, "eps2c": 0.022, "gamma12": 0.011}}
    validate_case_inputs(explicit)
    for bad, message in [
        ({**explicit, "material": {**explicit["material"], "gamma12": None}}, "positive magnitudes"),
        ({**explicit, "material": {**explicit["material"], "strain_limits": "from-strengths"}}, "not both"),
        ({**case, "material": {**case["material"], "strain_limits": "from-moduli"}}, "must be"),
        ({**case, "material": {k: v for k, v in case["material"].items() if not k.startswith("F")}}, "needs all five strengths"),
    ]:
        with pytest.raises(ValueError, match=message):
            validate_case_inputs(bad)
    half = {**explicit, "material": {k: v for k, v in explicit["material"].items() if k != "gamma12"}}
    with pytest.raises(ValueError, match="all five strain limits"):
        validate_case_inputs(half)
