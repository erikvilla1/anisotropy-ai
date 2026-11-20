"""The flutter estimate on the typical section (wing/flutter.py, ADR-0117): Theodorsen's function, the k method's answer
against a p-k solution with the exact function (in fea/tests/test_wing_model.py, where SciPy is), and how it moves."""

import math

import pytest

from anisotropy_engine.wing.flutter import TypicalSection, airload, flutter_speed, theodorsen

# Theodorsen's function from its Hankel functions, H1(2) / (H1(2) + i H0(2)), to four places (computed with
# scipy.special.hankel2; fea/tests/test_wing_model.py computes it live and compares).
EXACT = {0.1: 0.8319 - 0.1723j, 0.3: 0.6650 - 0.1793j, 1.0: 0.5394 - 0.1003j}


def section(**changes) -> TypicalSection:
    """A strip often used to show flutter: a = -1/5, x_theta = 1/10, r^2 = 6/25, omega_h / omega_theta = 2/5, mu = 20 at rho = 1."""
    values = dict(semichord_m=1.0, elastic_axis=-0.2, mass_offset=0.1, radius_of_gyration=math.sqrt(6 / 25),
                  mass_per_length_kg_m=20 * math.pi, bending_frequency_Hz=0.4 / (2 * math.pi), torsion_frequency_Hz=1 / (2 * math.pi))
    values.update(changes)
    return TypicalSection(**values)


def test_jones_approximation_is_within_two_hundredths_of_theodorsens_function():
    assert theodorsen(1e6) == pytest.approx(0.5, abs=1e-6)
    assert theodorsen(1e-6) == pytest.approx(1.0, abs=1e-4)
    for k, exact in EXACT.items():
        assert abs(theodorsen(k) - exact) < 0.02


def test_the_airload_has_the_steady_lift_slope_of_two_pi_when_the_strip_barely_moves():
    k = 1e-6
    lift_h, lift_theta, moment_h, moment_theta = airload(k, -0.2)
    # Divided by pi rho b^3 omega^2, the steady part 2 pi rho U^2 b theta is 2 theta / k^2 (C = 1).
    assert (lift_theta * k**2).real == pytest.approx(2.0, rel=1e-3)
    assert (moment_theta * k**2).real == pytest.approx(2 * (0.5 - 0.2), rel=1e-3)  # the lift acts at the quarter chord, (1/2 + a) b ahead


def test_the_strip_flutters_where_its_damping_crosses_zero():
    result = flutter_speed(section(), 1.0)
    assert result.mass_ratio == pytest.approx(20.0)
    assert result.speed_m_s == pytest.approx(2.1704, rel=1e-3)  # U / (b omega_theta); 2.1839 with the exact function (fea test)
    assert result.frequency_Hz * 2 * math.pi == pytest.approx(0.644, rel=0.01)  # between the two natural frequencies
    assert 0.2 < result.reduced_frequency < 0.4


def test_mass_ahead_of_the_axis_and_heavier_strips_fly_faster_before_flutter():
    base = flutter_speed(section(), 1.0).speed_m_s
    assert flutter_speed(section(mass_offset=0.0), 1.0).speed_m_s > base
    assert flutter_speed(section(mass_offset=-0.1), 1.0).speed_m_s > flutter_speed(section(mass_offset=0.0), 1.0).speed_m_s
    assert flutter_speed(section(mass_per_length_kg_m=40 * math.pi), 1.0).speed_m_s > base
    assert flutter_speed(section(), 0.5).speed_m_s > base  # thinner air: the same strip flutters at a higher true airspeed


def test_a_strip_that_is_not_a_strip_is_refused():
    with pytest.raises(ValueError, match="elastic axis"):
        section(elastic_axis=1.2)
    with pytest.raises(ValueError, match="torsion_frequency_Hz"):
        section(torsion_frequency_Hz=0.0)
    with pytest.raises(ValueError, match="density"):
        flutter_speed(section(), 0.0)
