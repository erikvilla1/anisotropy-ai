import numpy as np
import pytest
from pydantic import ValidationError

from anisotropy_engine.lamina import Lamina, reduced_stiffness

# Carbon/epoxy inputs from Daniel & Ishai Problem 7.11, in Pa.
CARBON = Lamina(E1=145e9, E2=10.5e9, G12=7e9, nu12=0.28)


def test_minor_poisson_ratio_follows_reciprocity():
    assert CARBON.nu21 == pytest.approx(0.28 * 10.5 / 145)


def test_carbon_epoxy_q_matches_hand_calculation():
    # nu21 = 0.0202759, so 1 - nu12 * nu21 = 0.994323.
    # Q11 = 145 / 0.994323, Q22 = 10.5 / 0.994323, Q12 = 0.28 * Q22, Q66 = G12.
    expected = np.array([
        [145.82790, 2.956786, 0.0],
        [2.956786, 10.559951, 0.0],
        [0.0, 0.0, 7.0],
    ]) * 1e9
    np.testing.assert_allclose(reduced_stiffness(CARBON), expected, rtol=1e-6, atol=1.0)


def test_isotropic_ply_reduces_to_plane_stress_hookes_law():
    E, nu = 70e9, 0.33
    q = reduced_stiffness(Lamina(E1=E, E2=E, G12=E / (2 * (1 + nu)), nu12=nu))
    assert q[0, 0] == pytest.approx(E / (1 - nu**2))
    assert q[0, 1] == pytest.approx(nu * E / (1 - nu**2))
    assert q[2, 2] == pytest.approx((q[0, 0] - q[0, 1]) / 2)


def test_q_is_symmetric_and_positive_definite():
    q = reduced_stiffness(CARBON)
    np.testing.assert_array_equal(q, q.T)
    assert np.all(np.linalg.eigvalsh(q) > 0)


@pytest.mark.parametrize("bad", [
    {"E1": 0.0},
    {"E2": -1e9},
    {"G12": float("nan")},
    {"E1": float("inf")},
    {"nu12": 10.0},
])
def test_invalid_constants_are_rejected(bad):
    with pytest.raises(ValidationError):
        Lamina(**{**CARBON.model_dump(), **bad})
