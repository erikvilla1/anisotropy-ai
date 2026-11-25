"""A stepped patch repair of a flat laminate, described by a few numbers (ADR-0131).

Two kinds are stated. In a flush repair (the first kind, and the one meant unless said) a round piece of damage is cut out of a laminate from its top face in steps: the deepest step has the damage's diameter, and
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

In an external repair (ADR-0131 amendment 1) nothing is cut in steps. The damage is cut out as a round hole through every
ply, and a patch made flat is bonded on the laminate's top face over it: one flat bondline, the patch's longest plies on it
and each step above shorter by the step length at each edge, so the patch thins toward its edge in ledges.

    kind            "external"
    damage          the hole's diameter
    steps           how many, the length of each ledge, and how many patch plies each step has (one unless said)
    patch           its angles, from the ply on the laminate upward (always said); its ply material (the laminate's unless
                    said, and its plies may be of any thickness); how far its shortest plies reach past the hole's edge
                    (`patch_overlap_m`); and its shape: "round", or "strip", a band across the panel's whole width stepped
                    along the load only
    cover           none: the patch's longest plies are its first step

Its steps are counted from the laminate up: step 1 is the longest, on the bondline.

What this description cannot state yet: a flush patch whose plies are thicker or thinner than the laminate's, a scarf (a
taper with no ledges), steps of different lengths, a flush repair that is not round, a curved laminate, a backing under a cut
that goes through every ply, an external patch laid shortest ply first (its longer plies joggle down over the shorter), a
patch on both faces, and damage left in place under an external patch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..lamina import Lamina
from .step_lap import Adhesive


REPAIR_KINDS = ("flush", "external")
PATCH_SHAPES = ("round", "strip")


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
class ThroughThickness:
    """A ply's constants through its thickness (ADR-0132), 3 the thickness direction: Young's modulus E3 and the shear
    moduli G13 and G23 (Pa), and Poisson's ratios nu13 and nu23 (the strain along 3 for a strain along 1 or 2, with the sign
    changed). A hand calculation in the laminate's plane does not use them; the solve of a repair's slice does."""

    E3: float
    G13: float
    G23: float
    nu13: float
    nu23: float

    def __post_init__(self) -> None:
        for name in ("E3", "G13", "G23"):
            object.__setattr__(self, name, _positive(getattr(self, name), name))
        for name in ("nu13", "nu23"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise RepairError(f"{name} must be a finite number, got {value!r}")
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True)
class PlyEnergies:
    """A ply's fracture energies (J/m^2): the energy it takes to part a unit area of one crack (ADR-0141). `fibre_tension`
    and `fibre_compression` are a break across the fibres, pulled apart and crushed; `matrix_tension` and `matrix_shear` a
    crack along the fibres, pulled open and slid. A hand calculation and the elastic solve do not use them; following the
    plies as they damage does."""

    fibre_tension: float
    fibre_compression: float
    matrix_tension: float
    matrix_shear: float

    def __post_init__(self) -> None:
        for name in ("fibre_tension", "fibre_compression", "matrix_tension", "matrix_shear"):
            object.__setattr__(self, name, _positive(getattr(self, name), name.replace("_", " ")))


def tape_through_thickness(lamina: Lamina, nu23: float) -> ThroughThickness:
    """The through-thickness constants of a unidirectional ply from one number. Such a ply is the same in every direction
    across its fibres, so E3 = E2, G13 = G12 and nu13 = nu12, and the shear modulus across the fibres follows from E2 and
    nu23 as in an isotropic material: G23 = E2 / (2 (1 + nu23))."""
    if isinstance(nu23, bool) or not isinstance(nu23, (int, float)) or not math.isfinite(nu23) or not -1 < nu23 < 1:
        raise RepairError(f"nu23 must be above -1 and below 1, got {nu23!r}")
    return ThroughThickness(E3=lamina.E2, G13=lamina.G12, G23=lamina.E2 / (2 * (1 + nu23)), nu13=lamina.nu12, nu23=float(nu23))


@dataclass(frozen=True)
class RepairMaterial:
    """A ply material of a repair: its name, its in-plane constants and its cured ply thickness; and, when the slice is to be
    solved, its constants through the thickness, and when the plies are to be followed as they damage, its four fracture
    energies."""

    name: str
    lamina: Lamina
    ply_thickness_m: float
    through: ThroughThickness | None = None
    energies: PlyEnergies | None = None  # for following the plies as they damage (ADR-0141)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise RepairError("A material needs a name")
        if not isinstance(self.lamina, Lamina):
            raise RepairError(f"Material {self.name!r} needs its ply constants (E1, E2, G12, nu12)")
        object.__setattr__(self, "ply_thickness_m", _positive(self.ply_thickness_m, f"The ply thickness of {self.name!r}"))
        if self.energies is not None and not isinstance(self.energies, PlyEnergies):
            raise RepairError(f"The fracture energies of {self.name!r} must be the fibre's in tension and compression and the matrix "
                              "crack's in tension and shear")
        if self.through is not None:
            if not isinstance(self.through, ThroughThickness):
                raise RepairError(f"The through-thickness constants of {self.name!r} must be E3, G13, G23, nu13 and nu23")
            # The three direct strains under the three direct stresses: a material stores energy under every load only when
            # this matrix is positive definite, which its three leading minors say.
            la, th = self.lamina, self.through
            s11, s22, s33 = 1 / la.E1, 1 / la.E2, 1 / th.E3
            s12, s13, s23 = -la.nu12 / la.E1, -th.nu13 / la.E1, -th.nu23 / la.E2
            minor = s11 * s22 - s12**2
            whole = s11 * (s22 * s33 - s23**2) - s12 * (s12 * s33 - s23 * s13) + s13 * (s12 * s23 - s22 * s13)
            if minor <= 0 or whole <= 0:
                raise RepairError(f"The constants of {self.name!r} do not make a material: with these Poisson's ratios it would give "
                                  "energy back under some load (nu13 and nu23 are too large for E1, E2 and E3)")


@dataclass(frozen=True)
class Repair:
    """A stepped patch repair. Angles are in degrees from x, the load's direction; a list of the laminate's or the patch's
    plies starts at the lowest ply. `kind` is "flush" (a stepped cut filled level) or "external" (a stepped patch bonded on
    top over a hole); `patch_overlap_m` and `patch_shape` belong to the external kind."""

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
    kind: str = "flush"
    patch_overlap_m: float = 0.0
    patch_shape: str = "round"

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
        if self.kind not in REPAIR_KINDS:
            raise RepairError(f"The kind of repair is one of {', '.join(REPAIR_KINDS)}, got {self.kind!r}")
        if self.patch_shape not in PATCH_SHAPES:
            raise RepairError(f"The patch's shape is one of {', '.join(PATCH_SHAPES)}, got {self.patch_shape!r}")
        if self.kind == "external":
            self._external(set_)
            return
        if self.patch_shape != "round" or self.patch_overlap_m not in (0, 0.0):
            raise RepairError("A flush repair is round and its deepest cut has the damage's diameter: a strip and a patch overlap "
                              "belong to an external repair")
        set_("patch_overlap_m", 0.0)
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

    def _external(self, set_) -> None:
        """The checks of a patch bonded on top over a hole."""
        if self.patch_material is None:
            set_("patch_material", self.parent_material)
        elif not isinstance(self.patch_material, RepairMaterial):
            raise RepairError("The patch's material must be a ply material")
        if self.patch_angles is None:
            raise RepairError("An external patch needs its plies listed, from the one on the laminate upward")
        set_("patch_angles", _angles(self.patch_angles, "The patch's layup"))
        if len(self.patch_angles) != self.patch_plies:
            raise RepairError(f"{self.steps} steps of {self.plies_per_step} plies make a patch of {self.patch_plies} plies, and "
                              f"{len(self.patch_angles)} are listed")
        if tuple(self.cover_angles) or self.cover_overlap_m not in (0, 0.0):
            raise RepairError("An external patch has no cover plies: its longest plies are its first step")
        set_("cover_angles", ())
        set_("cover_overlap_m", 0.0)
        set_("patch_overlap_m", _positive(self.patch_overlap_m, "The patch's overlap past the damage's edge"))
        bondline = self.adhesive.thickness_m
        if bondline >= self.step_length_m or bondline >= self.patch_overlap_m:
            raise RepairError("The bondline must be thinner than a step is long and than the patch's overlap")
        reach = 2 * self.patch_radius_m
        if self.patch_shape == "round" and reach >= min(self.panel_length_m, self.panel_width_m):
            raise RepairError(f"The patch is {reach:g} m across, so the panel must be longer and wider than that "
                              f"(it is {self.panel_length_m:g} m by {self.panel_width_m:g} m)")
        if self.patch_shape == "strip" and (reach >= self.panel_length_m or self.damage_diameter_m >= self.panel_width_m):
            raise RepairError(f"A strip patch {reach:g} m long over a hole of {self.damage_diameter_m:g} m needs a panel longer than "
                              f"the patch and wider than the hole (it is {self.panel_length_m:g} m by {self.panel_width_m:g} m)")

    # ------------------------------------------------------------------------------------------------------- sizes
    @property
    def external(self) -> bool:
        return self.kind == "external"

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
    def patch_plies(self) -> int:
        """How many plies the patch has: one group for each step."""
        return self.steps * self.plies_per_step

    @property
    def plies_removed(self) -> int:
        """The laminate plies the steps cut: none under an external patch, whose hole is the damage itself."""
        return 0 if self.external else self.patch_plies

    @property
    def group_thickness_m(self) -> float:
        """The height of one step: the thickness of its patch plies, which in a flush repair is that of the plies it removes."""
        material = self.patch_material if self.external else self.parent_material
        return self.plies_per_step * material.ply_thickness_m

    @property
    def patch_thickness_m(self) -> float:
        return self.steps * self.group_thickness_m

    @property
    def through(self) -> bool:
        """Every ply is cut at the repair's middle: the deepest step of a flush repair is a hole, as an external repair's
        damage always is."""
        return self.external or self.plies_removed == self.plies

    @property
    def depth_m(self) -> float:
        """How deep the stepped cavity is, from the top face: nothing under an external patch."""
        return 0.0 if self.external else self.steps * self.group_thickness_m

    def cut_radius_m(self, step: int) -> float:
        """The radius of step `step`. Flush (step 1 at the top): where it is cut, the damage's radius for the deepest and one
        step length more for each step above it. External (step 1 on the laminate): how far its plies reach, the damage's
        radius and the patch's overlap for the shortest and one step length more for each step under it."""
        if not 1 <= step <= self.steps:
            raise RepairError(f"The repair has steps 1 to {self.steps}, not {step}")
        return self.damage_diameter_m / 2 + self.patch_overlap_m + (self.steps - step) * self.step_length_m

    @property
    def patch_radius_m(self) -> float:
        """The radius of the widest cut, at the top face; of an external patch, how far its longest plies reach."""
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
        if self.external:
            return None
        from_top = self.plies - ply  # 0 for the top ply
        return from_top // self.plies_per_step + 1 if from_top < self.plies_removed else None

    def patch_group(self, step: int) -> tuple[float, ...]:
        """The angles of the patch plies of step `step`, lowest first."""
        self.cut_radius_m(step)
        start = (step - 1 if self.external else self.steps - step) * self.plies_per_step
        return self.patch_angles[start:start + self.plies_per_step]
