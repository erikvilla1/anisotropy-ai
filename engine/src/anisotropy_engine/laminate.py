"""Laminate stiffness (A, B, D) from a stack of plies, by classical laminate theory.

Plies are listed from the bottom face up: the first ply starts at z = -h/2, and z
is positive upward from the mid-plane. Units are SI: thickness in m, A in N/m,
B in N and D in N*m.
"""

import numpy as np
from pydantic import BaseModel, ConfigDict, PositiveFloat

from .lamina import Lamina
from .rotation import transformed_reduced_stiffness


class Ply(BaseModel):
    """One ply in a stack: its material, orientation and cured thickness."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    material: Lamina
    angle_deg: float
    thickness_m: PositiveFloat


def ply_interfaces(plies: list[Ply]) -> np.ndarray:
    """z of every ply boundary in m, bottom face first: [-h/2, ..., +h/2]."""
    if not plies:
        raise ValueError("A laminate needs at least one ply")
    h = sum(ply.thickness_m for ply in plies)
    z = [-h / 2]
    for ply in plies:
        z.append(z[-1] + ply.thickness_m)
    return np.array(z)


def abd_matrices(plies: list[Ply]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A (N/m), B (N) and D (N*m) for plies listed from the bottom face up."""
    z = ply_interfaces(plies)
    A, B, D = np.zeros((3, 3)), np.zeros((3, 3)), np.zeros((3, 3))
    for k, ply in enumerate(plies):
        bottom, top = z[k], z[k + 1]
        q_bar = transformed_reduced_stiffness(ply.material, ply.angle_deg)
        A += q_bar * (top - bottom)
        B += q_bar * (top**2 - bottom**2) / 2
        D += q_bar * (top**3 - bottom**3) / 3
    return A, B, D
