"""Divergence and aileron reversal of the uniform wing (ADR-0115 amendment 1): the closed forms against a finite-difference solution of the
same torsion equation written here without the engine's formulas, and the checks as the wing calculation reports them."""

import math

import numpy as np
import pytest

from anisotropy_engine.wing import analyze_wing, wing_from_dict, wing_report
from anisotropy_engine.wing.aeroelastic import (
    aileron_lift, divergence_dynamic_pressure, equivalent_airspeed, reversal_dynamic_pressure, twist_influence,
)
from anisotropy_engine.wing.atmosphere import SEA_LEVEL_DENSITY, density_ratio

from test_wing import example, run

GJ, L, C, E, A = 2.0e4, 2.0, 0.45, 0.05, 6.0  # N m^2, m, m, m, per rad: a wing of the example's size


def torsion_matrix(L: float, n: int) -> tuple[np.ndarray, np.ndarray, float]:
    """Second differences of theta on n intervals with theta(0) = 0 and theta'(L) = 0 (a mirrored ghost node at the tip).
    Returns the matrix acting on theta at the nodes 1..n, the nodes and the spacing."""
    h = L / n
    K = (np.diag(-2.0 * np.ones(n)) + np.diag(np.ones(n - 1), 1) + np.diag(np.ones(n - 1), -1)) / h**2
    K[-1, -2] = 2.0 / h**2  # theta_{n+1} = theta_{n-1}
    return K, np.linspace(h, L, n), h


def solve_shifted(n: int, shift: float, rhs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """theta at the nodes 1..n from (second difference + shift) theta = rhs, the matrix of torsion_matrix, by the tridiagonal
    (Thomas) elimination; returns theta and the nodes."""
    h = L / n
    lower = np.full(n, 1.0 / h**2)
    lower[-1] = 2.0 / h**2
    diagonal = np.full(n, -2.0 / h**2 + shift)
    upper = np.full(n, 1.0 / h**2)
    c, d = np.empty(n), np.empty(n)
    c[0], d[0] = upper[0] / diagonal[0], rhs[0] / diagonal[0]
    for i in range(1, n):
        m = diagonal[i] - lower[i] * c[i - 1]
        c[i] = upper[i] / m
        d[i] = (rhs[i] - lower[i] * d[i - 1]) / m
    theta = np.empty(n)
    theta[-1] = d[-1]
    for i in range(n - 2, -1, -1):
        theta[i] = d[i] - c[i] * theta[i + 1]
    return theta, np.linspace(h, L, n)


def fd_twist_integral(s: float, y1: float, y2: float, n: int = 4000) -> float:
    """The integral over [y1, y2] of psi with psi'' + s psi = 1, psi(0) = 0, psi'(L) = 0, by finite differences."""
    psi, y = solve_shifted(n, s, np.ones(n))
    return trapezoid_between(psi, y, y1, y2)


def trapezoid_between(values: np.ndarray, y: np.ndarray, y1: float, y2: float) -> float:
    """The integral over [y1, y2] of values at the nodes y (zero at the root), read linearly between nodes."""
    grid = np.r_[0.0, y]
    v = np.r_[0.0, values]
    fine = np.linspace(y1, y2, 20001)
    return float(np.trapezoid(np.interp(fine, grid, v), fine))


def test_divergence_is_the_lowest_eigenvalue_of_the_torsion_equation():
    K, _, _ = torsion_matrix(L, 500)
    lowest = np.sort(np.linalg.eigvals(-K).real)[0]  # theta'' + lambda^2 theta = 0 first has a solution at this lambda^2
    q_fd = lowest * GJ / (C * E * A)
    assert divergence_dynamic_pressure(GJ, L, C, E, A) == pytest.approx(q_fd, rel=1e-6)
    assert divergence_dynamic_pressure(GJ, L, C, E, A) == pytest.approx((math.pi / (2 * L)) ** 2 * GJ / (C * E * A), rel=1e-15)


@pytest.mark.parametrize("e", [0.0, -0.02])
def test_a_wing_whose_aerodynamic_center_is_not_ahead_of_its_shear_center_never_diverges(e):
    assert divergence_dynamic_pressure(GJ, L, C, e, A) == math.inf


@pytest.mark.parametrize("s", [0.3, 0.55, -0.4, -40.0, 1e-9, -1e-9])
def test_the_twist_integral_matches_a_finite_difference_solution(s):
    for y1, y2 in [(0.0, L), (1.2, 1.9), (0.3, 0.8)]:
        assert twist_influence(s, L, y1, y2) == pytest.approx(fd_twist_integral(s, y1, y2), rel=2e-5, abs=1e-9)


def test_the_twist_integral_is_continuous_where_its_series_takes_over():
    edge = 1e-6 / L**2
    for side in (1, -1):
        # the integral itself moves by about 1e-9 between the two, and rounding in the closed form is about as large
        assert twist_influence(side * edge * 0.999, L, 1.2, 1.9) == pytest.approx(twist_influence(side * edge * 1.001, L, 1.2, 1.9), rel=1e-8)


def fd_aileron_lift(q: float, dcl: float, dcm: float, y1: float, y2: float, n: int = 4000) -> float:
    """The lift the aileron adds, divided by q c, from the torsion equation solved by finite differences."""
    h = L / n
    y = np.linspace(h, L, n)
    # y1 and y2 fall on nodes (n = 4000 puts a node every 0.5 mm); a node at an end of the aileron inside the span carries half
    # its load (the tip's node already stands for half a spacing)
    inside = ((y >= y1 - h / 2) & (y <= y2 + h / 2)).astype(float)
    inside[(np.isclose(y, y1, atol=h / 4) | np.isclose(y, y2, atol=h / 4)) & ~np.isclose(y, L, atol=h / 4)] = 0.5
    moment = q * C * (E * dcl + C * dcm) * inside  # about the shear center, nose up, per unit span
    theta, _ = solve_shifted(n, q * C * E * A / GJ, -moment / GJ)
    return dcl * (y2 - y1) + A * trapezoid_between(theta, y, 0.0, L)


@pytest.mark.parametrize("y1, y2", [(1.2, 1.9), (0.0, L)])
def test_aileron_reversal_is_where_the_finite_difference_wing_loses_the_ailerons_lift(y1, y2):
    dcl, dcm = 0.3, -0.06
    q_r = reversal_dynamic_pressure(GJ, L, C, E, A, dcl, dcm, y1, y2)
    assert 0 < q_r < divergence_dynamic_pressure(GJ, L, C, E, A)
    assert aileron_lift(q_r, GJ, L, C, E, A, dcl, dcm, y1, y2) == pytest.approx(0.0, abs=1e-12)
    for q in (0.5 * q_r, 0.9 * q_r):
        assert aileron_lift(q, GJ, L, C, E, A, dcl, dcm, y1, y2) == pytest.approx(fd_aileron_lift(q, dcl, dcm, y1, y2), rel=1e-4)
    assert fd_aileron_lift(0.99 * q_r, dcl, dcm, y1, y2) > 0 > fd_aileron_lift(1.01 * q_r, dcl, dcm, y1, y2)


def test_reversal_depends_only_on_the_ratio_of_the_ailerons_coefficients_and_not_its_direction():
    down = reversal_dynamic_pressure(GJ, L, C, E, A, 0.3, -0.06, 1.2, 1.9)
    assert reversal_dynamic_pressure(GJ, L, C, E, A, 0.15, -0.03, 1.2, 1.9) == pytest.approx(down, rel=1e-12)
    assert reversal_dynamic_pressure(GJ, L, C, E, A, -0.3, 0.06, 1.2, 1.9) == pytest.approx(down, rel=1e-12)


def test_an_aileron_whose_moment_twists_the_nose_up_never_reverses_before_divergence():
    assert reversal_dynamic_pressure(GJ, L, C, E, A, 0.3, +0.01, 1.2, 1.9) == math.inf


def test_with_the_shear_center_at_the_aerodynamic_center_reversal_still_comes_from_the_ailerons_moment():
    q_r = reversal_dynamic_pressure(GJ, L, C, 0.0, A, 0.3, -0.06, 0.0, L)
    # Full span, e = 0: the twist is the aileron moment's alone, theta = -(q c^2 dcm / GJ)(y^2/2 - L y), and the lift is lost when
    # dcl L + a (q c^2 dcm / GJ) L^3 / 3 = 0.
    assert q_r == pytest.approx(3 * GJ * 0.3 / (A * C**2 * 0.06 * L**2), rel=1e-12)


def test_equivalent_airspeed_of_a_dynamic_pressure():
    assert equivalent_airspeed(0.5 * SEA_LEVEL_DENSITY * 70.0**2) == pytest.approx(70.0, rel=1e-15)
    assert equivalent_airspeed(math.inf) == math.inf


def test_the_wing_reports_its_divergence_and_reversal_against_the_dive_speed():
    result = run()
    a, section = result.aeroelastic, result.section
    e = section.shear_center_m - 0.25 * 0.45
    assert a.divergence_dynamic_pressure_Pa == pytest.approx(divergence_dynamic_pressure(section.GJ, 2.0, 0.45, e, 6.0), rel=1e-15)
    assert a.reversal_dynamic_pressure_Pa == pytest.approx(reversal_dynamic_pressure(section.GJ, 2.0, 0.45, e, 6.0, 0.3, -0.06, 1.2, 1.9), rel=1e-15)
    assert a.dive_speed_m_s == 70.0
    assert a.divergence_over_dive == pytest.approx(a.divergence_speed_m_s / 70.0)
    assert a.needs == ()
    report = wing_report(result, "SI", "m/s")["aeroelastic"]
    assert report["divergence_speed"] == pytest.approx(a.divergence_speed_m_s)
    assert report["divergence_never"] is False and report["reversal_never"] is False


def test_true_dive_speeds_are_read_at_the_altitude_where_they_are_fastest_in_equivalent_airspeed():
    result = run(**{"envelope.airspeed": "true"})
    assert result.aeroelastic.dive_speed_m_s == pytest.approx(70.0 * math.sqrt(density_ratio(0.0)))
    result = run(**{"envelope.airspeed": "true", "envelope.altitudes": [3000.0]})
    assert result.aeroelastic.dive_speed_m_s == pytest.approx(70.0 * math.sqrt(density_ratio(3000.0)))


def test_without_a_lift_slope_or_an_aileron_the_checks_say_what_they_need():
    a = run(**{"aerodynamics.lift_curve_slope": None}).aeroelastic
    assert a.divergence_speed_m_s is None and a.reversal_speed_m_s is None
    assert a.needs == ("the section's lift curve slope, for divergence and reversal",)
    a = run(**{"envelope.aileron": None}).aeroelastic
    assert a.divergence_speed_m_s is not None and a.reversal_speed_m_s is None
    assert a.needs == ("the aileron, for reversal",)


def test_a_wing_that_never_diverges_says_so():
    data = example(**{"aerodynamics.aerodynamic_center": 0.45})  # behind the shear center (about 0.38 of the chord)
    wing, envelope = wing_from_dict(data)
    result = analyze_wing(wing, envelope)
    assert result.aeroelastic.divergence_speed_m_s == math.inf
    assert wing_report(result, "SI", "m/s")["aeroelastic"]["divergence_never"] is True


def test_a_rib_layup_needs_a_rib_spacing_and_is_read_from_the_file():
    wing, _ = wing_from_dict(example())
    assert wing.rib is not None and wing.rib.half_stack_deg == (45.0, -45.0)
    with pytest.raises(ValueError, match="rib layup was given but no rib spacing"):
        wing_from_dict(example(**{"geometry.rib_spacing": None}))
