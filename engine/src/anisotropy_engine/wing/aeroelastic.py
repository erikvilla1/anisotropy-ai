"""Static aeroelastic checks of a straight, uniform wing: the divergence and the aileron reversal dynamic pressure.

Strip theory on a cantilever of constant torsion stiffness GJ and chord c, clamped at the root and free at the tip. Lift acts
at the aerodynamic center, a distance e ahead of the shear center (e > 0 when the aerodynamic center is forward), with the
section lift slope a. The elastic twist theta(y) (nose up positive) obeys

    GJ theta'' + q c e a theta = - (the moment of every other load about the shear center, per unit span)

with theta(0) = 0 and theta'(L) = 0. Divergence is the dynamic pressure at which the homogeneous equation has a solution:
lambda L = pi / 2 with lambda^2 = q c e a / GJ. Reversal is the dynamic pressure at which a deflected aileron adds no lift to
the wing: the lift it adds directly is cancelled by the lift lost to the nose-down twist its moment causes.

Sources: Bisplinghoff, Ashley and Halfman, Aeroelasticity (1955), chapter 8; Hodges and Pierce, Introduction to Structural
Dynamics and Aeroelasticity (2nd ed., 2011), chapter 5. The engine's working is in engine/docs/theory.md, section 13.
Not modeled: sweep, taper, the lift's spanwise drop at the tip (strip theory), compressibility, and flutter, which needs the
wing's mass and frequencies (the finite element model, step 3).
"""

import math
from dataclasses import dataclass

from .atmosphere import SEA_LEVEL_DENSITY

SERIES_LIMIT = 1e-6  # |lambda^2| L^2 below which the twist integral uses its two-term series


def divergence_dynamic_pressure(torsion_stiffness: float, half_span_m: float, chord_m: float, torque_arm_m: float,
                                lift_slope_per_rad: float) -> float:
    """q_D = (pi / 2L)^2 GJ / (c e a), infinity when the aerodynamic center is not ahead of the shear center (e <= 0).

    `torque_arm_m` is the distance from the aerodynamic center back to the shear center, e in the module's notation.
    """
    if torsion_stiffness <= 0 or half_span_m <= 0 or chord_m <= 0 or lift_slope_per_rad <= 0:
        raise ValueError("GJ, the half span, the chord and the lift slope must be positive")
    if torque_arm_m <= 0:
        return math.inf
    return (math.pi / (2 * half_span_m)) ** 2 * torsion_stiffness / (chord_m * torque_arm_m * lift_slope_per_rad)


def twist_influence(s: float, half_span_m: float, y1: float, y2: float) -> float:
    """The integral from y1 to y2 of psi, where psi'' + s psi = 1, psi(0) = 0, psi'(L) = 0; s is lambda^2 (either sign).

    psi is the twist of the wing under a unit uniform moment per unit span, divided by the moment and multiplied by GJ; the
    lift over the wing caused by a moment over [y1, y2] follows from it by the reciprocity of the torsion equation.
    """
    L = half_span_m
    if abs(s) * L**2 < SERIES_LIMIT:
        # psi = y^2/2 - L y + s (L y^3/6 - y^4/24 - L^3 y/3) + O(s^2)
        def antiderivative(y: float) -> float:
            return y**3 / 6 - L * y**2 / 2 + s * (L * y**4 / 24 - y**5 / 120 - L**3 * y**2 / 6)
        return antiderivative(y2) - antiderivative(y1)
    # psi = (1 - cos ky - tan kL sin ky) / s for s = k^2 > 0, and the same with cosh, sinh, tanh for s = -k^2 < 0. Its integral
    # is (y2 - y1 + g(y2) - g(y1)) / s, with -sin ky + tan kL cos ky = sin k(L - y) / cos kL, written so that nothing overflows.
    k = math.sqrt(abs(s))
    if s > 0:
        if math.cos(k * L) <= 0:
            raise ValueError("The dynamic pressure is at or beyond divergence")

        def g(y: float) -> float:
            return math.sin(k * (L - y)) / (k * math.cos(k * L))
    else:
        def g(y: float) -> float:  # sinh k(L - y) / (k cosh kL)
            return math.exp(-k * y) * -math.expm1(-2 * k * (L - y)) / (k * (1 + math.exp(-2 * k * L)))
    return (y2 - y1 + g(y2) - g(y1)) / s


def aileron_lift(q: float, torsion_stiffness: float, half_span_m: float, chord_m: float, torque_arm_m: float, lift_slope_per_rad: float,
                 delta_cl: float, delta_cm: float, y1: float, y2: float) -> float:
    """The lift the aileron adds to the flexible wing, divided by q c: delta_cl (y2 - y1) less the lift its twist removes.

    The aileron adds q c delta_cl per unit span at the aerodynamic center and q c^2 delta_cm about it over [y1, y2]; about the
    shear center that is a moment m = q c (e delta_cl + c delta_cm) per unit span. The twist it causes changes the lift by
    q c a theta, and the integral of theta is -(m / GJ) times twist_influence.
    """
    s = q * chord_m * torque_arm_m * lift_slope_per_rad / torsion_stiffness
    influence = twist_influence(s, half_span_m, y1, y2)
    moment_per_q = chord_m * (torque_arm_m * delta_cl + chord_m * delta_cm)
    return delta_cl * (y2 - y1) - lift_slope_per_rad * moment_per_q * q / torsion_stiffness * influence


def reversal_dynamic_pressure(torsion_stiffness: float, half_span_m: float, chord_m: float, torque_arm_m: float, lift_slope_per_rad: float,
                              delta_cl: float, delta_cm: float, y1: float, y2: float) -> float:
    """The lowest dynamic pressure at which the aileron adds no lift, or infinity when it never reverses below divergence.

    The aileron's coefficients may be those of any deflection: reversal depends only on their ratio.
    """
    if not 0 <= y1 < y2 <= half_span_m:
        raise ValueError("The aileron must lie between the root and the tip")
    if delta_cl == 0:
        raise ValueError("The aileron's lift coefficient change must not be zero")
    args = (torsion_stiffness, half_span_m, chord_m, torque_arm_m, lift_slope_per_rad, delta_cl, delta_cm, y1, y2)
    q_divergence = divergence_dynamic_pressure(torsion_stiffness, half_span_m, chord_m, torque_arm_m, lift_slope_per_rad)
    # Above zero the aileron's lift starts with the sign of delta_cl; search outward for the first change of sign.
    sign = math.copysign(1.0, delta_cl)
    reference = torsion_stiffness / (chord_m**2 * lift_slope_per_rad * half_span_m**2)  # the scale of q at which twist matters
    upper = q_divergence * (1 - 1e-9) if math.isfinite(q_divergence) else math.inf
    low, high = 0.0, min(reference, upper)
    for _ in range(200):
        if sign * aileron_lift(high, *args) <= 0:
            return _bisect(lambda q: sign * aileron_lift(q, *args), low, high)
        if high >= upper:
            return math.inf
        low, high = high, min(2 * high, upper)
    return math.inf


def _bisect(function, low: float, high: float) -> float:
    """The root of `function` between `low` (where it is positive) and `high` (where it is zero or negative), by bisection to
    the last bits of a double."""
    for _ in range(200):
        middle = (low + high) / 2
        if middle in (low, high):
            break
        if function(middle) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def equivalent_airspeed(dynamic_pressure_Pa: float) -> float:
    """The equivalent airspeed of a dynamic pressure, sqrt(2 q / rho0); infinity stays infinity."""
    return math.sqrt(2 * dynamic_pressure_Pa / SEA_LEVEL_DENSITY) if math.isfinite(dynamic_pressure_Pa) else math.inf


@dataclass(frozen=True)
class Aeroelastic:
    """The divergence and reversal dynamic pressures and equivalent airspeeds, each None with what it needs when it cannot run."""

    divergence_dynamic_pressure_Pa: float | None
    divergence_speed_m_s: float | None  # equivalent airspeed
    reversal_dynamic_pressure_Pa: float | None
    reversal_speed_m_s: float | None  # equivalent airspeed
    dive_speed_m_s: float | None  # equivalent airspeed of the envelope's dive speed (at its lowest altitude when it is true airspeed)
    needs: tuple[str, ...]  # what is missing for a check that did not run

    @property
    def divergence_over_dive(self) -> float | None:
        if self.divergence_speed_m_s is None or self.dive_speed_m_s is None:
            return None
        return self.divergence_speed_m_s / self.dive_speed_m_s

    @property
    def reversal_over_dive(self) -> float | None:
        if self.reversal_speed_m_s is None or self.dive_speed_m_s is None:
            return None
        return self.reversal_speed_m_s / self.dive_speed_m_s
