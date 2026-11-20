"""A sandwich panel's stiffness: the faces' plies at their own heights, the core adding distance only."""

import numpy as np
import pytest

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.rotation import transformed_reduced_stiffness
from anisotropy_engine.sandwich import sandwich_abd, sandwich_interfaces

AS4 = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27)  # Daniel & Ishai Table A.4


def stack(angles, t=0.125e-3):
    return [Ply(material=AS4, angle_deg=a, thickness_m=t) for a in angles]


def test_without_a_core_it_is_the_laminate_of_the_two_faces():
    lower, upper = stack([0, 45, -45]), stack([-45, 45, 0])
    for got, want in zip(sandwich_abd(lower, 0.0, upper), abd_matrices(lower + upper)):
        np.testing.assert_allclose(got, want, rtol=1e-13, atol=1e-9)


def test_one_ply_faces_follow_the_parallel_axis_theorem():
    t, core = 0.2e-3, 6e-3
    A, B, D = sandwich_abd(stack([0], t), core, stack([0], t))
    Q = transformed_reduced_stiffness(AS4, 0)
    d = (core + t) / 2  # each face's mid-plane from the panel's
    np.testing.assert_allclose(A, 2 * Q * t, rtol=1e-13)
    np.testing.assert_allclose(B, 0, atol=1e-9 * np.abs(A).max() * (core + 2 * t))
    np.testing.assert_allclose(D, 2 * Q * (t**3 / 12 + t * d**2), rtol=1e-12)


def test_the_core_raises_bending_stiffness_and_leaves_membrane_stiffness():
    face = stack([0, 45, -45, 90])
    A0, _, D0 = sandwich_abd(face, 0.0, face[::-1])
    A1, B1, D1 = sandwich_abd(face, 5e-3, face[::-1])
    np.testing.assert_allclose(A1, A0, rtol=1e-13)
    assert np.abs(B1).max() < 1e-9 * np.abs(A1).max() * 6e-3  # mirrored faces: still symmetric
    assert D1[0, 0] > 50 * D0[0, 0]


def test_interfaces_run_from_the_bottom_face_to_the_top_with_the_core_between():
    z_lower, z_upper = sandwich_interfaces(stack([0, 90], 1e-3), 4e-3, stack([90], 2e-3))
    np.testing.assert_allclose(z_lower, [-4e-3, -3e-3, -2e-3])
    np.testing.assert_allclose(z_upper, [2e-3, 4e-3])


@pytest.mark.parametrize("core", [-1e-3, float("nan"), float("inf")])
def test_a_core_thickness_that_is_not_a_length_is_refused(core):
    with pytest.raises(ValueError, match="Core thickness"):
        sandwich_abd(stack([0]), core, stack([0]))


def test_a_face_without_plies_is_refused():
    with pytest.raises(ValueError, match="each face"):
        sandwich_abd([], 1e-3, stack([0]))
