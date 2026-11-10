"""The outline of a dumbbell (dog-bone) coupon (ADR-0075): its half-width at every distance from mid-length.

The outline is symmetric about both axes. From mid-length outwards it is a straight narrow section of half-width a = narrow_width / 2 over
half its length l = narrow_length / 2, then a fillet of radius R tangent to the narrow section at s = l, then the full half-width
b = width / 2 to the end. With an outer radius RO the fillet meets a second arc, of radius RO and tangent to the full width, at the point
where the two arcs are tangent to each other (a reverse curve, the outline of ASTM D638 Type IV); without one, the fillet runs until it
reaches the full width and meets it at a corner, as D638 draws Types I, II, III and V.

Every function here is plain geometry in whatever length unit it is given; `s` is the distance from mid-length along the coupon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


class OutlineError(ValueError):
    """The sizes do not make a dog-bone: the fillet cannot reach the full width, or the ends leave no full-width part."""


@dataclass(frozen=True)
class Outline:
    a: float  # half the narrow width
    b: float  # half the overall width
    l: float  # half the narrow length
    R: float  # the fillet radius, tangent to the narrow section
    RO: float | None  # the outer radius, tangent to the full width (Type IV); None when the fillet meets the full width at a corner
    s_tangent: float  # where the fillet ends: the corner at the full width, or the tangent point of the two arcs
    s_full: float  # where the full width begins
    half_length: float

    def half_width(self, s: float) -> float:
        """The half-width at a distance `s` from mid-length (either side)."""
        s = abs(s)
        if s <= self.l:
            return self.a
        if s <= self.s_tangent:
            return self.a + self.R - math.sqrt(max(self.R ** 2 - (s - self.l) ** 2, 0.0))
        if s < self.s_full and self.RO is not None:
            return self.b - self.RO + math.sqrt(max(self.RO ** 2 - (s - self.s_full) ** 2, 0.0))
        return self.b

    def width_at(self, y: float) -> float:
        """The full width at a coordinate `y` measured from one end, the coupon's length axis (0 to the length)."""
        return 2.0 * self.half_width(y - self.half_length)

    def lines(self) -> dict[str, float]:
        """The y of every place the outline changes, from one end (0 to the length): where the narrow section ends and the fillet starts,
        where the two arcs meet (Type IV), and where the full width begins, on both sides."""
        c = self.half_length
        found = {"Narrow-Bottom": c - self.l, "Narrow-Top": c + self.l}
        if self.RO is not None:
            found |= {"Arcs-Bottom": c - self.s_tangent, "Arcs-Top": c + self.s_tangent}
        return found | {"Full-Bottom": c - self.s_full, "Full-Top": c + self.s_full}


def dogbone_outline(narrow_width: float, narrow_length: float, radius: float, outer_radius: float | None, width: float, length: float) -> Outline:
    """The outline of a dog-bone of these sizes; refuses sizes that do not make one."""
    a, b, l, R = narrow_width / 2.0, width / 2.0, narrow_length / 2.0, radius
    if not narrow_width < width:
        raise OutlineError(f"narrow_width ({narrow_width:g}) must be less than the overall width ({width:g})")
    if not narrow_length < length:
        raise OutlineError(f"narrow_length ({narrow_length:g}) must be less than the overall length ({length:g})")
    step = b - a  # how far each side steps out from the narrow section to the full width
    if outer_radius is None:
        if step > R:
            raise OutlineError(f"a fillet of radius {R:g} cannot step the half-width out by {step:g}: give a radius of at least {step:g}, "
                               "or an outer_radius")
        s_tangent = s_full = l + math.sqrt(R ** 2 - (R - step) ** 2)
        RO = None
    else:
        RO = outer_radius
        dx = a + R - (b - RO)  # across, from the outer arc's centre to the fillet's centre
        if dx <= 0:
            raise OutlineError(f"the fillet (radius {R:g}) and the outer arc (radius {RO:g}) do not meet: their radii are too small for the step "
                               f"of {step:g}")
        dy = math.sqrt((R + RO) ** 2 - dx ** 2)
        s_full = l + dy  # the outer arc's centre, level with where it touches the full width
        s_tangent = l + dy * R / (R + RO)  # the tangent point lies on the line between the centres, R from the fillet's centre
    if not s_full < length / 2.0:
        raise OutlineError(f"the fillet reaches the full width {s_full:g} from mid-length, beyond the end at {length / 2.0:g}: the coupon must be "
                           f"longer than {2.0 * s_full:g}")
    return Outline(a=a, b=b, l=l, R=R, RO=RO, s_tangent=s_tangent, s_full=s_full, half_length=length / 2.0)
