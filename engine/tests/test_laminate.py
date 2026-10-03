import numpy as np
import pytest
from pydantic import ValidationError

from anisotropy_engine.lamina import Lamina, reduced_stiffness
from anisotropy_engine.laminate import Ply, abd_matrices, ply_interfaces
from anisotropy_engine.rotation import transformed_reduced_stiffness

CARBON = Lamina(E1=145e9, E2=10.5e9, G12=7e9, nu12=0.28)
T = 0.25e-3  # ply thickness, m


def stack(angles, thickness=T):
    """CARBON plies at the given angles, bottom face first."""
    return [Ply(material=CARBON, angle_deg=angle, thickness_m=thickness) for angle in angles]


def test_interfaces_run_from_bottom_face_to_top_face():
    np.testing.assert_allclose(
        ply_interfaces(stack([0, 45, -45])), [-0.375e-3, -0.125e-3, 0.125e-3, 0.375e-3], atol=1e-12
    )


def test_problem_7_11_matches_printed_extensional_stiffness():
    # Daniel & Ishai Problem 7.11: [0/45/-45], 0.25 mm plies. Answers printed to 0.01 MN/m.
    A, _, _ = abd_matrices(stack([0, 45, -45]))
    printed = {(0, 0): 60.24, (0, 1): 17.53, (1, 1): 26.43, (2, 2): 20.56}
    for (i, j), value in printed.items():
        assert A[i, j] / 1e6 == pytest.approx(value, abs=0.005)
    # The +45 and -45 plies cancel the in-plane shear coupling.
    assert A[0, 2] == pytest.approx(0, abs=1.0)
    assert A[1, 2] == pytest.approx(0, abs=1.0)


@pytest.mark.parametrize("angle", [0, 30, -60])
def test_single_ply_is_centred_on_the_mid_plane(angle):
    # z runs from -t/2 to +t/2, so A = Q_bar t, B = 0 and D = Q_bar t^3 / 12.
    q_bar = transformed_reduced_stiffness(CARBON, angle)
    A, B, D = abd_matrices(stack([angle]))
    np.testing.assert_allclose(A, q_bar * T, rtol=1e-12, atol=1e-6)
    np.testing.assert_allclose(B, 0, atol=1e-9)
    np.testing.assert_allclose(D, q_bar * T**3 / 12, rtol=1e-12, atol=1e-15)


def test_symmetric_laminate_has_no_extension_bending_coupling():
    _, B, _ = abd_matrices(stack([0, 90, 90, 0]))
    np.testing.assert_allclose(B, 0, atol=1e-6)


def test_unsymmetric_cross_ply_couples_and_flipping_reverses_the_coupling():
    q = reduced_stiffness(CARBON)
    A, B, D = abd_matrices(stack([0, 90]))
    # z = -t, 0, +t, so B11 = 1/2 t^2 (Q22 - Q11).
    assert B[0, 0] == pytest.approx(0.5 * T**2 * (q[1, 1] - q[0, 0]))
    assert B[0, 0] / 1e3 == pytest.approx(-4.22712, abs=1e-5)
    assert B[1, 1] == pytest.approx(-B[0, 0])
    A_flipped, B_flipped, D_flipped = abd_matrices(stack([90, 0]))
    np.testing.assert_allclose(B_flipped, -B, atol=1e-6)
    np.testing.assert_allclose(A_flipped, A, atol=1e-6)
    np.testing.assert_allclose(D_flipped, D, atol=1e-12)


def test_doubling_ply_thickness_scales_a_b_d_by_2_4_8():
    A1, B1, D1 = abd_matrices(stack([0, 90]))
    A2, B2, D2 = abd_matrices(stack([0, 90], thickness=2 * T))
    np.testing.assert_allclose(A2, 2 * A1, atol=1e-6)
    np.testing.assert_allclose(B2, 4 * B1, atol=1e-6)
    np.testing.assert_allclose(D2, 8 * D1, atol=1e-12)


def test_balanced_symmetric_laminate_still_twists_when_bent():
    # [45/-45]s has no in-plane shear coupling and no B, but the outer +45 plies leave D16 and D26.
    A, B, D = abd_matrices(stack([45, -45, -45, 45]))
    assert A[0, 2] == pytest.approx(0, abs=1.0)
    assert A[1, 2] == pytest.approx(0, abs=1.0)
    np.testing.assert_allclose(B, 0, atol=1e-6)
    assert D[0, 2] == pytest.approx(2.11356, abs=1e-5)
    assert D[1, 2] == pytest.approx(2.11356, abs=1e-5)


def test_quasi_isotropic_laminate_is_isotropic_in_plane():
    A, _, _ = abd_matrices(stack([0, 45, -45, 90, 90, -45, 45, 0]))
    assert A[0, 0] == pytest.approx(A[1, 1])
    assert A[2, 2] == pytest.approx((A[0, 0] - A[0, 1]) / 2)
    assert A[0, 2] == pytest.approx(0, abs=1.0)
    assert A[1, 2] == pytest.approx(0, abs=1.0)


def test_empty_stack_is_rejected():
    with pytest.raises(ValueError):
        abd_matrices([])


@pytest.mark.parametrize("bad", [{"thickness_m": 0.0}, {"thickness_m": -1e-4}, {"angle_deg": float("nan")}])
def test_invalid_ply_is_rejected(bad):
    with pytest.raises(ValidationError):
        Ply(**{"material": CARBON, "angle_deg": 0.0, "thickness_m": T, **bad})
