import math

import numpy as np
import pytest
from pydantic import ValidationError

from anisotropy_engine.failure import first_ply_failure, margin_of_safety, max_stress_ratio, tsai_wu_ratio
from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads

# AS4/3501-6, Daniel & Ishai Table A.4 (p. 377), the same values as the website's material library. Pa.
STRENGTHS = Strengths(F1t=2280e6, F1c=1725e6, F2t=57e6, F2c=228e6, F6=76e6)
AS4 = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27, strengths=STRENGTHS)
T = 0.25e-3  # ply thickness, m
QUASI_ISOTROPIC = [0, 45, -45, 90, 90, -45, 45, 0]


def stack(angles, thickness=T, material=AS4):
    """Plies at the given angles, bottom face first."""
    return [Ply(material=material, angle_deg=angle, thickness_m=thickness) for angle in angles]


@pytest.mark.parametrize("stress_mpa, ratio, mode", [
    ([1000, 0, 0], 2.28, "longitudinal tension"),
    ([-1000, 0, 0], 1.725, "longitudinal compression"),
    ([0, 10, 0], 5.7, "transverse tension"),
    ([0, -100, 0], 2.28, "transverse compression"),
    ([0, 0, -38], 2.0, "in-plane shear"),
    ([500, 20, 30], 76 / 30, "in-plane shear"),  # limits 4.56, 2.85 and 2.53: shear is closest
])
def test_max_stress_ratio_takes_the_closest_limit(stress_mpa, ratio, mode):
    r, m = max_stress_ratio(np.array(stress_mpa) * 1e6, STRENGTHS)
    assert r == pytest.approx(ratio)
    assert m == mode


def test_unstressed_ply_never_fails():
    assert max_stress_ratio(np.zeros(3), STRENGTHS) == (math.inf, "none")
    assert tsai_wu_ratio(np.zeros(3), STRENGTHS, -0.5) == math.inf


@pytest.mark.parametrize("f12_star", [-0.5, 0.0, 0.3])
@pytest.mark.parametrize("stress", [
    [2280e6, 0, 0], [-1725e6, 0, 0], [0, 57e6, 0], [0, -228e6, 0], [0, 0, 76e6], [0, 0, -76e6],
])
def test_tsai_wu_reproduces_every_uniaxial_strength(stress, f12_star):
    # Loading exactly to one basic strength must give R = 1, whatever the interaction term.
    assert tsai_wu_ratio(np.array(stress), STRENGTHS, f12_star) == pytest.approx(1.0)


def test_tsai_wu_matches_the_textbook_root_formula():
    # Daniel & Ishai Eq. 6.59, R = (-b + sqrt(b^2 + 4a)) / 2a, with f12 from Eq. 6.40.
    s1, s2, t6 = 500e6, 20e6, 30e6
    f1, f2 = 1 / 2280e6 - 1 / 1725e6, 1 / 57e6 - 1 / 228e6
    f11, f22, f66 = 1 / (2280e6 * 1725e6), 1 / (57e6 * 228e6), 1 / 76e6**2
    f12 = -0.5 * math.sqrt(f11 * f22)
    a = f11 * s1**2 + f22 * s2**2 + f66 * t6**2 + 2 * f12 * s1 * s2
    b = f1 * s1 + f2 * s2
    expected = (-b + math.sqrt(b * b + 4 * a)) / (2 * a)
    assert tsai_wu_ratio(np.array([s1, s2, t6]), STRENGTHS, -0.5) == pytest.approx(expected, rel=1e-12)
    assert expected == pytest.approx(1.78508, rel=1e-5)


def test_strength_ratio_halves_when_the_stress_doubles():
    stress = np.array([300e6, 15e6, -20e6])
    assert tsai_wu_ratio(2 * stress, STRENGTHS, -0.5) == pytest.approx(tsai_wu_ratio(stress, STRENGTHS, -0.5) / 2)
    assert max_stress_ratio(2 * stress, STRENGTHS)[0] == pytest.approx(max_stress_ratio(stress, STRENGTHS)[0] / 2)


@pytest.mark.parametrize("f12_star", [-1.0, 1.0, 1.5, float("nan")])
def test_tsai_wu_rejects_an_open_failure_envelope(f12_star):
    with pytest.raises(ValueError):
        tsai_wu_ratio(np.array([1e6, 0, 0]), STRENGTHS, f12_star)


def test_margin_of_safety():
    assert margin_of_safety(1.5, 1.5) == pytest.approx(0.0)
    assert margin_of_safety(3.0, 1.5) == pytest.approx(1.0)
    assert margin_of_safety(0.9, 1.0) == pytest.approx(-0.1)
    with pytest.raises(ValueError):
        margin_of_safety(2.0, 0.9)


def test_compressive_strengths_are_entered_as_positive_magnitudes():
    with pytest.raises(ValidationError):
        Strengths(F1t=2280e6, F1c=-1725e6, F2t=57e6, F2c=228e6, F6=76e6)


@pytest.mark.parametrize("loads, strength_pa, mode", [
    (Loads(Nx=1e3), 2280e6, "longitudinal tension"),
    (Loads(Nx=-1e3), 1725e6, "longitudinal compression"),
    (Loads(Ny=1e3), 57e6, "transverse tension"),
    (Loads(Ny=-1e3), 228e6, "transverse compression"),
])
def test_unidirectional_ply_fails_at_its_basic_strengths(loads, strength_pa, mode):
    # One 0 deg ply carries a uniform stress N / h, so failure is reached exactly at the basic strength.
    result = first_ply_failure(stack([0]), loads)
    assert np.abs(result.failure_loads.as_vector()).max() / T == pytest.approx(strength_pa)
    assert result.governing.mode == mode


@pytest.mark.parametrize("shear_n_per_m, strength_pa, mode", [
    (1e3, 228e6, "transverse compression"),
    (-1e3, 57e6, "transverse tension"),
])
def test_shear_strength_at_45_degrees_follows_the_transverse_strengths(shear_n_per_m, strength_pa, mode):
    # Daniel & Ishai Sample Problem 6.1: positive shear at 45 deg to the fibers is limited by F2c and
    # negative shear by F2t. Under maximum stress the result is exact.
    result = first_ply_failure(stack([45]), Loads(Nxy=shear_n_per_m))
    assert abs(result.failure_loads.Nxy) / T == pytest.approx(strength_pa)
    assert result.governing.mode == mode


def test_angle_ply_axial_strength_is_twice_the_shear_strength():
    # Daniel & Ishai Sample Problem 9.1: [+-45]s axial strength is about 2 F6. Under maximum stress
    # it is exact, because every ply sees tau12 = sigma_x / 2.
    result = first_ply_failure(stack([45, -45, -45, 45]), Loads(Nx=1e5))
    assert result.failure_loads.Nx / (4 * T) == pytest.approx(2 * 76e6)
    assert result.governing.mode == "in-plane shear"


def test_bending_fails_the_compressive_face_first():
    # Faces see sigma_x = +-6 M / h^2 (chunk 4). F1c < F1t, so the bottom face, in compression, governs.
    result = first_ply_failure(stack([0]), Loads(Mx=2.0))
    assert result.strength_ratio == pytest.approx(1725e6 / (6 * 2.0 / T**2))
    assert result.governing.mode == "longitudinal compression"
    assert result.governing.z_m == pytest.approx(-T / 2)


def test_quasi_isotropic_laminate_cracks_in_the_90_degree_ply_first():
    result = first_ply_failure(stack(QUASI_ISOTROPIC), Loads(Nx=1e5))
    assert result.governing.angle_deg == 90
    assert result.governing.mode == "transverse tension"
    assert result.strength_ratio == pytest.approx(6.949000, rel=1e-6)
    assert len(result.checks) == 2 * len(QUASI_ISOTROPIC)
    # At the failure load, the governing ply's transverse stress reaches F2t exactly.
    assert result.governing.stress_12[1] * result.strength_ratio == pytest.approx(57e6)


def test_coupon_example_cracks_before_20_kn():
    # [45/-45/0/90]2s, 0.13 mm plies, 25 mm wide coupon pulled with 20 kN, so Nx = P / w.
    angles = [45, -45, 0, 90] * 2
    plies = stack(angles + angles[::-1], thickness=0.13e-3)
    loads = Loads(Nx=20e3 / 0.025)
    max_stress = first_ply_failure(plies, loads)
    assert max_stress.governing.angle_deg == 90
    assert max_stress.governing.mode == "transverse tension"
    assert max_stress.failure_loads.Nx * 0.025 / 1e3 == pytest.approx(18.0674, abs=1e-4)  # kN
    assert margin_of_safety(max_stress.strength_ratio, 1.0) < 0
    tsai_wu = first_ply_failure(plies, loads, "tsai_wu", f12_star=-0.5)
    assert tsai_wu.failure_loads.Nx * 0.025 / 1e3 == pytest.approx(16.6784, abs=1e-4)  # kN


def test_failure_loads_do_not_depend_on_the_reference_load():
    plies = stack(QUASI_ISOTROPIC)
    small = first_ply_failure(plies, Loads(Nx=1e4, Nxy=2e3))
    large = first_ply_failure(plies, Loads(Nx=1e6, Nxy=2e5))
    assert large.strength_ratio == pytest.approx(small.strength_ratio / 100)
    np.testing.assert_allclose(large.failure_loads.as_vector(), small.failure_loads.as_vector(), rtol=1e-9)


def test_invalid_requests_are_rejected():
    plies = stack([0, 90, 90, 0])
    with pytest.raises(ValueError, match="nonzero"):
        first_ply_failure(plies, Loads())
    with pytest.raises(ValueError, match="f12_star"):
        first_ply_failure(plies, Loads(Nx=1e5), "tsai_wu")
    with pytest.raises(ValueError, match="criterion"):
        first_ply_failure(plies, Loads(Nx=1e5), "hashin")
    no_strengths = AS4.model_copy(update={"strengths": None})
    with pytest.raises(ValueError, match="strengths"):
        first_ply_failure(stack([0], material=no_strengths), Loads(Nx=1e5))
