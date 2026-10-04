"""Uniform temperature change: physical checks that do not depend on the ABD solve.

The elastic constants and expansion coefficients below are constructed test inputs, not
measured properties. Course Reader Problem 5.9 is checked separately as a validation case.
"""

import math

import numpy as np
import pytest
from pydantic import ValidationError

from anisotropy_engine.cases import engine_results
from anisotropy_engine.failure import first_ply_failure_combined
from anisotropy_engine.lamina import Lamina, Strengths, ThermalExpansion, reduced_stiffness
from anisotropy_engine.laminate import Ply, ply_interfaces
from anisotropy_engine.response import Loads, midplane_response, ply_surfaces
from anisotropy_engine.rotation import strain_transformation
from anisotropy_engine.thermal import (
    thermal_expansion_xy, thermal_ply_surfaces, thermal_resultants, thermomechanical_response,
)

ALPHA = ThermalExpansion(alpha1=-0.5e-6, alpha2=30e-6)
MATERIAL = Lamina(E1=140e9, E2=10e9, G12=7e9, nu12=0.3, thermal_expansion=ALPHA)
THICKNESS = 0.125e-3
DELTA_T = -100.0
NO_LOAD = Loads(Nx=0, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0)


def stack(angles, material=MATERIAL):
    return [Ply(material=material, angle_deg=a, thickness_m=THICKNESS) for a in angles]


def free_response(plies):
    eps0, kappa = thermomechanical_response(plies, NO_LOAD, DELTA_T)
    return eps0, kappa, thermal_ply_surfaces(plies, eps0, kappa, DELTA_T)


@pytest.mark.parametrize("angle", [0, 30, 45, 90, -60])
def test_expansion_rotates_like_engineering_strain(angle):
    m, n = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    a1, a2 = ALPHA.alpha1, ALPHA.alpha2
    expected = [a1 * m * m + a2 * n * n, a1 * n * n + a2 * m * m, 2 * (a1 - a2) * m * n]
    alpha_xy = thermal_expansion_xy(MATERIAL, angle)
    np.testing.assert_allclose(alpha_xy, expected, rtol=1e-12, atol=1e-20)
    # Rotating back into fiber axes recovers [alpha1, alpha2, 0].
    np.testing.assert_allclose(strain_transformation(angle) @ alpha_xy, [a1, a2, 0], rtol=1e-12, atol=1e-20)


@pytest.mark.parametrize("angle", [0, 30, 90])
def test_single_ply_expands_freely_without_stress(angle):
    eps0, kappa, surfaces = free_response(stack([angle]))
    np.testing.assert_allclose(eps0, thermal_expansion_xy(MATERIAL, angle) * DELTA_T, rtol=1e-12, atol=1e-18)
    np.testing.assert_allclose(kappa, 0, atol=1e-12)
    for surface in surfaces:
        np.testing.assert_allclose(surface.stress_xy, 0, atol=1e-3)  # Pa; stiffness times strain is ~1e8 Pa


def test_equal_expansion_in_every_direction_leaves_any_layup_stress_free():
    # With alpha1 = alpha2 every ply wants the same strain, so nothing resists it.
    uniform = MATERIAL.model_copy(update={"thermal_expansion": ThermalExpansion(alpha1=12e-6, alpha2=12e-6)})
    eps0, kappa, surfaces = free_response(stack([0, 35, -70, 90, 10], uniform))
    np.testing.assert_allclose(eps0, [12e-6 * DELTA_T, 12e-6 * DELTA_T, 0], rtol=1e-10, atol=1e-18)
    np.testing.assert_allclose(kappa, 0, atol=1e-10)
    for surface in surfaces:
        np.testing.assert_allclose(surface.stress_xy, 0, atol=1e-2)


def test_balanced_symmetric_cross_ply_matches_closed_form():
    # Equal 0 and 90 thickness: eps0_x = eps0_y = dT [(Q11+Q12) a1 + (Q12+Q22) a2] / (Q11 + 2 Q12 + Q22).
    q = reduced_stiffness(MATERIAL)
    q11, q12, q22 = q[0, 0], q[0, 1], q[1, 1]
    a1, a2 = ALPHA.alpha1, ALPHA.alpha2
    strain = DELTA_T * ((q11 + q12) * a1 + (q12 + q22) * a2) / (q11 + 2 * q12 + q22)
    eps0, kappa, surfaces = free_response(stack([0, 90, 90, 0]))
    np.testing.assert_allclose(eps0, [strain, strain, 0], rtol=1e-12, atol=1e-15)
    np.testing.assert_allclose(kappa, 0, atol=1e-10)
    _, M_T = thermal_resultants(stack([0, 90, 90, 0]), DELTA_T)
    np.testing.assert_allclose(M_T, 0, atol=1e-12)
    # In fiber axes every ply has mechanical strain [eps0 - a1 dT, eps0 - a2 dT, 0].
    expected_12 = q @ [strain - a1 * DELTA_T, strain - a2 * DELTA_T, 0]
    for surface in surfaces:
        np.testing.assert_allclose(surface.stress_12, expected_12, rtol=1e-10, atol=1e-3)


def test_unsymmetric_laminate_warps_but_carries_no_net_force_or_moment():
    plies = stack([0, 90])
    eps0, kappa, surfaces = free_response(plies)
    assert kappa[0] * kappa[1] < 0  # saddle shape after cooling, as for unsymmetric cross-plies
    # Integrate the linear face stresses through each ply, independently of the ABD solve.
    z = ply_interfaces(plies)
    force, moment = np.zeros(3), np.zeros(3)
    for k, (bottom, top) in enumerate(zip(surfaces[::2], surfaces[1::2])):
        a, b = z[k], z[k + 1]
        force += (bottom.stress_xy + top.stress_xy) / 2 * (b - a)
        moment += (b - a) / 6 * (bottom.stress_xy * (2 * a + b) + top.stress_xy * (a + 2 * b))
    np.testing.assert_allclose(force, 0, atol=1e-6)   # N/m, against ply forces of order 1e3 N/m
    np.testing.assert_allclose(moment, 0, atol=1e-9)  # N*m/m


def test_thermal_and_mechanical_responses_add():
    plies = stack([0, 45, -30])
    loads = Loads(Nx=5000, Ny=-1000, Nxy=300, Mx=0.5, My=-0.2, Mxy=0.1)
    combined = thermomechanical_response(plies, loads, DELTA_T)
    mechanical = midplane_response(plies, loads)
    thermal = thermomechanical_response(plies, NO_LOAD, DELTA_T)
    for c, m, t in zip(combined, mechanical, thermal):
        np.testing.assert_allclose(c, m + t, rtol=1e-10, atol=1e-15)


def test_zero_temperature_change_reproduces_mechanical_results():
    plies = stack([0, 45, -30])
    loads = Loads(Nx=5000, Ny=-1000, Nxy=300, Mx=0.5, My=-0.2, Mxy=0.1)
    eps0, kappa = thermomechanical_response(plies, loads, 0.0)
    expected_eps0, expected_kappa = midplane_response(plies, loads)
    np.testing.assert_allclose(eps0, expected_eps0, rtol=1e-12)
    np.testing.assert_allclose(kappa, expected_kappa, rtol=1e-12)
    for thermal, mechanical in zip(thermal_ply_surfaces(plies, eps0, kappa, 0.0), ply_surfaces(plies, eps0, kappa)):
        np.testing.assert_allclose(thermal.stress_12, mechanical.stress_12, rtol=1e-12, atol=1e-6)


def test_thermal_analysis_requires_expansion_coefficients():
    plies = stack([0, 90], MATERIAL.model_copy(update={"thermal_expansion": None}))
    with pytest.raises(ValueError, match="no thermal expansion"):
        thermal_resultants(plies, DELTA_T)
    with pytest.raises(ValueError, match="no thermal expansion"):
        thermomechanical_response(plies, NO_LOAD, DELTA_T)
    with pytest.raises(ValueError, match="no thermal expansion"):
        thermal_ply_surfaces(plies, np.zeros(3), np.zeros(3), DELTA_T)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "150", True, None])
def test_temperature_change_must_be_a_finite_number(bad):
    with pytest.raises(ValueError, match="delta_T"):
        thermal_resultants(stack([0]), bad)


@pytest.mark.parametrize("values", [
    {"alpha1": float("nan"), "alpha2": 1e-6},
    {"alpha1": 1e-6, "alpha2": float("inf")},
    {"alpha1": 1e-6, "alpha2": 2e-6, "alpha12": 0.0},
    {"alpha1": 1e-6},
])
def test_expansion_coefficients_must_be_complete_finite_and_named(values):
    with pytest.raises(ValidationError):
        ThermalExpansion(**values)


# ------------------------------------------------------------------ case files

CASE = {
    "units": "SI",
    "material": {"E1": 140.0, "E2": 10.0, "G12": 7.0, "nu12": 0.3, "alpha1": -0.5e-6, "alpha2": 30e-6},
    "laminate": {"layup": [0, 90], "ply_thickness": 0.125},
    "applied": {"loads": [0, 0, 0, 0, 0, 0], "delta_T": -100.0},
}


def case_with(**changes):
    case = {key: dict(value) if isinstance(value, dict) else value for key, value in CASE.items()}
    for path, value in changes.items():
        table, _, field = path.partition("__")
        if value is None:
            del case[table][field]
        else:
            case[table][field] = value
    return case


def test_case_results_match_direct_engine_calls():
    results = engine_results(case_with())
    eps0, kappa, _ = free_response(stack([0, 90]))
    np.testing.assert_allclose(results["strain_global"][0], eps0, rtol=1e-12)
    np.testing.assert_allclose(results["curvature"][0], kappa, rtol=1e-12)
    N_T, M_T = thermal_resultants(stack([0, 90]), DELTA_T)
    np.testing.assert_allclose(results["N_T"][0], N_T, rtol=1e-12)
    np.testing.assert_allclose(results["M_T"][0], M_T, rtol=1e-12)
    assert results["ply_stress_local"][0].shape == (2, 3)


def test_holding_the_free_thermal_shape_needs_no_mechanical_load():
    # Prescribe the free thermal deformation; the mechanical loads that produce it must be zero.
    eps0, kappa, _ = free_response(stack([0, 90]))
    case = case_with(applied__loads=None, applied__strains=[*eps0, *kappa])
    results = engine_results(case)
    np.testing.assert_allclose(results["moments"][0], 0, atol=1e-9)
    case = case_with(applied__loads=None, applied__forces_curvature=[0, 0, 0, *kappa])
    np.testing.assert_allclose(engine_results(case)["moments"][0], 0, atol=1e-9)


def test_flattening_moments_remove_the_thermal_warp():
    case = case_with(applied__loads=None, applied__forces_curvature=[0, 0, 0, 0, 0, 0])
    Mx, My, Mxy = engine_results(case)["moments"][0]
    assert abs(Mx) > 1e-3  # an unsymmetric cross-ply needs a real moment to stay flat
    # Applying those moments together with the temperature change must give zero curvature.
    _, kappa = thermomechanical_response(stack([0, 90]), Loads(Nx=0, Ny=0, Nxy=0, Mx=Mx, My=My, Mxy=Mxy), DELTA_T)
    np.testing.assert_allclose(kappa, 0, atol=1e-9)


def test_cases_without_delta_t_are_unchanged_and_report_no_thermal_results():
    results = engine_results(case_with(applied__delta_T=None))
    assert "N_T" not in results and "M_T" not in results
    np.testing.assert_allclose(results["strain_global"][0], 0, atol=1e-20)


@pytest.mark.parametrize("changes, message", [
    ({"material__alpha2": None}, "both alpha1 and alpha2"),
    ({"material__alpha1": None, "material__alpha2": None}, "needs alpha1 and alpha2"),
    ({"applied__delta_T": True}, "delta_T must be a finite number"),
    ({"applied__delta_T": "-150"}, "delta_T must be a finite number"),
    ({"applied__delta_T": float("nan")}, "delta_T must be a finite number"),
    ({"applied__loads": None}, "exactly one"),
])
def test_invalid_thermal_case_inputs_are_rejected(changes, message):
    with pytest.raises(ValueError, match=message):
        engine_results(case_with(**changes))


def test_failure_ratios_with_a_temperature_change_hold_the_residual_stress_fixed():
    # Daniel & Ishai Section 9.8: mechanical loads scale with R; the thermal stress does not.
    material = dict(CASE["material"], F1t=2280.0, F1c=1725.0, F2t=57.0, F2c=228.0, F6=76.0)
    case = case_with(applied__loads=[1000, 0, 0, 0, 0, 0])
    case["material"] = material
    with_cooling = engine_results(case)["fpf_ratio_max_stress"][0]
    strengths = Strengths(F1t=2280e6, F1c=1725e6, F2t=57e6, F2c=228e6, F6=76e6)
    plies = stack([0, 90], MATERIAL.model_copy(update={"strengths": strengths}))
    loads = Loads(Nx=1000, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0)
    expected = first_ply_failure_combined(plies, NO_LOAD, loads, DELTA_T).strength_ratio
    assert with_cooling == pytest.approx(expected, rel=1e-12)
    del case["applied"]["delta_T"]
    mechanical_only = engine_results(case)["fpf_ratio_max_stress"][0]
    assert with_cooling < mechanical_only  # curing stress uses up part of the transverse strength


def test_us_units_convert_expansion_and_temperature_change_consistently():
    # 1/degF = 1.8/K and 1 degF = 5/9 K, so alpha * delta_T is the same strain in both systems.
    si = case_with()
    us = case_with(material__E1=140 / 6.894757293168361, material__E2=10 / 6.894757293168361,
                   material__G12=7 / 6.894757293168361, material__alpha1=-0.5e-6 / 1.8, material__alpha2=30e-6 / 1.8,
                   applied__delta_T=-180.0)
    us["units"] = "US"
    us["laminate"] = {"layup": [0, 90], "ply_thickness": 0.125e-3 / 0.0254}
    np.testing.assert_allclose(engine_results(us)["strain_global"][0], engine_results(si)["strain_global"][0], rtol=1e-9)
