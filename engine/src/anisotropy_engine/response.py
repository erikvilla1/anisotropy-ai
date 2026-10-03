"""Laminate response to in-plane forces and bending moments, by classical laminate theory.

Loads are per unit width: N = [Nx, Ny, Nxy] in N/m and M = [Mx, My, Mxy] in N*m/m.
Curvatures are in 1/m. Plies are listed from the bottom face up, as in laminate.py.
"""

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict

from .laminate import Ply, abd_matrices, ply_interfaces
from .rotation import strain_transformation, stress_transformation, transformed_reduced_stiffness


class Loads(BaseModel):
    """Force (N/m) and moment (N*m/m) resultants per unit width. Any not given are zero."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    Nx: float = 0.0
    Ny: float = 0.0
    Nxy: float = 0.0
    Mx: float = 0.0
    My: float = 0.0
    Mxy: float = 0.0

    def as_vector(self) -> np.ndarray:
        """[Nx, Ny, Nxy, Mx, My, Mxy], in the row order of the ABD matrix."""
        return np.array([self.Nx, self.Ny, self.Nxy, self.Mx, self.My, self.Mxy])


def abd_matrix(plies: list[Ply]) -> np.ndarray:
    """6x6 laminate stiffness [[A, B], [B, D]]."""
    A, B, D = abd_matrices(plies)
    return np.block([[A, B], [B, D]])


def midplane_response(plies: list[Ply], loads: Loads) -> tuple[np.ndarray, np.ndarray]:
    """Mid-plane strains eps0 = [eps_x, eps_y, gamma_xy] and curvatures kappa = [k_x, k_y, k_xy] in 1/m."""
    deformation = np.linalg.solve(abd_matrix(plies), loads.as_vector())
    return deformation[:3], deformation[3:]


@dataclass(frozen=True)
class PlySurface:
    """Strain and stress on one face (bottom or top) of one ply."""

    ply_index: int
    angle_deg: float
    z_m: float
    strain_xy: np.ndarray  # [eps_x, eps_y, gamma_xy]
    stress_xy: np.ndarray  # [sigma_x, sigma_y, tau_xy], Pa
    strain_12: np.ndarray  # [eps_1, eps_2, gamma_12]
    stress_12: np.ndarray  # [sigma_1, sigma_2, tau_12], Pa


def ply_surfaces(plies: list[Ply], eps0: np.ndarray, kappa: np.ndarray) -> list[PlySurface]:
    """Bottom then top face of every ply, bottom ply first: 2N entries."""
    eps0, kappa = np.asarray(eps0, dtype=float), np.asarray(kappa, dtype=float)
    if eps0.shape != (3,) or kappa.shape != (3,):
        raise ValueError("eps0 and kappa must each have 3 components")
    z = ply_interfaces(plies)
    surfaces = []
    for k, ply in enumerate(plies):
        q_bar = transformed_reduced_stiffness(ply.material, ply.angle_deg)
        t_sigma = stress_transformation(ply.angle_deg)
        t_eps = strain_transformation(ply.angle_deg)
        for z_m in (z[k], z[k + 1]):
            strain_xy = eps0 + z_m * kappa
            stress_xy = q_bar @ strain_xy
            surfaces.append(PlySurface(
                ply_index=k,
                angle_deg=ply.angle_deg,
                z_m=float(z_m),
                strain_xy=strain_xy,
                stress_xy=stress_xy,
                strain_12=t_eps @ strain_xy,
                stress_12=t_sigma @ stress_xy,
            ))
    return surfaces
