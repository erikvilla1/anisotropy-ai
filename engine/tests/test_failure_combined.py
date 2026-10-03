"""First-ply failure with fixed and variable loading, checked against the mechanical-only
functions, the failure criteria themselves and an independent bisection.

Strengths are Daniel & Ishai Table A.4 (AS4/3501-6); expansion coefficients and loads are
constructed test inputs. The course problem (Homework 5) is a validation case.
"""

import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from anisotropy_engine.cases import engine_results, validate_case_inputs
from anisotropy_engine.failure import (
    first_ply_failure, first_ply_failure_combined, max_stress_ratio, max_stress_ratio_combined, tsai_wu_ratio,
    tsai_wu_ratio_combined,
)
from anisotropy_engine.lamina import Lamina, Strengths, ThermalExpansion
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads
from anisotropy_engine.thermal import thermal_ply_surfaces, thermomechanical_response

STRENGTHS = Strengths(F1t=2280e6, F1c=1725e6, F2t=57e6, F2c=228e6, F6=76e6)
MATERIAL = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27, strengths=STRENGTHS,
                  thermal_expansion=ThermalExpansion(alpha1=-0.9e-6, alpha2=27e-6))
ZERO = Loads(Nx=0, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0)
STRESSES = [[300e6, 20e6, 10e6], [-400e6, -50e6, -30e6], [0, 40e6, 0], [100e6, -10e6, 60e6]]
ENGINE = Path(__file__).parents[1]


def stack(angles):
    return [Ply(material=MATERIAL, angle_deg=a, thickness_m=0.15e-3) for a in angles]


def tsai_wu_index(stress):
    s1, s2, s6 = stress
    st = STRENGTHS
    f12 = -0.5 * math.sqrt(1 / (st.F1t * st.F1c * st.F2t * st.F2c))
    return ((1 / st.F1t - 1 / st.F1c) * s1 + (1 / st.F2t - 1 / st.F2c) * s2 + s1 ** 2 / (st.F1t * st.F1c)
            + s2 ** 2 / (st.F2t * st.F2c) + s6 ** 2 / st.F6 ** 2 + 2 * f12 * s1 * s2)


@pytest.mark.parametrize("stress", STRESSES)
def test_with_nothing_fixed_the_ratios_equal_the_mechanical_ones(stress):
    assert max_stress_ratio_combined([0, 0, 0], stress, STRENGTHS) == max_stress_ratio(stress, STRENGTHS)
    assert tsai_wu_ratio_combined([0, 0, 0], stress, STRENGTHS, -0.5) == pytest.approx(
        tsai_wu_ratio(stress, STRENGTHS, -0.5), rel=1e-12)


@pytest.mark.parametrize("fixed", [[50e6, 30e6, 0], [-200e6, 25e6, -20e6]])
@pytest.mark.parametrize("variable", STRESSES)
def test_ratios_land_exactly_on_the_failure_envelope(fixed, variable):
    fixed, variable = np.array(fixed), np.array(variable)
    ratio = tsai_wu_ratio_combined(fixed, variable, STRENGTHS, -0.5)
    assert tsai_wu_index(fixed + ratio * variable) == pytest.approx(1.0, abs=1e-9)
    ratio, mode = max_stress_ratio_combined(fixed, variable, STRENGTHS)
    at_failure = fixed + ratio * variable
    limits = [STRENGTHS.F1t, STRENGTHS.F2t, STRENGTHS.F6], [STRENGTHS.F1c, STRENGTHS.F2c, STRENGTHS.F6]
    margins = [min(t - s, s + c) for s, t, c in zip(at_failure, *limits)]
    assert min(margins) == pytest.approx(0.0, abs=1e-3)  # one limit reached (Pa)
    assert max_stress_ratio_combined(fixed, 0.999 * ratio * variable, STRENGTHS)[0] > 1  # not yet at 99.9%


def test_fixed_stress_beyond_a_limit_fails_at_zero():
    assert max_stress_ratio_combined([0, 60e6, 0], [1e6, 0, 0], STRENGTHS) == (0.0, "transverse tension")
    assert tsai_wu_ratio_combined([0, 60e6, 0], [1e6, 0, 0], STRENGTHS, -0.5) == 0.0


def test_variable_stress_that_never_grows_gives_infinity():
    assert max_stress_ratio_combined([10e6, 0, 0], [0, 0, 0], STRENGTHS) == (math.inf, "none")


def test_laminate_with_nothing_fixed_matches_first_ply_failure():
    plies = stack([0, 45, -45, 90])
    loads = Loads(Nx=200e3, Ny=-50e3, Nxy=30e3, Mx=5.0, My=0, Mxy=-2.0)
    for criterion in ("max_stress", "tsai_wu"):
        old = first_ply_failure(plies, loads, criterion, -0.5)
        new = first_ply_failure_combined(plies, ZERO, loads, None, criterion, -0.5)
        assert new.strength_ratio == pytest.approx(old.strength_ratio, rel=1e-12)
        assert new.governing.ply_index == old.governing.ply_index
        np.testing.assert_allclose(new.failure_loads.as_vector(), old.failure_loads.as_vector(), rtol=1e-12)


def test_fixed_moment_and_cooling_match_an_independent_bisection():
    # Grow Nx and Ny = 0.5 Nx while Mx and a temperature change stay fixed; bisect on the full stress.
    plies = stack([45, -45, 90, 0, 0, 90, -45, 45])
    fixed = Loads(Nx=0, Ny=0, Nxy=0, Mx=-0.7, My=0, Mxy=0)
    variable = Loads(Nx=1000.0, Ny=500.0, Nxy=0, Mx=0, My=0, Mxy=0)
    result = first_ply_failure_combined(plies, fixed, variable, -150.0)

    def fails(r):
        loads = Loads(**{k: getattr(fixed, k) + r * getattr(variable, k) for k in ("Nx", "Ny", "Nxy", "Mx", "My", "Mxy")})
        eps0, kappa = thermomechanical_response(plies, loads, -150.0)
        return any(max_stress_ratio(s.stress_12, STRENGTHS)[0] <= 1 for s in thermal_ply_surfaces(plies, eps0, kappa, -150.0))

    low, high = 0.0, 1e4
    for _ in range(100):
        middle = (low + high) / 2
        low, high = (low, middle) if fails(middle) else (middle, high)
    assert result.strength_ratio == pytest.approx(high, rel=1e-9)
    np.testing.assert_allclose(result.failure_loads.as_vector(),
                               fixed.as_vector() + result.strength_ratio * variable.as_vector(), rtol=1e-12)


def test_superposition_of_fixed_and_variable_stresses_is_exact():
    plies = stack([0, 90, 45])
    fixed = Loads(Nx=0, Ny=1000, Nxy=0, Mx=0.3, My=0, Mxy=0)
    variable = Loads(Nx=5000, Ny=0, Nxy=-800, Mx=0, My=0, Mxy=0)
    result = first_ply_failure_combined(plies, fixed, variable, -100.0, "tsai_wu", -0.5)
    g = result.governing
    eps0, kappa = thermomechanical_response(plies, result.failure_loads, -100.0)
    face = [s for s in thermal_ply_surfaces(plies, eps0, kappa, -100.0) if s.ply_index == g.ply_index and s.z_m == g.z_m][0]
    np.testing.assert_allclose(face.stress_12, g.stress_12, rtol=1e-9, atol=1e-3)
    assert tsai_wu_index(face.stress_12) == pytest.approx(1.0, abs=1e-9)


def test_invalid_combined_searches_are_rejected():
    with pytest.raises(ValueError, match="nonzero variable load"):
        first_ply_failure_combined(stack([0]), ZERO, ZERO, None)
    no_strength = [Ply(material=MATERIAL.model_copy(update={"strengths": None}), angle_deg=0, thickness_m=1e-4)]
    with pytest.raises(ValueError, match="no strengths"):
        first_ply_failure_combined(no_strength, ZERO, Loads(Nx=1, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0), None)
    with pytest.raises(ValueError, match="f12_star"):
        first_ply_failure_combined(stack([0]), ZERO, Loads(Nx=1, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0), None, "tsai_wu")


# ------------------------------------------------------------------ case files

CASE = {"units": "SI", "material": {"E1": 147.0, "E2": 10.3, "G12": 7.0, "nu12": 0.27, "F1t": 2280.0,
                                    "F1c": 1725.0, "F2t": 57.0, "F2c": 228.0, "F6": 76.0},
        "laminate": {"layup": [0, 90, 90, 0], "ply_thickness": 0.15},
        "applied": {"loads": [1000.0, 0, 0, 0, 0, 0]}}


@pytest.mark.parametrize("failure, message", [
    ({"fixed": [0] * 6}, "missing fields \\['variable'\\]"),
    ({"fixed": [0] * 6, "variable": [0] * 6}, "at least one nonzero load"),
    ({"fixed": [0] * 5, "variable": [1, 0, 0, 0, 0, 0]}, "failure.fixed"),
])
def test_invalid_failure_tables_are_rejected(failure, message):
    with pytest.raises(ValueError, match=message):
        validate_case_inputs(dict(CASE, failure=failure))


def test_failure_table_needs_strengths():
    material = {k: v for k, v in CASE["material"].items() if not k.startswith("F")}
    with pytest.raises(ValueError, match="needs all five strengths"):
        validate_case_inputs(dict(CASE, material=material, failure={"fixed": [0] * 6, "variable": [1, 0, 0, 0, 0, 0]}))


def test_failure_table_results_report_loads_ply_and_location():
    results = engine_results(dict(CASE, failure={"fixed": [0, 0, 0, 0.5, 0, 0], "variable": [1, 0, 0, 0, 0, 0]}))
    ratio = results["fpf_ratio_max_stress"][0]
    np.testing.assert_allclose(results["fpf_forces_max_stress"][0], [ratio, 0, 0], rtol=1e-12)
    np.testing.assert_allclose(results["fpf_moments_max_stress"][0], [0.5, 0, 0], rtol=1e-12)
    assert results["fpf_ply_max_stress"][0] in (1.0, 2.0, 3.0, 4.0)
    assert abs(results["fpf_z_max_stress"][0]) <= 0.3  # mm, within the 0.6 mm laminate


def test_calculator_lists_fixed_and_variable_loads():
    run = subprocess.run([sys.executable, str(ENGINE / "examples/laminate_calculator.py"),
                          str(ENGINE / "validation/cases/se142-hw5-p1-thermal-bending-laminate.toml")],
                         cwd=ENGINE, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "First-ply failure search from [failure]" in run.stdout
    assert "R = 568.256, ply 3 (90 deg), transverse tension, bottom face at z = -0.015 in" in run.stdout
