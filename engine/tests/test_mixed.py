"""Mixed load/deformation conditions, checked against the other solvers and closed forms.

Elastic constants and expansion coefficients are constructed test inputs; course problems
are checked separately as validation cases.
"""

from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from anisotropy_engine.cases import engine_results, load_case, validate_case_inputs
from anisotropy_engine.lamina import Lamina, ThermalExpansion
from anisotropy_engine.laminate import Ply
from anisotropy_engine.mixed import mixed_response
from anisotropy_engine.response import Loads, abd_matrix, midplane_response, prescribed_curvature_response
from anisotropy_engine.rotation import transformed_compliance
from anisotropy_engine.thermal import thermal_resultants, thermomechanical_response

MATERIAL = Lamina(E1=140e9, E2=10e9, G12=7e9, nu12=0.3,
                  thermal_expansion=ThermalExpansion(alpha1=-1e-6, alpha2=26e-6))
NO_MOMENTS = {"Mx": 0.0, "My": 0.0, "Mxy": 0.0}
ENGINE = Path(__file__).parents[1]


def stack(angles, thickness=0.127e-3):
    return [Ply(material=MATERIAL, angle_deg=a, thickness_m=thickness) for a in angles]


def test_all_loads_known_matches_the_forward_solve():
    plies = stack([0, 45, -30])
    loads = dict(Nx=5000.0, Ny=-1000.0, Nxy=300.0, Mx=0.5, My=-0.2, Mxy=0.1)
    result = mixed_response(plies, loads, None)
    eps0, kappa = midplane_response(plies, Loads(**loads))
    np.testing.assert_allclose(result.midplane_strain, eps0, rtol=1e-12)
    np.testing.assert_allclose(result.curvature, kappa, rtol=1e-12)


def test_all_deformations_known_gives_the_loads_directly():
    plies = stack([0, 45, -30])
    deformation = np.array([1e-3, -2e-4, 5e-4, 0.3, -0.1, 0.2])
    known = dict(zip(("eps_x", "eps_y", "gamma_xy", "kappa_x", "kappa_y", "kappa_xy"), deformation))
    result = mixed_response(plies, known, None)
    np.testing.assert_allclose(result.loads.as_vector(), abd_matrix(plies) @ deformation, rtol=1e-12)


def test_known_forces_and_curvature_match_the_prescribed_curvature_solver():
    plies = stack([0, 0, 90, 90])
    known = dict(Nx=5000.0, Ny=0.0, Nxy=0.0, kappa_x=0.0, kappa_y=0.0, kappa_xy=0.0)
    result = mixed_response(plies, known, None)
    reference = prescribed_curvature_response(plies, [5000, 0, 0], [0, 0, 0])
    np.testing.assert_allclose(result.loads.as_vector()[3:], reference.moments, rtol=1e-12)
    np.testing.assert_allclose(result.midplane_strain, reference.midplane_strain, rtol=1e-12)


def test_lamina_kept_rectangular_matches_the_compliance_closed_form():
    # gamma_xy = S16 sx + S26 sy + S66 txy = 0, so txy = -(S16 sx + S26 sy) / S66.
    s = transformed_compliance(MATERIAL, 45)
    sx, sy = 10e6, -20e6
    expected = -(s[2, 0] * sx + s[2, 1] * sy) / s[2, 2]
    result = mixed_response(stack([45]), dict(sigma_x=sx, sigma_y=sy, gamma_xy=0.0, **NO_MOMENTS), None)
    h = 0.127e-3
    assert result.loads.Nxy / h == pytest.approx(expected, rel=1e-10)
    np.testing.assert_allclose(result.midplane_strain[2], 0, atol=1e-15)


def test_lamina_between_rigid_walls_matches_the_compliance_closed_form():
    # eps_x imposed, eps_y = 0 and tau_xy = 0: sigma_x = eps_x / (S11 - S12^2 / S22).
    s = transformed_compliance(MATERIAL, 30)
    expected = -0.01 / (s[0, 0] - s[0, 1] ** 2 / s[1, 1])
    result = mixed_response(stack([30]), dict(eps_x=-0.01, eps_y=0.0, tau_xy=0.0, **NO_MOMENTS), None)
    assert result.loads.Nx / 0.127e-3 == pytest.approx(expected, rel=1e-10)


def test_average_stress_and_force_per_width_are_the_same_condition():
    plies = stack([0, 90, 45])
    h = 3 * 0.127e-3
    by_stress = mixed_response(plies, dict(sigma_x=50e6, Ny=0.0, gamma_xy=0.0, **NO_MOMENTS), None)
    by_force = mixed_response(plies, dict(Nx=50e6 * h, Ny=0.0, gamma_xy=0.0, **NO_MOMENTS), None)
    np.testing.assert_allclose(by_stress.midplane_strain, by_force.midplane_strain, rtol=1e-12)


def test_holding_the_free_thermal_shape_needs_no_mechanical_load():
    plies = stack([0, 90])
    eps0, kappa = thermomechanical_response(plies, Loads(Nx=0, Ny=0, Nxy=0, Mx=0, My=0, Mxy=0), -150)
    known = dict(zip(("eps_x", "eps_y", "gamma_xy", "kappa_x", "kappa_y", "kappa_xy"), [*eps0, *kappa]))
    result = mixed_response(plies, known, -150)
    np.testing.assert_allclose(result.loads.as_vector(), 0, atol=1e-9)


def test_partially_held_cured_laminate_satisfies_every_known_quantity():
    plies = stack([0, 90])
    known = dict(Nx=0.0, Ny=0.0, Nxy=0.0, Mx=0.0, kappa_y=0.0, kappa_xy=0.0)
    result = mixed_response(plies, known, -150)
    # Total resultants K d must equal mechanical plus thermal in every row.
    total = abd_matrix(plies) @ np.concatenate([result.midplane_strain, result.curvature])
    thermal = np.concatenate(thermal_resultants(plies, -150))
    np.testing.assert_allclose(total, result.loads.as_vector() + thermal, rtol=1e-10, atol=1e-9)
    np.testing.assert_allclose(result.loads.as_vector()[:4], 0, atol=1e-9)
    np.testing.assert_allclose(result.curvature[1:], 0, atol=0)
    assert result.curvature[0] != 0 and result.verification.passed


@pytest.mark.parametrize("known, message", [
    (dict(Nx=0.0, eps_x=0.0, Ny=0.0, Nxy=0.0, **NO_MOMENTS), "exactly one of \\('Nx', 'sigma_x', 'eps_x'\\)"),
    (dict(Ny=0.0, Nxy=0.0, **NO_MOMENTS), "exactly one of \\('Nx', 'sigma_x', 'eps_x'\\); got none"),
    (dict(Nx=0.0, Ny=0.0, Nxy=0.0, Mx=0.0, My=0.0, kappa=0.0), "Unknown quantities \\['kappa'\\]"),
    (dict(Nx=float("nan"), Ny=0.0, Nxy=0.0, **NO_MOMENTS), "known values must contain only finite numbers"),
])
def test_invalid_mixed_conditions_are_rejected(known, message):
    with pytest.raises(ValueError, match=message):
        mixed_response(stack([0]), known, None)


def test_failed_forward_verification_rejects_the_result(monkeypatch):
    monkeypatch.setattr("anisotropy_engine.response.midplane_response",
                        lambda *_: (np.array([1.0, 1.0, 1.0]), np.zeros(3)))
    with pytest.raises(ValueError, match="verification"):
        mixed_response(stack([0, 90]), dict(Nx=5000.0, Ny=0.0, Nxy=0.0, kappa_x=0.0, kappa_y=0.0, kappa_xy=0.0), None)


# ------------------------------------------------------------------ case files

def mixed_case(**mixed):
    return {"units": "SI", "material": {"E1": 140.0, "E2": 10.0, "G12": 7.0, "nu12": 0.3},
            "laminate": {"layup": [30], "ply_thickness": 1.0}, "applied": {"mixed": mixed}}


@pytest.mark.parametrize("mixed, message", [
    (dict(eps_x=-0.01, eps_y=0.0, tau_xy=0.0, Mx=0.0, My=0.0), "exactly one of \\('Mxy', 'kappa_xy'\\)"),
    (dict(eps_x=-0.01, eps_y=0.0, tau_xy=0.0, Mx=0.0, My=0.0, Mxy=0.0, Nz=1.0), "unknown fields \\['Nz'\\]"),
    (dict(eps_x="-0.01", eps_y=0.0, tau_xy=0.0, Mx=0.0, My=0.0, Mxy=0.0), "\\['eps_x'\\] must be finite numbers"),
])
def test_invalid_mixed_case_inputs_are_rejected(mixed, message):
    with pytest.raises(ValueError, match=message):
        validate_case_inputs(mixed_case(**mixed))


def test_named_results_follow_the_case_units():
    results = engine_results(mixed_case(eps_x=-0.01, eps_y=0.0, tau_xy=0.0, Mx=0.0, My=0.0, Mxy=0.0))
    assert results["eps_x"][0] == pytest.approx(-0.01)
    assert results["sigma_x"][0] == pytest.approx(results["Nx"][0] / 1.0e-3 / 1e6)  # MPa from N/m over 1 mm
    assert results["eps_y"][0] == 0.0


def test_calculator_prints_the_given_quantities():
    run = subprocess.run([sys.executable, str(ENGINE / "examples/laminate_calculator.py"),
                          str(ENGINE / "validation/cases/se142-hw4-p2-cr-5-13-unsymmetric-cure.toml")],
                         cwd=ENGINE, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "Mixed conditions, in the case's units: given Nx = 0, Ny = 0, Nxy = 0, Mx = 0, kappa_y = 0, kappa_xy = 0." in run.stdout
    assert run.stdout.rstrip().endswith("values agree with the answer key.")
