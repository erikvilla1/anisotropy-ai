"""The MITC4 flat shell element on its own: strain-displacement rows, rigid modes, pure bending, pressure loads (fea/docs/theory.md, Section 8)."""

import numpy as np
import pytest

from anisotropy_fea.mesh import KernelError
from anisotropy_fea.shell import (DOFS, bending_rows, covariant_shear_rows, element_stiffness_shell, membrane_rows, physical_derivatives,
                                  pressure_loads, shear_rows)

E, NU, H = 70e9, 0.3, 1e-3
G = E / (2.0 * (1.0 + NU))
Q = E / (1.0 - NU**2) * np.array([[1.0, NU, 0.0], [NU, 1.0, 0.0], [0.0, 0.0, (1.0 - NU) / 2.0]])
A, B, D = Q * H, np.zeros((3, 3)), Q * H**3 / 12.0
HS = 5.0 / 6.0 * G * H * np.eye(2)
RECTANGLE = np.array([[0.0, 0.0], [0.1, 0.0], [0.1, 0.05], [0.0, 0.05]])
SKEWED = np.array([[0.0, 0.0], [0.1, 0.01], [0.12, 0.06], [-0.01, 0.05]])
UNIT = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])


def nodal_field(xy, u=None, v=None, w=None, theta_x=None, theta_y=None):
    """A nodal dof vector from functions of (x, y); a missing function means zero."""
    vector = np.zeros(4 * DOFS)
    for i, (x, y) in enumerate(xy):
        for d, f in enumerate((u, v, w, theta_x, theta_y)):
            vector[DOFS * i + d] = f(x, y) if f is not None else 0.0
    return vector


def test_strain_rows_on_the_unit_square_match_hand_values():
    dN, det = physical_derivatives(UNIT, 0.0, 0.0)
    assert det == pytest.approx(0.25)
    assert dN[0] == pytest.approx([-0.5, 0.5, 0.5, -0.5]) and dN[1] == pytest.approx([-0.5, -0.5, 0.5, 0.5])
    Bm, Bb = membrane_rows(dN), bending_rows(dN)
    assert Bm.shape == Bb.shape == (3, 20)
    assert Bm[0, 0::5] == pytest.approx(dN[0]) and Bm[1, 1::5] == pytest.approx(dN[1])  # eps_x from u, eps_y from v
    assert Bb[0, 4::5] == pytest.approx(dN[0])  # kappa_x = theta_y,x
    assert Bb[1, 3::5] == pytest.approx(-dN[1])  # kappa_y = -theta_x,y
    assert Bb[2, 4::5] == pytest.approx(dN[1]) and Bb[2, 3::5] == pytest.approx(-dN[0])  # kappa_xy = theta_y,y - theta_x,x
    # the covariant shear rows at the centre: gamma_xi = w,xi + x,xi theta_y - y,xi theta_x with x,xi = 1/2 and y,xi = 0 on the unit square
    rows = covariant_shear_rows(UNIT, 0.0, 0.0)
    assert rows[0, 4::5] == pytest.approx(0.5 * 0.25 * np.ones(4)) and rows[0, 3::5] == pytest.approx(np.zeros(4))
    assert rows[1, 3::5] == pytest.approx(-0.5 * 0.25 * np.ones(4)) and rows[1, 4::5] == pytest.approx(np.zeros(4))


@pytest.mark.parametrize("xy", [RECTANGLE, SKEWED], ids=["rectangle", "skewed"])
def test_stiffness_is_symmetric_with_exactly_six_rigid_modes(xy):
    k = element_stiffness_shell(xy, A, B, D, HS)
    assert np.allclose(k, k.T)
    eigenvalues = np.linalg.eigvalsh(k)
    assert int(np.sum(np.abs(eigenvalues) < 1e-9 * eigenvalues.max())) == 6  # three translations, three rotations; no spurious mode


@pytest.mark.parametrize("xy", [RECTANGLE, SKEWED], ids=["rectangle", "skewed"])
def test_rigid_motions_give_no_strain_and_no_force(xy):
    k = element_stiffness_shell(xy, A, B, D, HS)
    alpha = 0.01
    modes = {
        "translation w": nodal_field(xy, w=lambda x, y: alpha),
        "rotation about x": nodal_field(xy, w=lambda x, y: alpha * y, theta_x=lambda x, y: alpha),
        "rotation about y": nodal_field(xy, w=lambda x, y: -alpha * x, theta_y=lambda x, y: alpha),
        "in-plane rotation": nodal_field(xy, u=lambda x, y: -alpha * y, v=lambda x, y: alpha * x),
    }
    scale = np.abs(k).max() * alpha
    for name, u in modes.items():
        assert np.abs(k @ u).max() < 1e-12 * scale, name
        for xi, eta in ((0.0, 0.0), (0.6, -0.4), (-1.0, 1.0)):
            dN, _ = physical_derivatives(xy, xi, eta)
            assert np.abs(bending_rows(dN) @ u).max() < 1e-12 * alpha, name
            assert np.abs(shear_rows(xy, xi, eta) @ u).max() < 1e-12 * alpha, name


@pytest.mark.parametrize("xy", [RECTANGLE, SKEWED], ids=["rectangle", "skewed"])
def test_a_pure_bending_field_is_carried_exactly_with_zero_transverse_shear(xy):
    """w = -kappa x^2 / 2, theta_y = kappa x: constant curvature kappa_x, no shear at any point; the nodal forces are the edge moments."""
    kappa = 0.01
    u = nodal_field(xy, w=lambda x, y: -kappa * x * x / 2.0, theta_y=lambda x, y: kappa * x)
    for xi, eta in ((0.0, 0.0), (0.6, -0.4), (-1.0, 1.0), (1.0, 1.0)):
        dN, _ = physical_derivatives(xy, xi, eta)
        assert bending_rows(dN) @ u == pytest.approx([kappa, 0.0, 0.0], abs=1e-14)
        assert shear_rows(xy, xi, eta) @ u == pytest.approx([0.0, 0.0], abs=1e-14)
    k = element_stiffness_shell(xy, A, B, D, HS)
    f = k @ u
    assert np.abs(f[2::5]).max() < 1e-12 * np.abs(k).max() * np.abs(u).max()  # no transverse forces beyond roundoff of the product
    if xy is RECTANGLE:
        b = 0.05  # the moments about y at the nodes are M_x b / 2 at each end, opposite in sign
        assert f[4::5] == pytest.approx([-D[0, 0] * kappa * b / 2, D[0, 0] * kappa * b / 2, D[0, 0] * kappa * b / 2, -D[0, 0] * kappa * b / 2])


def test_pressure_loads_are_consistent_and_sum_to_the_load():
    f = pressure_loads(RECTANGLE, 1000.0)
    assert f[2::5].sum() == pytest.approx(-1000.0 * 0.1 * 0.05)  # a positive pressure pushes toward -z
    assert f[2::5] == pytest.approx(np.full(4, -1000.0 * 0.1 * 0.05 / 4))  # equal shares on a rectangle
    assert np.all(f[0::5] == 0.0) and np.all(f[1::5] == 0.0) and np.all(f[3::5] == 0.0) and np.all(f[4::5] == 0.0)
    x, y = SKEWED[:, 0], SKEWED[:, 1]
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))  # the shoelace formula
    assert pressure_loads(SKEWED, 1.0)[2::5].sum() == pytest.approx(-area)


def test_a_clockwise_element_is_refused():
    with pytest.raises(KernelError, match="clockwise"):
        element_stiffness_shell(RECTANGLE[::-1], A, B, D, HS)
