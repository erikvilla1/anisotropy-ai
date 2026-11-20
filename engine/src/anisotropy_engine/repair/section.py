"""The slice through the middle of a stepped patch repair, as rectangles (ADR-0131).

The slice is cut along the load through the repair's middle, and one half of it is described: r from the middle outward
(0 to half the panel's length) and z up from the laminate's bottom face. Every part is a rectangle there, and because the
repair is round, every rectangle of the repair itself is also a ring or a disc in the panel.

How the parts sit, with t the ply thickness, g the thickness of one step's plies, eta the bondline, h the laminate's
thickness and R_j the radius at which step j is cut (step 1 at the top):

- a laminate ply runs from its step's cut radius outward (from the middle when no step cuts it);
- the adhesive lines the cavity: on each ledge (z from h - j g, eta thick, out to R_j), up each cut face (eta thick, inside
  R_j), over the floor of a cavity that does not go through, and, under cover plies, over the ring of laminate they reach;
- patch group j fills step j inside the adhesive: out to R_j - eta, and raised by eta, because it sits on the bondline. The
  top patch plies therefore stand eta proud of the laminate's top face, and cover plies lie flat over them and over the
  adhesive on the laminate;
- a cut through every ply has nothing under its deepest patch group: the space of one bondline below it is left empty.

`regions` lists the rectangles from these rules; `region_at` answers the same question for one point by a different route
(first the level, then the radius), so that one can check the other, and a mesh can ask it cell by cell.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .description import Repair, RepairError

KINDS = ("parent", "adhesive", "patch", "cover")


@dataclass(frozen=True)
class Region:
    """One rectangle of the half slice: what it is, where it is (m), and for a ply its angle from the load's direction.
    `ply` counts the laminate's plies from the bottom face, the patch's from its deepest and the cover's from its lowest;
    `step` is the step a patch ply fills or a laminate ply is cut by, or the ledge an adhesive rectangle lies on."""

    kind: str
    name: str
    r0: float
    r1: float
    z0: float
    z1: float
    angle_deg: float | None = None
    ply: int | None = None
    step: int | None = None
    round: bool = True  # a ring or a disc about the repair's middle; a laminate ply is the panel with a round hole instead

    @property
    def area(self) -> float:
        """The rectangle's area in the slice, m^2."""
        return (self.r1 - self.r0) * (self.z1 - self.z0)

    @property
    def revolved_volume(self) -> float:
        """The volume of the ring this rectangle sweeps about the repair's middle, m^3."""
        return math.pi * (self.r1**2 - self.r0**2) * (self.z1 - self.z0)


def _angle_name(angle: float) -> str:
    return f"{angle:g}°"


def regions(repair: Repair) -> tuple[Region, ...]:
    """Every rectangle of the half slice, none overlapping: the laminate's plies from the bottom, the adhesive from the
    floor up, the patch plies from the deepest, and the cover plies."""
    t, g, eta, h = repair.ply_thickness_m, repair.group_thickness_m, repair.adhesive.thickness_m, repair.thickness_m
    edge, n = repair.panel_length_m / 2, repair.steps
    radius = repair.cut_radius_m
    out: list[Region] = []
    for ply, angle in enumerate(repair.parent_angles, 1):
        step = repair.parent_ply_step(ply)
        out.append(Region("parent", f"Laminate ply {ply} ({_angle_name(angle)})", radius(step) if step else 0.0, edge, (ply - 1) * t, ply * t,
                          angle, ply, step, round=False))
    floor = h - n * g
    if not repair.through:
        out.append(Region("adhesive", "Adhesive on the floor", 0.0, radius(n), floor, floor + eta, step=n))
    for step in range(n, 0, -1):
        ledge = h - step * g  # the level this step's patch plies would rest on without a bondline
        low = ledge if repair.through and step == n else ledge + eta
        out.append(Region("adhesive", f"Adhesive on the cut face of step {step}", radius(step) - eta, radius(step), low, ledge + g, step=step))
        if step > 1:
            out.append(Region("adhesive", f"Adhesive on the ledge of step {step - 1}", radius(step) - eta, radius(step - 1), ledge + g,
                              ledge + g + eta, step=step - 1))
    if repair.cover_angles:
        out.append(Region("adhesive", "Adhesive under the cover plies", radius(1) - eta, repair.cover_radius_m, h, h + eta, step=0))
    number = 0
    for step in range(n, 0, -1):
        for k, angle in enumerate(repair.patch_group(step)):
            number += 1
            z0 = h - step * g + eta + k * t
            out.append(Region("patch", f"Patch ply {number} ({_angle_name(angle)})", 0.0, radius(step) - eta, z0, z0 + t, angle, number, step))
    for k, angle in enumerate(repair.cover_angles):
        z0 = h + eta + k * t
        out.append(Region("cover", f"Cover ply {k + 1} ({_angle_name(angle)})", 0.0, repair.cover_radius_m, z0, z0 + t, angle, k + 1))
    return tuple(out)


def region_at(repair: Repair, r: float, z: float) -> str | None:
    """What lies at a point of the half slice: "parent", "adhesive", "patch", "cover", or None where there is nothing.
    Worked level by level, not from the rectangles of `regions`. A point on a boundary may be given to either side."""
    t, g, eta, h = repair.ply_thickness_m, repair.group_thickness_m, repair.adhesive.thickness_m, repair.thickness_m
    if not 0 <= r <= repair.panel_length_m / 2 or z < 0:
        return None
    top = h + eta
    if z >= top:  # above the patch: cover plies, or nothing
        return "cover" if z < top + repair.cover_thickness_m and r < repair.cover_radius_m else None
    if z >= h:  # the one bondline's height above the laminate's top face
        if r < repair.patch_radius_m - eta:
            return "patch"
        return "adhesive" if repair.cover_angles and r < repair.cover_radius_m else None
    from_top = int((h - z) / t)  # how many whole plies lie above the point
    if from_top >= repair.plies_removed:
        return "parent"  # below the cavity
    step = from_top // repair.plies_per_step + 1
    if r >= repair.cut_radius_m(step):
        return "parent"
    # inside the cavity at this level: the patch group whose raised layer holds z, when r is inside its edge
    raised = h + eta - z  # measured down from the patch's proud top
    group = int(raised / g) + 1
    if group <= repair.steps and r < repair.cut_radius_m(group) - eta:
        return "patch"
    if repair.through and z < eta and r < repair.cut_radius_m(repair.steps) - eta:
        return None  # under the deepest patch plies of a cut through every ply
    return "adhesive"


def areas(repair: Repair) -> dict[str, float]:
    """The area of each kind of part in the half slice, m^2."""
    total = dict.fromkeys(KINDS, 0.0)
    for region in regions(repair):
        total[region.kind] += region.area
    return total


def volumes(repair: Repair) -> dict[str, float]:
    """The volume of each kind of part in the whole panel, m^3: a part of the repair is its rectangle swept about the
    middle, and a laminate ply is the panel's rectangle less the disc its step cuts."""
    total = dict.fromkeys(KINDS, 0.0)
    panel = repair.panel_length_m * repair.panel_width_m
    for region in regions(repair):
        if region.round:
            total[region.kind] += region.revolved_volume
        else:
            total[region.kind] += (panel - math.pi * region.r0**2) * (region.z1 - region.z0)
    return total


def bond_lengths(repair: Repair) -> dict[str, float]:
    """The bondline's length in the half slice, m: along the ledges (where the load passes), up the cut faces, over the
    floor and under the cover plies."""
    eta, n = repair.adhesive.thickness_m, repair.steps
    return {
        "ledges": (n - 1) * repair.step_length_m,
        "cut_faces": n * repair.group_thickness_m - (n - 1 if repair.through else n) * eta,  # each face less the bondline at its foot
        "floor": 0.0 if repair.through else repair.cut_radius_m(n),
        "cover": repair.cover_overlap_m if repair.cover_angles else 0.0,
    }


def check_regions(repair: Repair, samples: int = 7) -> None:
    """Refuse a description whose rectangles disagree with `region_at`: every rectangle is probed on a grid of points
    inside it. This is the engine's own cross-check of the two routes; a failure is a fault of this module."""
    for region in regions(repair):
        for i in range(1, samples + 1):
            for j in range(1, samples + 1):
                r = region.r0 + (region.r1 - region.r0) * i / (samples + 1)
                z = region.z0 + (region.z1 - region.z0) * j / (samples + 1)
                found = region_at(repair, r, z)
                if found != region.kind:
                    raise RepairError(f"{region.name}: the point r = {r:g} m, z = {z:g} m is {found} by its level and {region.kind} by its rectangle")
