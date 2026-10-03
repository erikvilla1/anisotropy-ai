"""Analytical and equilibrium checks for known forces and prescribed curvature.

The elastic constants and dimensions below are constructed test inputs, not a
measured material or a course problem. nu12=0 makes independent checks diagonal.
"""

import numpy as np
import pytest

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import prescribed_curvature_response, ply_surfaces


MATERIAL = Lamina(E1=120e9, E2=30e9, G12=6e9, nu12=0)
THICKNESS = 0.2e-3


def stack(angles, thickness=THICKNESS):
    return [Ply(material=MATERIAL, angle_deg=a, thickness_m=thickness) for a in angles]


def test_flat_cross_ply_matches_independent_diagonal_solution():
    # A11=A22=(E1+E2)t; A66=2 G12 t; B11=-B22=(E2-E1)t^2/2.
    result = prescribed_curvature_response(stack([0, 90]), [6000, -3000, 1200], [0, 0, 0])
    np.testing.assert_allclose(result.midplane_strain, [2e-4, -1e-4, 5e-4], atol=1e-15)
    np.testing.assert_allclose(result.moments, [-0.36, -0.18, 0], atol=1e-14)
    assert result.verification.passed
    np.testing.assert_allclose(result.verification.recovered_curvature, 0, atol=1e-12)


def test_single_ply_nonzero_curvature_matches_beam_stiffness():
    # B=0 and D=diag(E1,E2,G12)*h^3/12 independently of the force solve.
    result = prescribed_curvature_response(stack([0]), [6000, -3000, 1200], [0.2, -0.1, 0.3])
    np.testing.assert_allclose(result.midplane_strain, [0.00025, -0.0005, 0.001], atol=1e-15)
    np.testing.assert_allclose(result.moments, [0.016, -0.002, 0.0012], atol=1e-15)
    np.testing.assert_allclose(result.verification.recovered_curvature, [0.2, -0.1, 0.3], atol=1e-12)


def test_symmetric_stack_needs_no_flattening_moments():
    result = prescribed_curvature_response(stack([0, 90, 90, 0]), [6000, -3000, 1200], [0, 0, 0])
    np.testing.assert_allclose(result.moments, 0, atol=1e-14)


def test_reversing_stack_reverses_flattening_moments_only():
    first = prescribed_curvature_response(stack([0, 35, -20]), [6000, -3000, 1200], [0, 0, 0])
    flipped = prescribed_curvature_response(stack([-20, 35, 0]), [6000, -3000, 1200], [0, 0, 0])
    np.testing.assert_allclose(flipped.midplane_strain, first.midplane_strain, atol=1e-15)
    np.testing.assert_allclose(flipped.moments, -first.moments, atol=1e-14)


def test_off_axis_unequal_plies_preserve_force_and_moment_equilibrium():
    # Integrate face stresses through thickness, separately from the ABD solve.
    plies = [Ply(material=MATERIAL, angle_deg=a, thickness_m=t)
             for a, t in [(15, 0.2e-3), (-35, 0.3e-3), (75, 0.1e-3)]]
    forces, curvature = np.array([-6000, 3000, 1200]), np.array([0.2, -0.1, 0.3])
    result = prescribed_curvature_response(plies, forces, curvature)
    surfaces = ply_surfaces(plies, result.midplane_strain, curvature)
    integrated_force, integrated_moment = np.zeros(3), np.zeros(3)
    for bottom, top in zip(surfaces[::2], surfaces[1::2]):
        zb, zt = bottom.z_m, top.z_m
        integrated_force += (top.stress_xy + bottom.stress_xy) * (zt - zb) / 2
        integrated_moment += (zt - zb) / 6 * (
            bottom.stress_xy * (2 * zb + zt) + top.stress_xy * (zb + 2 * zt))
    np.testing.assert_allclose(integrated_force, forces, rtol=1e-12, atol=1e-9)
    np.testing.assert_allclose(integrated_moment, result.moments, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(result.verification.recovered_curvature, curvature, atol=1e-12)


def test_explicit_zero_problem_returns_zero():
    result = prescribed_curvature_response(stack([0, 90]), [0, 0, 0], [0, 0, 0])
    np.testing.assert_array_equal(result.midplane_strain, [0, 0, 0])
    np.testing.assert_array_equal(result.moments, [0, 0, 0])
    assert result.verification.passed


@pytest.mark.parametrize("bad", [[1, 2], [1, 2, 3, 4], [[1, 2, 3]], [float("nan"), 0, 0], [0, float("inf"), 0]])
@pytest.mark.parametrize("field", ["forces", "curvature"])
def test_incomplete_or_nonfinite_vectors_are_rejected(bad, field):
    args = {"forces": [0, 0, 0], "curvature": [0, 0, 0], field: bad}
    with pytest.raises(ValueError, match=field):
        prescribed_curvature_response(stack([0]), **args)


def test_empty_stack_is_rejected():
    with pytest.raises(ValueError, match="at least one ply"):
        prescribed_curvature_response([], [0, 0, 0], [0, 0, 0])


@pytest.mark.parametrize("thickness", [1e-200, 1e200])
def test_extreme_geometry_fails_instead_of_returning_unchecked_numbers(thickness):
    with pytest.raises((ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError)):
        prescribed_curvature_response(stack([0], thickness), [6000, 0, 0], [0, 0, 0])


@pytest.mark.parametrize("bad_result", [([1, 1, 1], [0, 0, 0]), ([0, 0, 0], [1, 1, 1]), ([float("nan"), 0, 0], [0, 0, 0])])
def test_forward_verification_failure_rejects_the_result(monkeypatch, bad_result):
    # Simulate a regression in the forward solve: the verification gate must stop it.
    monkeypatch.setattr("anisotropy_engine.response.midplane_response", lambda *_: tuple(np.array(v) for v in bad_result))
    with pytest.raises(ValueError, match="verification"):
        prescribed_curvature_response(stack([0, 90]), [6000, -3000, 1200], [0, 0, 0])
