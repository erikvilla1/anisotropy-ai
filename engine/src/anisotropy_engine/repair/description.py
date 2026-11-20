"""A stepped patch repair of a flat laminate, described by a few numbers (ADR-0131).

A round piece of damage is cut out of a laminate from its top face in steps: the deepest step has the damage's diameter, and
every step above it is cut wider by the step length all round, so each leaves a ledge to bond to. The cavity is lined with
adhesive and filled with patch plies, one group of plies for each step, and cover plies may be laid over the patch and a ring
of the laminate around it.

    parent      the laminate: its ply material and its angles, bottom face first
    damage      the diameter of the deepest cut
    steps       how many, the length of each ledge, and how many plies each step removes (one unless said)
    patch       its ply material and its angles, deepest ply first; unless said, the material and the angles of the plies removed
    cover       plies over the patch, and how far they reach past the widest cut
    adhesive    its shear modulus, the thickness of the bondline, and its shear strength when the elastic limit is wanted
    panel       the length (along the load) and the width of the laminate drawn around the repair

Steps and groups are counted from the top face down: step 1 is the widest cut, and group 1 the patch plies that fill it. The
load runs along x, the repair's middle is at x = 0 and z is 0 at the bottom face. SI throughout: m, Pa.

What this description cannot state yet: a patch whose plies are thicker or thinner than the laminate's, a scarf (a taper with
no ledges), steps of different lengths, a repair that is not round, a curved laminate, and a backing under a cut that goes
through every ply.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..lamina import Lamina
from .step_lap import Adhesive


class RepairError(ValueError):
    """The numbers do not describe a repair this description can state; the message says which one and why."""


def _positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise RepairError(f"{name} must be a positive, finite number, got {value!r}")
    return float(value)


def _count(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RepairError(f"{name} must be a whole number, 1 or more, got {value!r}")
    return value


def _angles(values, name: str) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
        raise RepairError(f"{name} must be a list of ply angles in degrees")
    angles = tuple(values)
    for angle in angles:
        if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle) or not -90 <= angle <= 90:
            raise RepairError(f"{name}: a ply angle is a number from -90 to 90 degrees, got {angle!r}")
    return tuple(float(angle) for angle in angles)


@dataclass(frozen=True)
class RepairMaterial:
    """A ply material of a repair: its name, its in-plane constants and its cured ply thickness."""

    name: str
    lamina: Lamina
    ply_thickness_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise RepairError("A material needs a name")
        if not isinstance(self.lamina, Lamina):
            raise RepairError(f"Material {self.name!r} needs its ply constants (E1, E2, G12, nu12)")
        object.__setattr__(self, "ply_thickness_m", _positive(self.ply_thickness_m, f"The ply thickness of {self.name!r}"))


@dataclass(frozen=True)
class Repair:
    """A stepped patch repair. Angles are in degrees from x, the load's direction; a list of the laminate's or the patch's
    plies starts at the lowest ply."""

    parent_material: RepairMaterial
    parent_angles: tuple[float, ...]
    damage_diameter_m: float
    steps: int
    step_length_m: float
    adhesive: Adhesive
    panel_length_m: float
    panel_width_m: float
    plies_per_step: int = 1
    patch_material: RepairMaterial | None = None
    patch_angles: tuple[float, ...] | None = None
    cover_angles: tuple[float, ...] = field(default=())
    cover_overlap_m: float = 0.0

    def __post_init__(self) -> None:
        set_ = lambda name, value: object.__setattr__(self, name, value)  # noqa: E731
        if not isinstance(self.parent_material, RepairMaterial):
            raise RepairError("The laminate needs its ply material")
        set_("parent_angles", _angles(self.parent_angles, "The laminate's layup"))
        if not self.parent_angles:
            raise RepairError("The laminate needs at least one ply")
        set_("damage_diameter_m", _positive(self.damage_diameter_m, "The damage's diameter"))
        set_("steps", _count(self.steps, "The number of steps"))
        set_("plies_per_step", _count(self.plies_per_step, "The plies in a step"))
        set_("step_length_m", _positive(self.step_length_m, "The step length"))
        if not isinstance(self.adhesive, Adhesive):
            raise RepairError("The repair needs its adhesive")
        set_("panel_length_m", _positive(self.panel_length_m, "The panel's length"))
        set_("panel_width_m", _positive(self.panel_width_m, "The panel's width"))
        if self.plies_removed > len(self.parent_angles):
            raise RepairError(f"{self.steps} steps of {self.plies_per_step} plies remove {self.plies_removed} plies, and the laminate has "
                              f"{len(self.parent_angles)}")
        if self.patch_material is None:
            set_("patch_material", self.parent_material)
        elif not isinstance(self.patch_material, RepairMaterial):
            raise RepairError("The patch's material must be a ply material")
        if not math.isclose(self.patch_material.ply_thickness_m, self.parent_material.ply_thickness_m, rel_tol=1e-9):
            raise RepairError("The patch's plies must be as thick as the laminate's: each group of patch plies fills the step cut for it "
                              f"(patch {self.patch_material.ply_thickness_m:g} m, laminate {self.parent_material.ply_thickness_m:g} m)")
        removed = self.parent_angles[len(self.parent_angles) - self.plies_removed:]
        set_("patch_angles", removed if self.patch_angles is None else _angles(self.patch_angles, "The patch's layup"))
        if len(self.patch_angles) != self.plies_removed:
            raise RepairError(f"The patch needs {self.plies_removed} plies, one for each ply removed, and {len(self.patch_angles)} are listed")
        set_("cover_angles", _angles(self.cover_angles, "The cover plies"))
        if self.cover_angles:
            set_("cover_overlap_m", _positive(self.cover_overlap_m, "The cover plies' overlap"))
        elif self.cover_overlap_m not in (0, 0.0):
            raise RepairError("An overlap is given for cover plies, and no cover ply is listed")
        else:
            set_("cover_overlap_m", 0.0)
        bondline = self.adhesive.thickness_m
        if bondline >= self.group_thickness_m:
            raise RepairError(f"The bondline ({bondline:g} m) must be thinner than the plies of one step ({self.group_thickness_m:g} m)")
        if bondline >= self.step_length_m or bondline >= self.damage_diameter_m / 2:
            raise RepairError("The bondline must be thinner than a step is long and than the damage's radius")
        if self.through and self.steps == 1 and not self.cover_angles:
            raise RepairError("One step through every ply leaves no ledge to bond to: give more steps, or cover plies")
        reach = 2 * self.cover_radius_m
        if reach >= min(self.panel_length_m, self.panel_width_m):
            raise RepairError(f"The repair is {reach:g} m across, so the panel must be longer and wider than that "
                              f"(it is {self.panel_length_m:g} m by {self.panel_width_m:g} m)")

    # ------------------------------------------------------------------------------------------------------- sizes
    @property
    def plies(self) -> int:
        return len(self.parent_angles)

    @property
    def ply_thickness_m(self) -> float:
        return self.parent_material.ply_thickness_m

    @property
    def thickness_m(self) -> float:
        """The laminate's thickness."""
        return self.plies * self.ply_thickness_m

    @property
    def plies_removed(self) -> int:
        return self.steps * self.plies_per_step

    @property
    def group_thickness_m(self) -> float:
        """The height of one step: the thickness of the plies it removes, and of the patch plies that fill it."""
        return self.plies_per_step * self.ply_thickness_m

    @property
    def through(self) -> bool:
        """Every ply is cut, so the deepest step is a hole through the laminate."""
        return self.plies_removed == self.plies

    @property
    def depth_m(self) -> float:
        """How deep the cavity is, from the top face."""
        return self.steps * self.group_thickness_m

    def cut_radius_m(self, step: int) -> float:
        """The radius at which step `step` (1 at the top) is cut: the damage's radius for the deepest, one step length more for
        each step above it."""
        if not 1 <= step <= self.steps:
            raise RepairError(f"The repair has steps 1 to {self.steps}, not {step}")
        return self.damage_diameter_m / 2 + (self.steps - step) * self.step_length_m

    @property
    def patch_radius_m(self) -> float:
        """The radius of the widest cut, at the top face."""
        return self.cut_radius_m(1)

    @property
    def cover_radius_m(self) -> float:
        """How far the repair reaches from its middle: the cover plies' edge, or the widest cut where there is no cover."""
        return self.patch_radius_m + self.cover_overlap_m

    @property
    def cover_thickness_m(self) -> float:
        return len(self.cover_angles) * self.patch_material.ply_thickness_m

    # ------------------------------------------------------------------------------------------------------- plies
    def parent_ply_step(self, ply: int) -> int | None:
        """The step that removes laminate ply `ply` (1 at the bottom face), or None for a ply no step cuts."""
        if not 1 <= ply <= self.plies:
            raise RepairError(f"The laminate has plies 1 to {self.plies}, not {ply}")
        from_top = self.plies - ply  # 0 for the top ply
        return from_top // self.plies_per_step + 1 if from_top < self.plies_removed else None

    def patch_group(self, step: int) -> tuple[float, ...]:
        """The angles of the patch plies that fill step `step`, lowest first."""
        self.cut_radius_m(step)
        start = (self.steps - step) * self.plies_per_step
        return self.patch_angles[start:start + self.plies_per_step]
