import numpy as np
import pytest
from pydantic import ValidationError

from anisotropy_engine.lamina import Lamina, reduced_stiffness
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.response import Loads, abd_matrix, midplane_response, ply_surfaces

CARBON = Lamina(E1=145e9, E2=10.5e9, G12=7e9, nu12=0.28)
T = 0.25e-3  # ply thickness, m
QUASI_ISOTROPIC = [0, 45, -45, 90, 90, -45, 45, 0]
MIXED = Loads(Nx=1e5, Ny=2e4, Nxy=-5e3, Mx=3, My=-1, Mxy=0.5)


def stack(angles, thickness=T):
    """CARBON plies at the given angles, bottom face first."""
    return [Ply(material=CARBON, angle_deg=angle, thickness_m=thickness) for angle in angles]


def solve(plies, loads):
    eps0, kappa = midplane_response(plies, loads)
    return eps0, kappa, ply_surfaces(plies, eps0, kappa)


def faces(surfaces):
    """(bottom, top) pairs, one per ply."""
    return zip(surfaces[::2], surfaces[1::2])


def test_abd_matrix_places_the_a_b_d_blocks():
    plies = stack([0, 90])
    A, B, D = abd_matrices(plies)
    abd = abd_matrix(plies)
    assert abd.shape == (6, 6)
    np.testing.assert_array_equal(abd[:3, :3], A)
    np.testing.assert_array_equal(abd[:3, 3:], B)
    np.testing.assert_array_equal(abd[3:, :3], B)
    np.testing.assert_array_equal(abd[3:, 3:], D)
    np.testing.assert_allclose(abd, abd.T, rtol=1e-12, atol=1e-6)


def test_loads_default_to_zero_and_follow_abd_row_order():
    np.testing.assert_array_equal(Loads().as_vector(), np.zeros(6))
    np.testing.assert_array_equal(Loads(Nx=5, Mxy=-2).as_vector(), [5, 0, 0, 0, 0, -2])
    with pytest.raises(ValidationError):
        Loads(Nx=float("nan"))


def test_solution_reproduces_the_applied_loads():
    plies = stack(QUASI_ISOTROPIC)
    eps0, kappa = midplane_response(plies, MIXED)
    np.testing.assert_allclose(
        abd_matrix(plies) @ np.concatenate([eps0, kappa]), MIXED.as_vector(), rtol=1e-9, atol=1e-6
    )


def test_single_zero_degree_ply_matches_hand_calculation():
    # One ply carries sigma_x = Nx / h; its strains follow from the compliance in chunk 1.
    eps0, kappa, surfaces = solve(stack([0]), Loads(Nx=1000.0))
    sigma_x = 1000.0 / T
    np.testing.assert_allclose(eps0, [sigma_x / 145e9, -0.28 * sigma_x / 145e9, 0], rtol=1e-12, atol=1e-18)
    np.testing.assert_allclose(kappa, 0, atol=1e-12)
    for surface in surfaces:
        np.testing.assert_allclose(surface.stress_xy, [sigma_x, 0, 0], rtol=1e-12, atol=1e-3)


def test_single_ply_in_bending_matches_the_beam_formula():
    # sigma = M c / I with c = h/2 and I = h^3/12 per unit width, so sigma_x = +-6 Mx / h^2.
    _, _, surfaces = solve(stack([0]), Loads(Mx=2.0))
    bottom, top = surfaces
    sigma = 6 * 2.0 / T**2
    np.testing.assert_allclose(top.stress_xy, [sigma, 0, 0], rtol=1e-9, atol=1e-3)
    np.testing.assert_allclose(bottom.stress_xy, [-sigma, 0, 0], rtol=1e-9, atol=1e-3)


def test_symmetric_laminate_does_not_warp_under_in_plane_load():
    _, kappa = midplane_response(stack([0, 90, 90, 0]), Loads(Nx=1e5))
    np.testing.assert_allclose(kappa, 0, atol=1e-9)


def test_unsymmetric_cross_ply_curls_under_a_pure_stretch():
    eps0, kappa = midplane_response(stack([0, 90]), Loads(Nx=1e5))
    assert eps0[0] == pytest.approx(5.846752e-3, rel=1e-6)
    assert kappa[0] == pytest.approx(30.34295, rel=1e-6)  # 1/m, a curl of about 33 mm radius


def test_ply_forces_add_up_to_the_applied_forces():
    # Stress is linear through each ply, so average stress times thickness is the exact force.
    _, _, surfaces = solve(stack(QUASI_ISOTROPIC), MIXED)
    force = sum((bottom.stress_xy + top.stress_xy) / 2 * (top.z_m - bottom.z_m) for bottom, top in faces(surfaces))
    np.testing.assert_allclose(force, [MIXED.Nx, MIXED.Ny, MIXED.Nxy], rtol=1e-9)


def test_ply_moments_add_up_to_the_applied_moments():
    # Exact integral of a linearly varying stress times z over one ply.
    _, _, surfaces = solve(stack(QUASI_ISOTROPIC), MIXED)
    moment = np.zeros(3)
    for bottom, top in faces(surfaces):
        zb, zt = bottom.z_m, top.z_m
        moment += (zt - zb) / 6 * (bottom.stress_xy * (2 * zb + zt) + top.stress_xy * (zb + 2 * zt))
    np.testing.assert_allclose(moment, [MIXED.Mx, MIXED.My, MIXED.Mxy], rtol=1e-9)


def test_fiber_axis_stress_obeys_hookes_law_on_every_face():
    q = reduced_stiffness(CARBON)
    _, _, surfaces = solve(stack(QUASI_ISOTROPIC), MIXED)
    for surface in surfaces:
        np.testing.assert_allclose(surface.stress_12, q @ surface.strain_12, rtol=1e-9, atol=1e-3)


def test_strain_is_continuous_across_an_interface_but_stress_jumps():
    _, _, surfaces = solve(stack([0, 90]), Loads(Nx=1e5))
    assert [s.ply_index for s in surfaces] == [0, 0, 1, 1]
    np.testing.assert_allclose([s.z_m for s in surfaces], [-T, 0, 0, T], atol=1e-15)
    top_of_0, bottom_of_90 = surfaces[1], surfaces[2]
    np.testing.assert_allclose(top_of_0.strain_xy, bottom_of_90.strain_xy)
    assert top_of_0.stress_xy[0] / 1e6 == pytest.approx(851.9659, abs=1e-4)
    assert bottom_of_90.stress_xy[0] / 1e6 == pytest.approx(61.0877, abs=1e-4)


@pytest.mark.parametrize("ply_index, expected_mpa", [
    (0, [125.8873, -0.0960, 0.0]),
    (1, [45.8359, 4.1641, -7.8443]),
    (2, [45.8359, 4.1641, 7.8443]),
    (3, [-34.2155, 8.4242, 0.0]),
])
def test_quasi_isotropic_ply_stresses_under_uniaxial_load(ply_index, expected_mpa):
    # Computed regression values, not printed in a book. kappa = 0, so both faces agree.
    _, _, surfaces = solve(stack(QUASI_ISOTROPIC), Loads(Nx=1e5))
    for surface in surfaces[2 * ply_index:2 * ply_index + 2]:
        np.testing.assert_allclose(surface.stress_12 / 1e6, expected_mpa, atol=1e-4)


def test_ply_surfaces_needs_three_component_vectors():
    with pytest.raises(ValueError):
        ply_surfaces(stack([0]), np.zeros(2), np.zeros(3))
