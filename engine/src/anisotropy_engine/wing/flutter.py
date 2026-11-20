"""A flutter estimate on the typical section: a wing strip that plunges and pitches, with Theodorsen's unsteady airload.

The strip has the wing's mass per unit span m, its center of mass a distance x_theta b aft of the elastic axis, its radius of
gyration r b about that axis, and two springs set by the wing's first bending and first torsion frequencies, omega_h and
omega_theta. b is the semichord and the elastic axis lies a b aft of mid-chord. With h positive down and theta nose up,

    m h'' + m b x_theta theta'' + k_h h = -L
    m b x_theta h'' + m b^2 r^2 theta'' + k_theta theta = M

and for harmonic motion at reduced frequency k = omega b / U, Theodorsen's lift and moment about the elastic axis are

    L = pi rho b^2 (h'' + U theta' - b a theta'') + 2 pi rho U b C(k) [h' + U theta + b (1/2 - a) theta']
    M = pi rho b^2 [b a h'' - U b (1/2 - a) theta' - b^2 (1/8 + a^2) theta''] + 2 pi rho U b^2 (a + 1/2) C(k) [h' + U theta + b (1/2 - a) theta']

The k method (the V-g method) adds a structural damping g to both springs, k (1 + i g), and for each reduced frequency solves for
Z = (omega_theta / omega)^2 (1 + i g): each root gives a frequency omega, a speed U = omega b / k and the damping g the strip
would need to hold that motion. Flutter is where a root's g rises through zero as the speed grows.

C(k) is R. T. Jones's two-term approximation of Theodorsen's function, within about 1.5 % of it (NACA Report 681, 1940).
Sources: Theodorsen, NACA Report 496 (1935); Bisplinghoff, Ashley and Halfman, Aeroelasticity (1955), chapters 5 and 9;
Hodges and Pierce, Introduction to Structural Dynamics and Aeroelasticity (2nd ed., 2011), chapter 5. The engine's working is
in engine/docs/theory.md, section 14.

An estimate only: two-dimensional air on one strip (a real wing's tip loses lift, which usually raises the flutter speed), the
first bending and first torsion modes alone, no compressibility, sweep or control surface, and only the mass the description
holds (no fuel, systems or balance weights, which can move the answer either way).
"""

import math
from dataclasses import dataclass

import numpy as np

REDUCED_FREQUENCIES = np.geomspace(4.0, 0.01, 1200)  # the sweep, high to low: speed rises along it


@dataclass(frozen=True)
class TypicalSection:
    """The strip the estimate flies, SI units."""

    semichord_m: float  # b
    elastic_axis: float  # a: the elastic axis aft of mid-chord, in semichords
    mass_offset: float  # x_theta: the center of mass aft of the elastic axis, in semichords
    radius_of_gyration: float  # r: about the elastic axis, in semichords
    mass_per_length_kg_m: float
    bending_frequency_Hz: float  # the wing's first bending mode
    torsion_frequency_Hz: float  # its first torsion mode

    def __post_init__(self) -> None:
        for name in ("semichord_m", "radius_of_gyration", "mass_per_length_kg_m", "bending_frequency_Hz", "torsion_frequency_Hz"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"The typical section's {name} must be positive, got {value}")
        if not -1 < self.elastic_axis < 1:
            raise ValueError("The elastic axis must lie on the chord: -1 < a < 1")


@dataclass(frozen=True)
class FlutterResult:
    density_kg_m3: float
    speed_m_s: float  # true airspeed at that density; infinity when no root goes unstable in the sweep
    frequency_Hz: float | None
    reduced_frequency: float | None
    mass_ratio: float  # mu = m / (pi rho b^2)
    speeds_m_s: np.ndarray  # (2, sweep) each root's speed along the sweep, NaN where it has none
    damping: np.ndarray  # (2, sweep) the damping g each root needs
    frequencies_Hz: np.ndarray  # (2, sweep)


def theodorsen(k: np.ndarray | float) -> np.ndarray | complex:
    """C(k), by R. T. Jones's approximation: 1 - 0.165 / (1 - 0.0455 i / k) - 0.335 / (1 - 0.3 i / k)."""
    k = np.asarray(k, dtype=float)
    value = 1 - 0.165 / (1 - 0.0455j / k) - 0.335 / (1 - 0.3j / k)
    return complex(value) if value.ndim == 0 else value


def airload(k: float, a: float) -> tuple[complex, complex, complex, complex]:
    """Theodorsen's lift and moment for harmonic motion, divided by pi rho b^3 omega^2 and pi rho b^4 omega^2, per unit h / b and
    per unit theta: (L_h, L_theta, M_h, M_theta)."""
    C = theodorsen(k)
    lift_h = -1 + 2j * C / k
    lift_theta = a + 1j / k + 2 * C / k**2 + 1j * C * (1 - 2 * a) / k
    moment_h = -a + 2j * (a + 0.5) * C / k
    moment_theta = (0.125 + a**2) - 1j * (0.5 - a) / k + 2 * (a + 0.5) * C / k**2 + 1j * (a + 0.5) * (1 - 2 * a) * C / k
    return lift_h, lift_theta, moment_h, moment_theta


def _roots(section: TypicalSection, mu: float, k: float) -> np.ndarray:
    a, x, r2 = section.elastic_axis, section.mass_offset, section.radius_of_gyration**2
    sigma2 = (section.bending_frequency_Hz / section.torsion_frequency_Hz) ** 2
    lift_h, lift_theta, moment_h, moment_theta = airload(k, a)
    A = np.array([[1 - lift_h / mu, x - lift_theta / mu], [x + moment_h / mu, r2 + moment_theta / mu]])
    return np.linalg.eigvals(np.diag([1 / sigma2, 1 / r2]) @ A)


def flutter_speed(section: TypicalSection, density_kg_m3: float, structural_damping: float = 0.0) -> FlutterResult:
    """The lowest speed at which a root of the k method needs more damping than `structural_damping`, at one air density."""
    if density_kg_m3 <= 0:
        raise ValueError("The air density must be positive")
    b = section.semichord_m
    mu = section.mass_per_length_kg_m / (math.pi * density_kg_m3 * b**2)
    omega_theta = 2 * math.pi * section.torsion_frequency_Hz
    n = REDUCED_FREQUENCIES.size
    speeds, damping, frequencies = (np.full((2, n), np.nan) for _ in range(3))
    previous = None
    for j, k in enumerate(REDUCED_FREQUENCIES):
        Z = _roots(section, mu, k)
        if previous is not None and abs(Z[0] - previous[1]) + abs(Z[1] - previous[0]) < abs(Z[0] - previous[0]) + abs(Z[1] - previous[1]):
            Z = Z[::-1]  # follow each root from one reduced frequency to the next
        previous = Z
        for i, z in enumerate(Z):
            if z.real > 0:
                omega = omega_theta / math.sqrt(z.real)
                speeds[i, j], damping[i, j], frequencies[i, j] = omega * b / k, z.imag / z.real, omega / (2 * math.pi)
    best = (math.inf, None, None)
    for i in range(2):
        g = damping[i] - structural_damping
        for j in range(1, n):
            if np.isfinite(g[j - 1]) and np.isfinite(g[j]) and g[j - 1] < 0 <= g[j]:
                t = -g[j - 1] / (g[j] - g[j - 1])
                speed = speeds[i, j - 1] + t * (speeds[i, j] - speeds[i, j - 1])
                if speed < best[0]:
                    k = REDUCED_FREQUENCIES[j - 1] + t * (REDUCED_FREQUENCIES[j] - REDUCED_FREQUENCIES[j - 1])
                    best = (float(speed), float(frequencies[i, j - 1] + t * (frequencies[i, j] - frequencies[i, j - 1])), float(k))
                break
    return FlutterResult(density_kg_m3, best[0], best[1], best[2], mu, speeds, damping, frequencies)
