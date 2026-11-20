"""The stepped lap of a patch repair, taken from its description (ADR-0131), for the hand calculation of ADR-0130.

Along the slice through the repair's middle, from the patch's edge inward, the patch and the laminate are bonded ledge by
ledge. Each stretch of that path is one step of a stepped lap (`step_lap`):

- under the cover plies' overlap: the cover plies over the whole laminate;
- on the ledge of step j (j = 1 at the top): the cover plies and patch groups 1 to j over the laminate less the plies
  steps 1 to j removed;
- over the floor of a cavity that does not go through: the whole patch over the plies left under it, as far as the
  repair's middle, which is a plane of symmetry: both carry on across it and the shear stress is zero there.

A cut through every ply has no floor: the lap ends at the deepest cut, where the laminate ends and the patch carries
everything.

An adherend's stiffness in a step is its share of the bonded section's. Where the load has passed across, the patch and
the laminate strain alike, as one laminate under the load along x, free to contract and to shear as a whole. With A_o and
A_i the stretching (A) matrices of the two stacks (N/m) and a the inverse of their sum, that strain per unit load is the
first column of a, the outer stack carries the fraction f = (A_o a)_11 of the load and the inner one the rest, so

    (E t)_o = f / a_11        (E t)_i = (1 - f) / a_11

The two add up to the section's own stiffness 1 / a_11, and the force the patch carries where the strains are alike is
exact. A ply at an angle so counts for what it carries inside the bonded section, held from shearing by the plies around
it, not for what it would carry alone. Coupling with bending is left out, as the lap model itself leaves bending out. The
length bonded on a ledge is taken as the step length; the bondline's own thickness at the foot of each cut face is not
taken off it.
"""

from __future__ import annotations

import numpy as np

from ..laminate import Ply, abd_matrices
from .description import Repair, RepairError, RepairMaterial
from .step_lap import Step, StepLap, step_lap


def stretching_matrix(material: RepairMaterial, angles: tuple[float, ...]) -> np.ndarray:
    """The A matrix of a stack of plies, N/m, x along the load."""
    if not angles:
        raise RepairError("A stack needs at least one ply")
    extensional, _, _ = abd_matrices([Ply(material=material.lamina, angle_deg=angle, thickness_m=material.ply_thickness_m) for angle in angles])
    return np.asarray(extensional, dtype=float)


def shared_stiffnesses(outer: np.ndarray, inner: np.ndarray) -> tuple[float, float]:
    """E t along the load of two stacks bonded into one section, N/m, from their A matrices: each one's share of the
    section's stiffness 1 / a_11 when both strain as the section does under a load along x."""
    compliance = np.linalg.inv(outer + inner)
    share = float((outer @ compliance)[0, 0])
    if not 0 < share < 1:
        raise RepairError("One of the two stacks would carry none of the load, or less: the layups cannot be worked as a lap along this direction")
    total = 1.0 / float(compliance[0, 0])
    return share * total, (1 - share) * total


def lap_steps(repair: Repair) -> tuple[list[Step], list[str], bool]:
    """The steps of the repair's lap from the patch's edge inward, a name for each, and whether the lap ends at the
    repair's middle with the laminate carrying on under it (a cavity that does not go through)."""
    parent, patch = repair.parent_material, repair.patch_material
    steps, names = [], []

    def add(length: float, groups: int, name: str) -> None:
        """One step: patch groups 1 to `groups` and the cover plies over the laminate less the plies those steps removed."""
        patch_plies = repair.patch_angles[(repair.steps - groups) * repair.plies_per_step:]  # lowest first
        over = patch_plies + repair.cover_angles
        under = repair.parent_angles[:repair.plies - groups * repair.plies_per_step]
        outer_t, inner_t = len(over) * patch.ply_thickness_m, len(under) * parent.ply_thickness_m
        outer_s, inner_s = shared_stiffnesses(stretching_matrix(patch, over), stretching_matrix(parent, under))
        steps.append(Step(length, outer_t, outer_s / outer_t, inner_t, inner_s / inner_t))
        names.append(name)

    if repair.cover_angles:
        add(repair.cover_overlap_m, 0, "Cover overlap")
    for step in range(1, repair.steps):
        add(repair.step_length_m, step, f"Ledge of step {step}")
    if not repair.through:
        add(repair.cut_radius_m(repair.steps), repair.steps, "Floor")
    if not steps:
        raise RepairError("The repair has no ledge to carry load across")
    return steps, names, not repair.through


def repair_lap(repair: Repair, load_n_per_m: float) -> StepLap:
    """The repair's stepped lap under a load per unit width along x (N/m, tension positive), solved."""
    steps, _, continues = lap_steps(repair)
    return step_lap(steps, repair.adhesive, load_n_per_m, inner_continues=continues)
