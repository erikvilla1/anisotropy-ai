"""Plate buckling against Whitney's closed-form examples, the Ritz series against the closed form,
and the series' own properties (upper bound, convergence, symmetry)."""

import math

import numpy as np
import pytest

from anisotropy_engine.buckling import (
    is_specially_orthotropic, navier_buckling, plate_bending_stiffness, plate_buckling, ritz_buckling,
)
from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply, abd_matrices

AS4 = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27)  # Daniel & Ishai Table A.4


def stack(angles, t=0.25e-3, material=AS4):
    return [Ply(material=material, angle_deg=a, thickness_m=t) for a in angles]


def whitney_D(d11_over_d22=10.0, d12_2d66_over_d22=1.0, d22=1.0):
    """Specially orthotropic D with the ratios of Whitney's worked examples, Section 5.5."""
    return np.array([[d11_over_d22 * d22, 0.0, 0.0], [0.0, d22, 0.0], [0.0, 0.0, d12_2d66_over_d22 * d22 / 2]])


def test_whitney_case_i_square_plate_under_uniaxial_compression():
    # Whitney Eq. 5.76: D11/D22 = 10, (D12 + 2 D66)/D22 = 1, R = 1: N_cr = 13 pi^2 D22 / a^2.
    a = 0.5
    result = navier_buckling(whitney_D(), a, a, [-1.0, 0.0, 0.0])
    assert result.load_factor == pytest.approx(13 * math.pi**2 / a**2)
    assert result.mode == (1, 1)
    np.testing.assert_allclose(result.critical_loads, [-13 * math.pi**2 / a**2, 0, 0])


def test_whitney_absolute_minimum_at_aspect_ratio_1_78():
    # Whitney Eqs. 5.80-5.81: the lowest value over aspect ratio, N_cr = (2 sqrt(10) + 2) pi^2 D22 / b^2
    # at a/b = 10^(1/4) = 1.778, where the plate buckles with one half-wave.
    b = 0.3
    a = b * 10**0.25
    result = navier_buckling(whitney_D(), a, b, [-1.0, 0.0, 0.0])
    assert result.load_factor == pytest.approx((2 * math.sqrt(10) + 2) * math.pi**2 / b**2)
    assert result.load_factor == pytest.approx(8.32 * math.pi**2 / b**2, rel=2e-3)
    assert result.mode == (1, 1)
    # A longer plate buckles into more half-waves and is never below the absolute minimum.
    longer = navier_buckling(whitney_D(), 3.1 * b, b, [-1.0, 0.0, 0.0])
    assert longer.mode[0] == 2 and longer.load_factor >= result.load_factor


def test_whitney_case_ii_square_plate_under_equal_biaxial_compression():
    # Whitney Eq. 5.84: k = 1 gives N_cr = 6.5 pi^2 D22 / a^2 with m = n = 1.
    a = 0.4
    result = navier_buckling(whitney_D(), a, a, [-1.0, -1.0, 0.0])
    assert result.load_factor == pytest.approx(6.5 * math.pi**2 / a**2)
    assert result.mode == (1, 1)


def test_whitney_case_iii_transverse_tension_doubles_the_critical_load():
    # Whitney Eq. 5.87: k = -0.5 (Ny tensile at half of Nx) gives N_cr = 26 pi^2 D22 / a^2.
    a = 0.4
    result = navier_buckling(whitney_D(), a, a, [-1.0, 0.5, 0.0])
    assert result.load_factor == pytest.approx(26 * math.pi**2 / a**2)


def test_pure_tension_cannot_buckle_and_shear_needs_the_series():
    with pytest.raises(ValueError, match="no buckling"):
        navier_buckling(whitney_D(), 1.0, 1.0, [1.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="shear needs the Ritz"):
        navier_buckling(whitney_D(), 1.0, 1.0, [0.0, 0.0, 1.0])
    with pytest.raises(ValueError, match="nonzero reference load"):
        navier_buckling(whitney_D(), 1.0, 1.0, [0.0, 0.0, 0.0])


def test_ritz_reproduces_the_closed_form_for_a_specially_orthotropic_plate():
    D = whitney_D()
    for a, b, loads in [(0.5, 0.5, [-1.0, 0.0, 0.0]), (0.9, 0.3, [-1.0, 0.0, 0.0]), (0.4, 0.4, [-1.0, -1.0, 0.0]), (0.4, 0.4, [-1.0, 0.5, 0.0])]:
        exact = navier_buckling(D, a, b, loads, (6, 6))
        series = ritz_buckling(D, a, b, loads, 6)
        assert series.load_factor == pytest.approx(exact.load_factor, rel=1e-10)
        assert series.orthotropic_factor == pytest.approx(exact.load_factor, rel=1e-10)
        m, n = exact.mode
        assert abs(series.mode_shape[m - 1, n - 1]) == pytest.approx(1.0)


def test_a_cross_ply_laminate_is_specially_orthotropic_and_an_angle_ply_is_not():
    D_cross = plate_bending_stiffness(stack([0, 90, 90, 0]))
    assert is_specially_orthotropic(D_cross)
    D_angle = plate_bending_stiffness(stack([45, -45, -45, 45]))
    assert not is_specially_orthotropic(D_angle)
    with pytest.raises(ValueError, match="midplane-symmetric"):
        plate_bending_stiffness(stack([0, 90]))


def test_bending_twisting_coupling_lowers_the_buckling_load_below_the_orthotropic_estimate():
    # The Ritz space contains the orthotropic mode, on which D16 and D26 contribute nothing, so the
    # series minimum can only be lower (Whitney Section 6.5: the orthotropic solution is nonconservative).
    plies = stack([45, -45, -45, 45] * 2)
    result = plate_buckling(plies, 0.3, 0.3, [-1.0, 0.0, 0.0], terms=7)
    assert result.method == "ritz"
    assert result.load_factor < result.orthotropic_factor
    assert result.load_factor > 0.5 * result.orthotropic_factor


def test_ritz_converges_from_above_as_terms_increase():
    plies = stack([30, -30, -30, 30] * 2)
    factors = [plate_buckling(plies, 0.3, 0.2, [-1.0, 0.0, 0.0], terms=k).load_factor for k in (1, 2, 3, 5, 7, 9)]
    assert all(later <= earlier + 1e-12 for earlier, later in zip(factors, factors[1:]))
    assert abs(factors[-1] - factors[-2]) / factors[-1] < 5e-3


def test_mirroring_the_layup_mirrors_the_shear_direction_but_not_compression():
    # Flipping every angle flips D16 and D26. Compression cannot tell the two plates apart;
    # positive shear on one is negative shear on the other.
    plus, minus = stack([45, -45, -45, 45] * 2), stack([-45, 45, 45, -45] * 2)
    compression = [plate_buckling(p, 0.3, 0.2, [-1.0, 0.0, 0.0], terms=7).load_factor for p in (plus, minus)]
    assert compression[0] == pytest.approx(compression[1], rel=1e-10)
    shear_plus = plate_buckling(plus, 0.3, 0.2, [0.0, 0.0, 1.0], terms=7).load_factor
    shear_minus_on_mirror = plate_buckling(minus, 0.3, 0.2, [0.0, 0.0, -1.0], terms=7).load_factor
    assert shear_plus == pytest.approx(shear_minus_on_mirror, rel=1e-10)
    # Whitney Section 6.5: a 45-degree plate resists shear in one direction far better than the other.
    shear_minus = plate_buckling(plus, 0.3, 0.2, [0.0, 0.0, -1.0], terms=7).load_factor
    assert shear_plus != pytest.approx(shear_minus, rel=0.05)


def test_plate_buckling_requires_terms_when_the_closed_form_does_not_apply():
    with pytest.raises(ValueError, match="give the number of Ritz terms"):
        plate_buckling(stack([45, -45, -45, 45]), 0.3, 0.3, [-1.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="positive integer"):
        ritz_buckling(whitney_D(), 1.0, 1.0, [-1.0, 0.0, 0.0], 0)
    with pytest.raises(ValueError, match="positive"):
        navier_buckling(whitney_D(), -1.0, 1.0, [-1.0, 0.0, 0.0])
    closed = plate_buckling(stack([0, 90, 90, 0]), 0.3, 0.3, [-1.0, 0.0, 0.0])
    assert closed.method == "navier" and closed.terms is None


def test_single_ply_plate_matches_the_hand_formula():
    # One 0-degree ply, square: N_cr = pi^2 [D11 + 2 (D12 + 2 D66) + D22] / a^2 for m = n = 1.
    plies = stack([0], t=1e-3)
    _, _, D = abd_matrices(plies)
    a = 0.1
    result = plate_buckling(plies, a, a, [-1.0, 0.0, 0.0])
    assert result.load_factor == pytest.approx(math.pi**2 * (D[0, 0] + 2 * (D[0, 1] + 2 * D[2, 2]) + D[1, 1]) / a**2)
