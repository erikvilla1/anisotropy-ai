"""The plies and the adhesive of a repair's slice as solids (ADR-0132): what the finite element solve of the slice is given,
and what turns its strains back into each ply's stresses.

The slice's axes are x along the load, y across the panel's width and z through the thickness; a ply's are 1 along its
fibres, 2 across them in the ply and 3 through the thickness, and its angle turns 1 from x toward y about z. A stiffness is a
6 by 6 matrix between the stresses and the strains in the order xx, yy, zz, yz, xz, xy (11, 22, 33, 23, 13, 12 in a ply's
axes), the shear strains engineering ones.

A ply needs nine constants here: the four of the laminate's plane (E1, E2, G12, nu12) and five through the thickness
(`ThroughThickness`). The adhesive is isotropic, from its shear modulus and Poisson's ratio.

Far from the repair the laminate is one flat plate under the load: it stretches along x, it is free to contract across its
width, it does not shear in its plane and it does not bend, since the slice is held flat. `far_field` works out that state.
The slice is solved with the laminate's contraction there put on every part of it, so that far from the repair every ply's
stress is the laminate theory's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..lamina import Lamina
from .description import Repair, RepairError, RepairMaterial, ThroughThickness
from .step_lap import Adhesive

PAIRS = ((0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1))  # the order of a stress or a strain: xx, yy, zz, yz, xz, xy


def ply_compliance(lamina: Lamina, through: ThroughThickness) -> np.ndarray:
    """A ply's strains for its stresses in its own axes, 6 by 6, 1/Pa: an orthotropic solid's nine constants."""
    s = np.zeros((6, 6))
    s[0, 0], s[1, 1], s[2, 2] = 1 / lamina.E1, 1 / lamina.E2, 1 / through.E3
    s[0, 1] = s[1, 0] = -lamina.nu12 / lamina.E1
    s[0, 2] = s[2, 0] = -through.nu13 / lamina.E1
    s[1, 2] = s[2, 1] = -through.nu23 / lamina.E2
    s[3, 3], s[4, 4], s[5, 5] = 1 / through.G23, 1 / through.G13, 1 / lamina.G12
    return s


def _tensor(matrix: np.ndarray) -> np.ndarray:
    """A 6 by 6 stiffness as the fourth-order tensor it stands for."""
    tensor = np.zeros((3, 3, 3, 3))
    for a, (i, j) in enumerate(PAIRS):
        for b, (k, m) in enumerate(PAIRS):
            tensor[i, j, k, m] = tensor[j, i, k, m] = tensor[i, j, m, k] = tensor[j, i, m, k] = matrix[a, b]
    return tensor


def _axes(angle_deg: float) -> np.ndarray:
    """A ply's three axes as columns, in the slice's axes: 1 turned from x toward y by the ply's angle."""
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def turned_stiffness(stiffness: np.ndarray, angle_deg: float) -> np.ndarray:
    """A stiffness given in a ply's axes, in the slice's axes: each of its four directions turned by the ply's angle about
    the thickness."""
    turn = _axes(angle_deg)
    tensor = np.einsum("ia,jb,kc,md,abcd->ijkm", turn, turn, turn, turn, _tensor(np.asarray(stiffness, dtype=float)))
    return np.array([[tensor[i, j, k, m] for (k, m) in PAIRS] for (i, j) in PAIRS])


def ply_stiffness(material: RepairMaterial, angle_deg: float) -> np.ndarray:
    """A ply's stiffness in the slice's axes, 6 by 6, Pa. Refused when the material has no through-thickness constants."""
    if material.through is None:
        raise RepairError(f"The solve of the slice needs the through-thickness constants of {material.name!r}: nu23 for a unidirectional ply, "
                          "or E3, G13, G23, nu13 and nu23")
    return turned_stiffness(np.linalg.inv(ply_compliance(material.lamina, material.through)), angle_deg)


def adhesive_stiffness(adhesive: Adhesive) -> np.ndarray:
    """The adhesive's stiffness, 6 by 6, Pa: isotropic, from its shear modulus G and Poisson's ratio nu. With
    lam = 2 G nu / (1 - 2 nu), a direct stress is (lam + 2 G) times its own strain and lam times each of the other two."""
    if adhesive.poisson_ratio is None:
        raise RepairError("The solve of the slice needs the adhesive's Poisson's ratio")
    g, nu = adhesive.shear_modulus_pa, adhesive.poisson_ratio
    lam = 2 * g * nu / (1 - 2 * nu)
    stiffness = np.zeros((6, 6))
    stiffness[:3, :3] = lam
    stiffness[np.arange(3), np.arange(3)] = lam + 2 * g
    stiffness[np.arange(3, 6), np.arange(3, 6)] = g
    return stiffness


def plane_stress_stiffness(stiffness: np.ndarray) -> np.ndarray:
    """The stiffness of a layer free through its thickness (no stress on zz, yz or xz), 3 by 3 between the stresses and the
    strains xx, yy, xy: the three thickness strains are solved for and put back. For a ply this is the laminate theory's
    transformed reduced stiffness."""
    kept, free = [0, 1, 5], [2, 3, 4]
    c = np.asarray(stiffness, dtype=float)
    return c[np.ix_(kept, kept)] - c[np.ix_(kept, free)] @ np.linalg.solve(c[np.ix_(free, free)], c[np.ix_(free, kept)])


@dataclass(frozen=True)
class FarField:
    """The laminate far from the repair under the load: its strain along the load and across the width, and each ply's
    stress along the load (Pa), bottom ply first."""

    strain_x: float
    strain_width: float
    ply_stress_x: tuple[float, ...]


def far_field(repair: Repair, load_n_per_m: float) -> FarField:
    """The laminate far from the repair under a load per unit width (N/m): held flat, free to contract across its width
    (no force across it), kept from shearing in its plane. With A_11, A_12 and A_22 the sums of each ply's reduced
    stiffness times its thickness,

        strain_x = N / (A_11 - A_12^2 / A_22)        strain_width = -(A_12 / A_22) strain_x

    and a ply's stress along the load is Q_11 strain_x + Q_12 strain_width. For a laminate that is balanced (as many plies
    at +theta as at -theta) and symmetric this is the laminate theory's answer under the load alone."""
    if isinstance(load_n_per_m, bool) or not isinstance(load_n_per_m, (int, float)) or not math.isfinite(load_n_per_m):
        raise RepairError(f"The load must be a finite number, got {load_n_per_m!r}")
    reduced = [plane_stress_stiffness(ply_stiffness(repair.parent_material, angle)) for angle in repair.parent_angles]
    t = repair.ply_thickness_m
    a11, a12, a22 = (sum(float(q[i, j]) for q in reduced) * t for i, j in ((0, 0), (0, 1), (1, 1)))
    strain_x = float(load_n_per_m) / (a11 - a12**2 / a22)
    strain_width = -a12 / a22 * strain_x
    return FarField(strain_x, strain_width, tuple(float(q[0, 0] * strain_x + q[0, 1] * strain_width) for q in reduced))


def ply_axis_stress(stiffness: np.ndarray, angle_deg: float, strain: np.ndarray) -> np.ndarray:
    """A ply's stresses in its own axes (Pa: 11, 22, 33, 23, 13, 12) from its strains in the slice's axes (xx, yy, zz, yz,
    xz, xy, the shear strains engineering ones) and its stiffness there: the stresses in the slice's axes first, then
    turned into the ply's. `strain` may hold many rows, one state each."""
    stress = np.asarray(strain, dtype=float) @ np.asarray(stiffness, dtype=float).T
    rows = np.atleast_2d(stress)
    tensor = np.zeros((len(rows), 3, 3))
    for a, (i, j) in enumerate(PAIRS):
        tensor[:, i, j] = tensor[:, j, i] = rows[:, a]
    turn = _axes(angle_deg)
    turned = np.einsum("ai,nab,bj->nij", turn, tensor, turn)
    out = np.array([turned[:, i, j] for (i, j) in PAIRS]).T
    return out if stress.ndim == 2 else out[0]
