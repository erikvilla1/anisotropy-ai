"""The bilinear quadrilateral: shape functions, strain-displacement matrix, element stiffness (fea/docs/theory.md, Section 2)."""

import numpy as np
import pytest

from anisotropy_fea.membrane import GAUSS_POINTS, NATURAL, element_stiffness, jacobian, shape_derivatives, shape_functions, strain_displacement
from anisotropy_fea.mesh import KernelError

UNIT_SQUARE = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
SKEWED = np.array([[0.0, 0.0], [2.0, 0.3], [2.4, 1.7], [-0.2, 1.1]])
# an isotropic-like membrane stiffness, N/m, just to have a positive definite A
A_ISO = 1e6 * np.array([[3.0, 1.0, 0.0], [1.0, 3.0, 0.0], [0.0, 0.0, 1.0]])


@pytest.mark.parametrize("i", range(4))
def test_each_shape_function_is_one_at_its_node_and_zero_at_the_others(i):
    xi, eta = NATURAL[i]
    assert shape_functions(xi, eta) == pytest.approx(np.eye(4)[i])


@pytest.mark.parametrize("point", [(0.0, 0.0), (0.3, -0.7), (-0.9, 0.2), (1.0, 1.0)])
def test_partition_of_unity_and_zero_sum_derivatives(point):
    assert shape_functions(*point).sum() == pytest.approx(1.0)
    assert shape_derivatives(*point).sum(axis=1) == pytest.approx([0.0, 0.0])


def test_jacobian_and_strain_displacement_on_the_unit_square_match_hand_values():
    assert jacobian(UNIT_SQUARE, 0.0, 0.0) == pytest.approx(0.5 * np.eye(2))
    B, det = strain_displacement(UNIT_SQUARE, 0.0, 0.0)
    assert det == pytest.approx(0.25)
    assert B[0] == pytest.approx([-0.5, 0, 0.5, 0, 0.5, 0, -0.5, 0])
    assert B[1] == pytest.approx([0, -0.5, 0, -0.5, 0, 0.5, 0, 0.5])
    assert B[2] == pytest.approx([-0.5, -0.5, -0.5, 0.5, 0.5, 0.5, 0.5, -0.5])


def test_a_uniform_strain_field_is_recovered_exactly_on_a_skewed_element():
    eps = np.array([0.003, -0.001, 0.002])
    # u = eps_x x + gamma y, v = eps_y y: a displacement field with exactly this engineering strain
    u_e = np.column_stack([eps[0] * SKEWED[:, 0] + eps[2] * SKEWED[:, 1], eps[1] * SKEWED[:, 1]]).ravel()
    for xi, eta in GAUSS_POINTS:
        B, det = strain_displacement(SKEWED, xi, eta)
        assert det > 0
        assert B @ u_e == pytest.approx(eps, abs=1e-15)


def test_element_stiffness_is_symmetric_with_exactly_three_rigid_modes():
    k = element_stiffness(SKEWED, A_ISO)
    assert k == pytest.approx(k.T)
    eigenvalues = np.sort(np.linalg.eigvalsh(k))
    assert np.all(np.abs(eigenvalues[:3]) < 1e-9 * eigenvalues[-1])
    assert eigenvalues[3] > 1e-6 * eigenvalues[-1]
    translation_x = np.tile([1.0, 0.0], 4)
    rotation = np.column_stack([-SKEWED[:, 1], SKEWED[:, 0]]).ravel()
    assert k @ translation_x == pytest.approx(np.zeros(8), abs=1e-9 * eigenvalues[-1])
    assert k @ rotation == pytest.approx(np.zeros(8), abs=1e-9 * eigenvalues[-1])


def test_stiffness_scales_linearly_with_the_laminate_stiffness():
    assert element_stiffness(UNIT_SQUARE, 2.0 * A_ISO) == pytest.approx(2.0 * element_stiffness(UNIT_SQUARE, A_ISO))


def test_uniform_strain_gives_the_consistent_nodal_forces_of_its_tractions():
    # Unit square, eps = (0, eps_y, 0): N_y = A22 eps_y acts on the top edge (+) and bottom edge (-), half to each node.
    eps_y = 0.01
    u_e = np.column_stack([-A_ISO[0, 1] / A_ISO[0, 0] * eps_y * UNIT_SQUARE[:, 0] * 0, eps_y * UNIT_SQUARE[:, 1]]).ravel()
    N = A_ISO @ np.array([0.0, eps_y, 0.0])
    f = element_stiffness(UNIT_SQUARE, A_ISO) @ u_e
    # vertical forces: nodes 3, 4 (top) get +N_y/2 each, nodes 1, 2 (bottom) get -N_y/2 each
    assert f[1::2] == pytest.approx([-N[1] / 2, -N[1] / 2, N[1] / 2, N[1] / 2])
    # horizontal forces: N_x acts on the right edge (+, nodes 2, 3) and left edge (-, nodes 1, 4)
    assert f[0::2] == pytest.approx([-N[0] / 2, N[0] / 2, N[0] / 2, -N[0] / 2])


def test_clockwise_and_bow_tie_elements_are_refused():
    with pytest.raises(KernelError, match="clockwise or it is degenerate"):
        element_stiffness(UNIT_SQUARE[::-1], A_ISO)
    bow_tie = np.array([[0.0, 0.0], [1.0, 1.0], [1.0, 0.0], [0.0, 1.0]])
    with pytest.raises(KernelError, match="det J"):
        element_stiffness(bow_tie, A_ISO)
