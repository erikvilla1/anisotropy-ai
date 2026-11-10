"""Tension of a resin-impregnated carbon or graphite fibre tow: the calculations of ASTM D4018-23 §12 and its Tables 1 and 2 (ADR-0074).

A tow is a strand, not a laminate. Its load-bearing area is the fibre's: the mass per unit length divided by the fibre density. The tensile
strength and the chord modulus are the measured forces over that area; the resin only holds the filaments together (§4.5). Nothing here
is a finite element model or laminate theory.

Every quantity is SI: masses in kilograms, lengths in metres, densities in kg/m^3, mass per unit length in kg/m, forces in newtons, stresses
and moduli in pascals, strains absolute (m/m). The standard states its equations in g, m, g/cm^3 and N and its strain limits in
microstrain; the caller converts where values enter and leave (ADR-0002).

D4018-23 Eq 5 multiplies by B = 1e-3 for a load in newtons to give GPa and lists the strains in microstrain. The two do not agree: with P in N,
rho_f in g/cm^3 and MUL in g/m, P rho_f / MUL is in MPa, and dividing by a strain difference then multiplying by 1e-3 gives GPa only when
the strains are absolute (0.005, not 5000). Here the strains are absolute and no factor is needed (our reading, recorded in ADR-0074).

Invalid input is refused, never defaulted (ADR-0003): a value that is not a finite positive number where the physics needs one, a strain
range that is empty, an impregnated strand lighter than its fibre.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# Table 1 and Table 2 of D4018-23, keyed by the product's typical strain at failure (absolute strain). A failure strain at or above the
# bound selects the row; the rows are tried from the highest bound down, so the last row (bound 0) takes every lower strain.
PRELOAD_LIMITS: tuple[tuple[float, float], ...] = ((12000e-6, 200e-6), (6000e-6, 100e-6), (0.0, 100e-6))  # (bound, maximum preload strain)
CHORD_LIMITS: tuple[tuple[float, tuple[float, float]], ...] = (  # (bound, (lower, upper) chord strains)
    (12000e-6, (1000e-6, 6000e-6)),
    (6000e-6, (1000e-6, 3000e-6)),
    (0.0, (500e-6, 1500e-6)),
)


def _positive(value: float, name: str) -> float:
    """A finite number greater than zero, or a refusal naming the quantity."""
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite number greater than zero; got {value!r}")
    return number


def _finite(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number; got {value!r}")
    return number


# --------------------------------------------------------------------------------------------- Eqs 1 to 3: the fibre and the strand


def mass_per_unit_length(mass: float, length: float) -> float:
    """D4018-23 Eq 1: the mass per unit length of the sized fibre, MUL = W1 / L, in kg/m from a specimen's mass (kg) and length (m)."""
    return _positive(mass, "the specimen's mass") / _positive(length, "the specimen's length")


def fibre_density(sized_density: float, correction: float = 0.0) -> float:
    """D4018-23 Eq 2: the fibre density from a sized fibre's, rho_f = rho_sf - k_c, in kg/m^3. The correction k_c for the sizing is the
    laboratory's (found from repeated tests of sized and desized fibre, §12.2.2); zero leaves the measured density as it is."""
    density = _positive(sized_density, "the sized fibre's density") - _finite(correction, "the sizing correction k_c")
    if density <= 0:
        raise ValueError(f"the sizing correction k_c ({correction!r}) leaves no positive fibre density from {sized_density!r}")
    return density


def resin_content(mul: float, mul_impregnated: float) -> float:
    """D4018-23 Eq 3: the resin content by weight, RC = 100 (1 - MUL / MUL_i), in percent, from the fibre's mass per unit length and the
    impregnated, consolidated strand's (any one unit, the same for both)."""
    fibre = _positive(mul, "the fibre's mass per unit length")
    strand = _positive(mul_impregnated, "the impregnated strand's mass per unit length")
    if strand <= fibre:
        raise ValueError(f"the impregnated strand's mass per unit length ({mul_impregnated!r}) must exceed the fibre's ({mul!r}): it carries the resin")
    return 100.0 * (1.0 - fibre / strand)


def fibre_area(mul: float, density: float) -> float:
    """The fibre's cross-sectional area, A = MUL / rho_f, in m^2: the area Eqs 4 and 5 divide the force by, and the area §11.3.6 sizes the
    preload with."""
    return _positive(mul, "the fibre's mass per unit length") / _positive(density, "the fibre density")


# --------------------------------------------------------------------------------------------- Eqs 4 and 5: strength and chord modulus


def tow_strength(force: float, density: float, mul: float) -> float:
    """D4018-23 Eq 4: the fibre's tensile strength from the maximum force, sigma = P rho_f / MUL, in Pa (P/A with A = MUL / rho_f)."""
    return _positive(force, "the maximum force") / fibre_area(mul, density)


def tow_chord_modulus(force_lower: float, force_upper: float, strain_lower: float, strain_upper: float, density: float, mul: float) -> float:
    """D4018-23 Eq 5 with absolute strains: E = (P_u - P_l) rho_f / ((eps_u - eps_l) MUL), in Pa, from the forces read at the lower and
    upper strain of the chord (§11.3.11). The strains are absolute (m/m); see the module's note on the standard's factor B."""
    lower, upper = _finite(strain_lower, "the chord's lower strain"), _finite(strain_upper, "the chord's upper strain")
    if lower < 0 or upper <= lower:
        raise ValueError(f"the chord's strains must satisfy 0 <= lower < upper; got {strain_lower!r} and {strain_upper!r}")
    p_lower, p_upper = _finite(force_lower, "the force at the lower strain"), _finite(force_upper, "the force at the upper strain")
    if p_lower < 0 or p_upper <= p_lower:
        raise ValueError(f"the force at the upper strain ({force_upper!r}) must exceed the force at the lower strain ({force_lower!r}), "
                         "both at least zero, for a tow in tension")
    return (p_upper - p_lower) / ((upper - lower) * fibre_area(mul, density))


# --------------------------------------------------------------------------------------------- Tables 1 and 2: by the typical failure strain


def _row(table, failure_strain: float):
    strain = _positive(failure_strain, "the product's typical strain at failure")
    return next(value for bound, value in table if strain >= bound)


def preload_strain(failure_strain: float) -> float:
    """D4018-23 Table 1: the largest preload, as a strain, for a product of this typical strain at failure (absolute strains)."""
    return _row(PRELOAD_LIMITS, failure_strain)


def chord_strains(failure_strain: float) -> tuple[float, float]:
    """D4018-23 Table 2: the lower and upper strain of the chord modulus for a product of this typical strain at failure (absolute)."""
    return _row(CHORD_LIMITS, failure_strain)


# --------------------------------------------------------------------------------------------- Eqs 6 to 8: a series of specimens


@dataclass(frozen=True)
class SampleStatistics:
    n: int
    mean: float
    standard_deviation: float  # s_(n-1), the sample standard deviation
    cv_percent: float  # 100 s_(n-1) / mean


def sample_statistics(values: Sequence[float]) -> SampleStatistics:
    """D4018-23 Eqs 6 to 8: the mean, the sample standard deviation s_(n-1) and the coefficient of variation in percent of a series.

    s_(n-1) is computed as sqrt(sum (x_i - mean)^2 / (n - 1)), which equals Eq 7's sqrt((sum x_i^2 - n mean^2) / (n - 1)) exactly in
    arithmetic and loses no digits to cancellation. A series needs two values for a deviation and a mean above zero for a coefficient.
    """
    series = [_finite(v, "a value of the series") for v in values]
    if len(series) < 2:
        raise ValueError(f"a series needs at least two values for its standard deviation; got {len(series)}")
    n = len(series)
    mean = math.fsum(series) / n
    if mean <= 0:
        raise ValueError(f"the series' mean ({mean!r}) must be greater than zero for a coefficient of variation")
    deviation = math.sqrt(math.fsum((x - mean) ** 2 for x in series) / (n - 1))
    return SampleStatistics(n, mean, deviation, 100.0 * deviation / mean)


# --------------------------------------------------------------------------------------------- planning loads (§11.3.6)


@dataclass(frozen=True)
class PlanningLoads:
    """The forces a test of this tow should see, from its area and a datasheet's modulus and strength (linear to failure). None where the
    datasheet value they need is not given."""

    area: float  # m^2
    preload_strain: float  # Table 1, absolute
    chord_strains: tuple[float, float]  # Table 2, absolute
    preload_force: float | None  # N: the largest preload, eps_pre E A
    force_lower: float | None  # N: the force expected at the chord's lower strain
    force_upper: float | None  # N: and at its upper strain
    failure_force: float | None  # N: sigma A, the force at the datasheet strength


def planning_loads(mul: float, density: float, failure_strain: float, modulus: float | None = None, strength: float | None = None) -> PlanningLoads:
    """The loads to plan a test with (§11.3.6: the preload is found from the expected modulus and the fibre's area): P = eps E A at the
    preload strain of Table 1 and the chord strains of Table 2, and P = sigma A at the datasheet strength. A datasheet value left out
    leaves the forces that need it out; nothing is assumed in its place."""
    area = fibre_area(mul, density)
    pre = preload_strain(failure_strain)
    lower, upper = chord_strains(failure_strain)
    e = None if modulus is None else _positive(modulus, "the datasheet modulus")
    s = None if strength is None else _positive(strength, "the datasheet strength")
    return PlanningLoads(area=area, preload_strain=pre, chord_strains=(lower, upper),
                         preload_force=None if e is None else pre * e * area,
                         force_lower=None if e is None else lower * e * area,
                         force_upper=None if e is None else upper * e * area,
                         failure_force=None if s is None else s * area)
