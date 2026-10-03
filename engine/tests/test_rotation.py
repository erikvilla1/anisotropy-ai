import math

import numpy as np
import pytest

from anisotropy_engine.lamina import Lamina, reduced_stiffness
from anisotropy_engine.rotation import (
    strain_transformation,
    stress_transformation,
    transformed_reduced_stiffness,
)

CARBON = Lamina(E1=145e9, E2=10.5e9, G12=7e9, nu12=0.28)
Q = reduced_stiffness(CARBON)
ANGLES = [0, 30, 45, -37, 90]


def _expanded_q_bar(angle_deg):
    """Q_bar from the standard expanded m, n formulas, written independently of rotation.py."""
    m, n = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    q11, q22, q12, q66 = Q[0, 0], Q[1, 1], Q[0, 1], Q[2, 2]
    b11 = q11 * m**4 + 2 * (q12 + 2 * q66) * m**2 * n**2 + q22 * n**4
    b22 = q11 * n**4 + 2 * (q12 + 2 * q66) * m**2 * n**2 + q22 * m**4
    b12 = (q11 + q22 - 4 * q66) * m**2 * n**2 + q12 * (m**4 + n**4)
    b66 = (q11 + q22 - 2 * q12 - 2 * q66) * m**2 * n**2 + q66 * (m**4 + n**4)
    b16 = (q11 - q12 - 2 * q66) * m**3 * n + (q12 - q22 + 2 * q66) * m * n**3
    b26 = (q11 - q12 - 2 * q66) * m * n**3 + (q12 - q22 + 2 * q66) * m**3 * n
    return np.array([[b11, b12, b16], [b12, b22, b26], [b16, b26, b66]])


def test_zero_angle_changes_nothing():
    np.testing.assert_array_equal(stress_transformation(0), np.eye(3))
    np.testing.assert_array_equal(strain_transformation(0), np.eye(3))
    np.testing.assert_allclose(transformed_reduced_stiffness(CARBON, 0), Q)


def test_ninety_degrees_swaps_fiber_and_transverse_stiffness():
    q_bar = transformed_reduced_stiffness(CARBON, 90)
    assert q_bar[0, 0] == pytest.approx(Q[1, 1])
    assert q_bar[1, 1] == pytest.approx(Q[0, 0])
    # cos(90 deg) is 6e-17, not exactly 0, so the coupling terms are compared within 1 Pa.
    assert q_bar[0, 2] == pytest.approx(0, abs=1.0)
    assert q_bar[1, 2] == pytest.approx(0, abs=1.0)


def test_45_degree_ply_matches_hand_checkable_values():
    # GPa. Q_bar11 = Q_bar22 because the fibers sit halfway between x and y;
    # nonzero Q_bar16 means pulling along x also shears the ply.
    expected = np.array([
        [47.575356, 33.575356, 33.816987],
        [33.575356, 47.575356, 33.816987],
        [33.816987, 33.816987, 37.618570],
    ]) * 1e9
    np.testing.assert_allclose(transformed_reduced_stiffness(CARBON, 45), expected, rtol=1e-7)


@pytest.mark.parametrize("angle", ANGLES)
def test_matrix_form_matches_expanded_formulas(angle):
    np.testing.assert_allclose(
        transformed_reduced_stiffness(CARBON, angle), _expanded_q_bar(angle), rtol=1e-12, atol=1.0
    )


@pytest.mark.parametrize("angle", ANGLES)
def test_rotating_back_undoes_the_rotation(angle):
    np.testing.assert_allclose(stress_transformation(angle) @ stress_transformation(-angle), np.eye(3), atol=1e-12)
    np.testing.assert_allclose(strain_transformation(angle) @ strain_transformation(-angle), np.eye(3), atol=1e-12)


@pytest.mark.parametrize("angle", ANGLES)
def test_q_bar_is_symmetric(angle):
    q_bar = transformed_reduced_stiffness(CARBON, angle)
    np.testing.assert_allclose(q_bar, q_bar.T, rtol=1e-12, atol=1.0)


@pytest.mark.parametrize("angle", ANGLES)
def test_half_turn_gives_the_same_ply(angle):
    np.testing.assert_allclose(
        transformed_reduced_stiffness(CARBON, angle + 180),
        transformed_reduced_stiffness(CARBON, angle),
        rtol=1e-12,
        atol=1.0,
    )


def test_negative_angle_flips_only_the_shear_coupling_terms():
    plus = transformed_reduced_stiffness(CARBON, 45)
    minus = transformed_reduced_stiffness(CARBON, -45)
    signs = np.array([[1, 1, -1], [1, 1, -1], [-1, -1, 1]])
    np.testing.assert_allclose(minus, signs * plus, rtol=1e-12)


@pytest.mark.parametrize("angle", ANGLES)
def test_work_is_the_same_in_both_axis_systems(angle):
    # Catches a factor of 2 in the wrong place in T_sigma or T_eps.
    stress = np.array([120e6, -40e6, 17e6])
    strain = np.array([0.003, -0.001, 0.004])
    local_work = (stress_transformation(angle) @ stress) @ (strain_transformation(angle) @ strain)
    assert local_work == pytest.approx(stress @ strain)


@pytest.mark.parametrize("angle", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_angles_are_rejected(angle):
    with pytest.raises(ValueError):
        stress_transformation(angle)
    with pytest.raises(ValueError):
        strain_transformation(angle)
    with pytest.raises(ValueError):
        transformed_reduced_stiffness(CARBON, angle)
