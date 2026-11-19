"""Airfoil outlines: the NACA four-digit series from its formula, or coordinates the engineer supplies.

Coordinates are fractions of the chord: x from the leading edge along the chord line, z up from
it. The wing calculation needs only the height of the upper and lower surface at a chord
position, to place the spars and the skins.

The NACA four-digit series (Jacobs, Ward and Pinkerton, NACA Report 460, 1933; Abbott and von
Doenhoff, Theory of Wing Sections, 1959, Section 6.4): digits m p tt give the largest camber m/100
at p/10 of the chord and a thickness of tt/100. The thickness is laid off at right angles to
the camber line, with the open trailing edge of the original series.
"""

import math
import re

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

Point = tuple[float, float]


def _naca_thickness(x: float, t: float) -> float:
    """Half thickness y_t at chord position x for a thickness ratio t."""
    return 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1015 * x**4)


def _naca_camber(x: float, m: float, p: float) -> tuple[float, float]:
    """Camber line height y_c and its slope at chord position x."""
    if m == 0:
        return 0.0, 0.0
    if x < p:
        return m / p**2 * (2 * p * x - x**2), 2 * m / p**2 * (p - x)
    return m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2), 2 * m / (1 - p) ** 2 * (p - x)


class Airfoil(BaseModel):
    """An outline by name (`naca`, four digits) or by points on each surface, leading edge first."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    name: str
    naca: str | None = None
    upper: tuple[Point, ...] = ()
    lower: tuple[Point, ...] = ()

    @model_validator(mode="after")
    def _one_definition(self) -> "Airfoil":
        if self.naca is not None:
            if self.upper or self.lower:
                raise ValueError("Give the NACA digits or the surface points, not both")
            if not re.fullmatch(r"\d{4}", self.naca) or self.naca[2:] == "00":
                raise ValueError(f"A NACA four-digit airfoil is four digits with a thickness, got {self.naca!r}")
            if (self.naca[0] == "0") != (self.naca[1] == "0"):
                raise ValueError(f"NACA {self.naca}: the camber and its position are both zero or both not")
            return self
        for label, points in (("upper", self.upper), ("lower", self.lower)):
            if len(points) < 2:
                raise ValueError(f"The {label} surface needs at least two points")
            x = [point[0] for point in points]
            if any(b <= a for a, b in zip(x, x[1:])):
                raise ValueError(f"The {label} surface's x must increase from the leading edge to the trailing edge")
        return self

    def _naca_surface(self, x: float, side: int) -> float:
        """Height of the upper (side +1) or lower (-1) surface at chord position x: the point of the camber line whose
        normal passes through x, found by repeating x_p = x + side * y_t sin(theta), which closes in a few steps because
        the thickness and the camber slope are small."""
        m, p, t = int(self.naca[0]) / 100, int(self.naca[1]) / 10, int(self.naca[2:]) / 100
        xp = x
        for _ in range(60):
            _, slope = _naca_camber(xp, m, p)
            previous, xp = xp, min(max(x + side * _naca_thickness(xp, t) * math.sin(math.atan(slope)), 0.0), 1.0)
            if xp == previous:  # settled: the next step would give the same point
                break
        yc, slope = _naca_camber(xp, m, p)
        return yc + side * _naca_thickness(xp, t) * math.cos(math.atan(slope))

    def surface_heights(self, x_over_c: float) -> tuple[float, float]:
        """(upper, lower) surface heights at a chord position, as fractions of the chord."""
        if self.naca is not None:
            if not 0 <= x_over_c <= 1:
                raise ValueError(f"Chord position must be between 0 and 1, got {x_over_c}")
            return self._naca_surface(x_over_c, 1), self._naca_surface(x_over_c, -1)
        heights = []
        for label, points in (("upper", self.upper), ("lower", self.lower)):
            x, z = np.array(points).T
            if not x[0] <= x_over_c <= x[-1]:
                raise ValueError(f"Chord position {x_over_c} is outside the {label} surface's points ({x[0]} to {x[-1]})")
            heights.append(float(np.interp(x_over_c, x, z)))
        return heights[0], heights[1]


def naca4(digits: str) -> Airfoil:
    """The NACA four-digit airfoil of these digits, for example "2412"."""
    return Airfoil(name=f"NACA {digits}", naca=digits)
