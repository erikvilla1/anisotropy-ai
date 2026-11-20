"""Flight load cases and the loads along the span of a straight wing.

The case set is the usual one for a light airplane's wing (14 CFR Part 23 as it stood before
Amendment 23-64: 23.333 flight envelope, 23.337 maneuvering load factors, 23.341 gust load
factors, 23.349 rolling conditions): level flight at five speeds, the four corners of the
maneuver envelope, four gusts and four rolling cases, each at every altitude of the envelope.

Along the span the lift follows Schrenk's approximation (Schrenk, NACA TM 948, 1940): the mean
of a load in proportion to the chord and an elliptical load of the same total. The wing is
straight with a constant chord, so the first part is uniform. An aileron adds a change of
section lift and moment coefficient over its span; roll acceleration, the change of angle of
attack in the roll and the wing's elastic twist are not modeled. The wing's own weight, which
relieves the bending, is not subtracted. Shear, bending moment and torque are the exact
integrals of those running loads, so they do not depend on the number of stations.
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .atmosphere import SEA_LEVEL_DENSITY, STANDARD_GRAVITY, air_density, density_ratio
from .description import FlightEnvelope, GustLoadFactors, GustSpeeds

AileronState = Literal["none", "down", "up"]
Group = Literal["level", "maneuver", "gust", "roll"]

# number, label, group, the speed it flies at, how its load factor is found, the aileron
CASE_TABLE: tuple[tuple[int, str, Group, str, str, AileronState], ...] = (
    (1, "Stall, flaps extended", "level", "stall_flaps", "one", "none"),
    (2, "Stall, flaps stowed", "level", "stall_clean", "one", "none"),
    (3, "Cruise", "level", "cruise", "one", "none"),
    (4, "Dive", "level", "dive", "one", "none"),
    (5, "Flutter speed", "level", "flutter", "one", "none"),
    (6, "Positive high angle of attack", "maneuver", "positive_maneuver", "positive", "none"),
    (7, "Positive low angle of attack", "maneuver", "dive", "positive", "none"),
    (8, "Negative high angle of attack", "maneuver", "negative_maneuver", "negative", "none"),
    (9, "Negative low angle of attack", "maneuver", "dive", "negative", "none"),
    (10, "Gust at cruise, up", "gust", "cruise", "cruise_positive", "none"),
    (11, "Gust at cruise, down", "gust", "cruise", "cruise_negative", "none"),
    (12, "Gust at dive, up", "gust", "dive", "dive_positive", "none"),
    (13, "Gust at dive, down", "gust", "dive", "dive_negative", "none"),
    (14, "Roll at cruise, aileron down", "roll", "cruise", "one", "down"),
    (15, "Roll at cruise, aileron up", "roll", "cruise", "one", "up"),
    (16, "Roll in a pull-up, aileron down", "roll", "positive_maneuver", "roll_pull_up", "down"),
    (17, "Roll in a pull-up, aileron up", "roll", "positive_maneuver", "roll_pull_up", "up"),
)
SPEED_NAMES = {"stall_flaps": "stall speed with flaps extended", "stall_clean": "stall speed with flaps stowed",
               "cruise": "cruise speed", "dive": "dive speed", "flutter": "flutter speed",
               "positive_maneuver": "speed of the positive maneuver corner",
               "negative_maneuver": "speed of the negative maneuver corner"}


@dataclass(frozen=True)
class LoadCase:
    """One flight condition for one side of the wing, in SI units."""

    number: int
    label: str
    group: Group
    altitude_m: float
    speed_m_s: float  # of the envelope's kind, equivalent or true
    load_factor: float
    aileron: AileronState
    dynamic_pressure_Pa: float


@dataclass(frozen=True)
class CaseNotRun:
    """A case of the set that the envelope cannot state yet, and what it needs."""

    number: int
    label: str
    altitude_m: float
    needs: str


def dynamic_pressure(speed_m_s: float, altitude_m: float, airspeed: str) -> float:
    """q = rho V^2 / 2 for a true airspeed at altitude, rho_0 V^2 / 2 for an equivalent airspeed at any altitude."""
    rho = SEA_LEVEL_DENSITY if airspeed == "equivalent" else air_density(altitude_m)
    return 0.5 * rho * speed_m_s**2


def gust_load_factor_increment(gust: GustSpeeds, gust_speed_m_s: float, speed_m_s: float, altitude_m: float, airspeed: str,
                               gross_weight_N: float, mean_chord_m: float) -> float:
    """The change of load factor in a gust, 14 CFR 23.341(c): K_g rho_0 U_de V_e a / (2 W/S), with the gust alleviation
    factor K_g = 0.88 mu / (5.3 + mu) and the mass ratio mu = 2 (W/S) / (rho c a g). The regulation prints the same with
    V in knots, U_de in ft/s and W/S in lb/ft^2 as K_g U_de V a / (498 W/S)."""
    wing_loading = gross_weight_N / gust.wing_area_m2
    slope = gust.lift_curve_slope_per_rad
    mass_ratio = 2 * wing_loading / (air_density(altitude_m) * mean_chord_m * slope * STANDARD_GRAVITY)
    alleviation = 0.88 * mass_ratio / (5.3 + mass_ratio)
    equivalent_speed = speed_m_s if airspeed == "equivalent" else speed_m_s * math.sqrt(density_ratio(altitude_m))
    return alleviation * SEA_LEVEL_DENSITY * gust_speed_m_s * equivalent_speed * slope / (2 * wing_loading)


def _load_factor(rule: str, envelope: FlightEnvelope, speed: float, altitude: float, mean_chord_m: float) -> float | None:
    if rule == "one":
        return 1.0
    if rule == "positive":
        return envelope.positive_load_factor
    if rule == "negative":
        return envelope.negative_load_factor
    if rule == "roll_pull_up":
        return envelope.aileron.roll_pull_up_fraction * envelope.positive_load_factor if envelope.aileron else None
    gust = envelope.gust
    if gust is None:
        return None
    if isinstance(gust, GustLoadFactors):
        return getattr(gust, rule)
    gust_speed = gust.cruise_gust_speed_m_s if rule.startswith("cruise") else gust.dive_gust_speed_m_s
    increment = gust_load_factor_increment(gust, gust_speed, speed, altitude, envelope.airspeed, envelope.gross_weight_N, mean_chord_m)
    return 1 + increment if rule.endswith("positive") else 1 - increment


def flight_cases(envelope: FlightEnvelope, mean_chord_m: float) -> tuple[list[LoadCase], list[CaseNotRun]]:
    """Every case of the set at every altitude: those the envelope states, and those it cannot with what each needs."""
    cases, not_run = [], []
    for altitude in envelope.altitudes_m:
        for number, label, group, speed_field, rule, aileron in CASE_TABLE:
            needs = []
            speed = getattr(envelope.speeds, speed_field)
            if speed is None:
                needs.append(f"the {SPEED_NAMES[speed_field]}")
            if group == "gust" and envelope.gust is None:
                needs.append("the gust load factors or the gust speeds")
            if group == "roll" and envelope.aileron is None:
                needs.append("the aileron")
            if needs:
                not_run.append(CaseNotRun(number, label, altitude, " and ".join(needs)))
                continue
            cases.append(LoadCase(number, label, group, altitude, speed, _load_factor(rule, envelope, speed, altitude, mean_chord_m),
                                  aileron, dynamic_pressure(speed, altitude, envelope.airspeed)))
    return cases, not_run


@dataclass(frozen=True)
class SpanLoads:
    """Loads at the stations of every case: arrays of shape (cases, stations), SI units."""

    y: np.ndarray  # stations from the root, m, shape (stations,)
    running_lift: np.ndarray  # N/m, up positive
    shear: np.ndarray  # N, the lift outboard of the station
    moment: np.ndarray  # N*m, positive when the tip bends up
    torque: np.ndarray  # N*m about the shear center, nose up positive


def span_loads(y: np.ndarray, half_span_m: float, chord_m: float, cases: list[LoadCase], envelope: FlightEnvelope,
               torque_arm_m: float, pitching_moment_coefficient: float) -> SpanLoads:
    """Running lift, shear, bending moment and torque of every case at the stations y.

    `torque_arm_m` is the distance from the aerodynamic center back to the shear center: lift ahead of the shear center
    twists the nose up. The airfoil's moment q c^2 c_m acts on every unit of span, and the aileron's change of it over
    the aileron's span.
    """
    L, c = half_span_m, chord_m
    eta = y / L
    root = np.sqrt(np.clip(1 - eta**2, 0, None))
    n = np.array([case.load_factor for case in cases])[:, None]
    q = np.array([case.dynamic_pressure_Pa for case in cases])[:, None]
    half_lift = n * envelope.gross_weight_N / 2  # the lift of one side
    peak = 4 * half_lift / (math.pi * L)  # the elliptical load at the root
    lift = 0.5 * (peak * root + half_lift / L)
    shear = 0.5 * (peak * L / 2 * (math.pi / 2 - np.arcsin(eta) - eta * root) + half_lift * (1 - eta))
    moment = 0.5 * (peak * L**2 / 2 * (eta * np.arcsin(eta) - math.pi / 2 * eta + root - root**3 / 3) + half_lift * L * (1 - eta) ** 2 / 2)
    torque_per_span = np.broadcast_to(q * c**2 * pitching_moment_coefficient, shear.shape)
    torque = torque_per_span * (L - y)

    aileron = envelope.aileron
    if aileron is not None and any(case.aileron != "none" for case in cases):
        if aileron.span_end_m > L:
            raise ValueError("The aileron ends outboard of the wing tip")
        y1, y2 = aileron.span_start_m, aileron.span_end_m
        delta_cl = np.array([{"none": 0.0, "down": aileron.down_delta_cl, "up": aileron.up_delta_cl}[case.aileron] for case in cases])[:, None]
        delta_cm = np.array([{"none": 0.0, "down": aileron.down_delta_cm, "up": aileron.up_delta_cm}[case.aileron] for case in cases])[:, None]
        extra = q * c * delta_cl  # N/m over the aileron's span
        inside = np.clip(y, y1, y2)
        lift = lift + extra * ((y >= y1) & (y <= y2))
        shear = shear + extra * (y2 - inside)
        moment = moment + extra / 2 * np.where(y < y2, (y2 - y) ** 2 - (inside - y) ** 2, 0.0)
        torque = torque + q * c**2 * delta_cm * (y2 - inside)
    torque = torque + torque_arm_m * shear
    return SpanLoads(y=y, running_lift=lift, shear=shear, moment=moment, torque=torque)
