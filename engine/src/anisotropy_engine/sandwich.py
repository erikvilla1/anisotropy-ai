"""Stiffness of a sandwich panel: two thin laminated faces on a core that carries no in-plane load.

The faces are laminates listed from the bottom up, as in laminate.py: the lower face from the
panel's bottom surface to the core, the upper face from the core to the top surface. The reference
plane is the panel's geometric mid-plane, so z runs from -(t_lower + c + t_upper)/2 to the same
value positive, with the core between the faces. The core adds thickness only: its in-plane
stiffness is taken as zero, the usual assumption for a foam or honeycomb core whose modulus is
hundreds of times below the faces' (Zenkert, An Introduction to Sandwich Construction, 1995,
Chapter 3). With a core of zero thickness the result is the laminate of the two faces stacked.

Not covered: transverse shear deformation of the core, which lowers the buckling load and adds
deflection, face wrinkling, core crushing and shear failure of the core.
"""

import math

import numpy as np

from .laminate import Ply
from .rotation import transformed_reduced_stiffness


def sandwich_interfaces(lower_face: list[Ply], core_thickness_m: float, upper_face: list[Ply]) -> tuple[np.ndarray, np.ndarray]:
    """z of every ply boundary of the lower face and of the upper face, in m, bottom first, from the panel's mid-plane."""
    if not lower_face or not upper_face:
        raise ValueError("A sandwich needs at least one ply in each face")
    if not math.isfinite(core_thickness_m) or core_thickness_m < 0:
        raise ValueError(f"Core thickness must be finite and not negative, got {core_thickness_m}")
    t_lower = sum(ply.thickness_m for ply in lower_face)
    t_upper = sum(ply.thickness_m for ply in upper_face)
    half = (t_lower + core_thickness_m + t_upper) / 2
    z_lower = [-half]
    for ply in lower_face:
        z_lower.append(z_lower[-1] + ply.thickness_m)
    z_upper = [z_lower[-1] + core_thickness_m]
    for ply in upper_face:
        z_upper.append(z_upper[-1] + ply.thickness_m)
    return np.array(z_lower), np.array(z_upper)


def sandwich_abd(lower_face: list[Ply], core_thickness_m: float, upper_face: list[Ply]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A (N/m), B (N) and D (N*m) of the panel about its mid-plane: the sums of laminate.abd_matrices over the face plies only."""
    z_lower, z_upper = sandwich_interfaces(lower_face, core_thickness_m, upper_face)
    A, B, D = np.zeros((3, 3)), np.zeros((3, 3)), np.zeros((3, 3))
    for face, z in ((lower_face, z_lower), (upper_face, z_upper)):
        for k, ply in enumerate(face):
            bottom, top = z[k], z[k + 1]
            q_bar = transformed_reduced_stiffness(ply.material, ply.angle_deg)
            A += q_bar * (top - bottom)
            B += q_bar * (top**2 - bottom**2) / 2
            D += q_bar * (top**3 - bottom**3) / 3
    return A, B, D
