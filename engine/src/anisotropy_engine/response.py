"""Laminate response to in-plane forces and bending moments, by classical laminate theory.

Loads are per unit width: N = [Nx, Ny, Nxy] in N/m and M = [Mx, My, Mxy] in N*m/m.
Curvatures are in 1/m. Plies are listed from the bottom face up, as in laminate.py.
"""

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict

from ._validation import finite_vector
from .laminate import Ply, abd_matrices, ply_interfaces
from .rotation import strain_transformation, stress_transformation, transformed_reduced_stiffness


class Loads(BaseModel):
    """Force (N/m) and moment (N*m/m) resultants per unit width. Any not given are zero."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

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
class ResponseVerification:
    """Numerical agreement with the full ABD solve; not experimental validation.

    Residuals are recovered minus requested/calculated deformation. Allowed errors
    are componentwise absolute + relative tolerances, in strain and 1/m.
    """

    passed: bool
    recovered_strain: np.ndarray
    recovered_curvature: np.ndarray
    strain_residual: np.ndarray
    curvature_residual: np.ndarray
    strain_allowed_error: np.ndarray
    curvature_allowed_error: np.ndarray


@dataclass(frozen=True)
class PrescribedCurvatureResult:
    """Known N and curvature determine eps0 and required M, all in SI base units."""

    A: np.ndarray
    B: np.ndarray
    D: np.ndarray
    midplane_strain: np.ndarray
    moments: np.ndarray  # [Mx, My, Mxy], N*m/m
    verification: ResponseVerification


def prescribed_curvature_response(
    plies: list[Ply], forces: np.ndarray, curvature: np.ndarray,
) -> PrescribedCurvatureResult:
    """Solve A eps0 = N - B kappa, then M = B eps0 + D kappa.

    All three forces (N/m) and all three curvatures (1/m) are required. Zero
    curvature imposes flatness in CLT; this does not solve rigid-body displacement
    or design a fixture. Ply order is bottom to top, as for the forward solve.
    Reject non-finite output and failed forward verification; never return an
    unchecked result. Tolerances are numerical policy, not physical accuracy.
    """
    forces = finite_vector(forces, "forces")
    curvature = finite_vector(curvature, "curvature")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        A, B, D = abd_matrices(plies)
        eps0 = np.linalg.solve(A, forces - B @ curvature)
        moments = B @ eps0 + D @ curvature
        if not all(np.isfinite(v).all() for v in (A, B, D, eps0, moments)):
            raise ValueError("Prescribed-curvature solve produced non-finite values")
        loads = Loads(Nx=forces[0], Ny=forces[1], Nxy=forces[2],
                      Mx=moments[0], My=moments[1], Mxy=moments[2])
        recovered_eps, recovered_kappa = midplane_response(plies, loads)
        if not all(np.isfinite(v).all() for v in (recovered_eps, recovered_kappa)):
            raise ValueError("Forward verification produced non-finite values")
        strain_error = recovered_eps - eps0
        curvature_error = recovered_kappa - curvature
        # Componentwise tolerance: atol + rtol * abs(reference), including zeros.
        strain_allowed = 1e-12 + 1e-9 * np.abs(eps0)
        curvature_allowed = 1e-9 + 1e-9 * np.abs(curvature)
        passed = bool(np.all(np.abs(strain_error) <= strain_allowed)
                      and np.all(np.abs(curvature_error) <= curvature_allowed))
        if not passed:
            raise ValueError("Forward verification did not recover the prescribed response within tolerance")
    verification = ResponseVerification(
        passed, recovered_eps, recovered_kappa, strain_error, curvature_error,
        strain_allowed, curvature_allowed,
    )
    return PrescribedCurvatureResult(A, B, D, eps0, moments, verification)


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
    eps0 = finite_vector(eps0, "eps0")
    kappa = finite_vector(kappa, "kappa")
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
