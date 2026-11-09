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


def abd_compliance(plies: list[Ply]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Blocks a (m/N), b (1/N) and d (1/(N*m)) of the inverted ABD matrix.

    [eps0; kappa] = [[a, b], [b.T, d]] [N; M]. Some texts write them as alpha,
    beta and delta. Here the inverse is the result itself, so it is formed explicitly.
    """
    inverse = np.linalg.inv(abd_matrix(plies))
    return inverse[:3, :3], inverse[:3, 3:], inverse[3:, 3:]


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
        verification = forward_verification(plies, np.concatenate([forces, moments]), eps0, curvature)
    return PrescribedCurvatureResult(A, B, D, eps0, moments, verification)


def forward_verification(plies: list[Ply], total_loads: np.ndarray, eps0: np.ndarray,
                         kappa: np.ndarray) -> ResponseVerification:
    """Re-solve the full ABD system for total_loads; it must recover eps0 and kappa.

    total_loads is [Nx, Ny, Nxy, Mx, My, Mxy], including any thermal resultants.
    Raises ValueError on non-finite output or a failed check, so an unchecked result
    is never returned. Tolerances are numerical policy (ADR-0013), not physical accuracy.
    """
    loads = Loads(**dict(zip(("Nx", "Ny", "Nxy", "Mx", "My", "Mxy"), np.asarray(total_loads, dtype=float))))
    recovered_eps, recovered_kappa = midplane_response(plies, loads)
    if not all(np.isfinite(v).all() for v in (recovered_eps, recovered_kappa)):
        raise ValueError("Forward verification produced non-finite values")
    strain_error = recovered_eps - eps0
    curvature_error = recovered_kappa - kappa
    # Componentwise tolerance: atol + rtol * abs(reference), including zeros.
    strain_allowed = 1e-12 + 1e-9 * np.abs(eps0)
    curvature_allowed = 1e-9 + 1e-9 * np.abs(kappa)
    passed = bool(np.all(np.abs(strain_error) <= strain_allowed)
                  and np.all(np.abs(curvature_error) <= curvature_allowed))
    if not passed:
        raise ValueError("Forward verification did not recover the prescribed response within tolerance")
    return ResponseVerification(passed, recovered_eps, recovered_kappa, strain_error, curvature_error,
                                strain_allowed, curvature_allowed)


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



def ply_surface_arrays(plies: list[Ply], eps0: np.ndarray, kappa: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """`ply_surfaces` for n mid-plane states at once (ADR-0069): eps0 and kappa are (n, 3), and the result is strain_xy, stress_xy,
    strain_12 and stress_12, each (n, plies, 2, 3), the bottom then the top face of every ply, bottom ply first. The same matrices and
    the same operations as `ply_surfaces`, row by row, so a finite element kernel gets every element's plies in one call."""
    eps0 = np.asarray(eps0, dtype=float)
    kappa = np.asarray(kappa, dtype=float)
    for value, name in ((eps0, "eps0"), (kappa, "kappa")):
        if value.ndim != 2 or value.shape[1] != 3:
            raise ValueError(f"{name} must be an array of shape (n, 3)")
        if not np.all(np.isfinite(value)):
            raise ValueError(f"{name} must contain only finite numbers")
    if eps0.shape != kappa.shape:
        raise ValueError("eps0 and kappa must have the same shape")
    z = ply_interfaces(plies)
    shape = (eps0.shape[0], len(plies), 2, 3)
    strain_xy, stress_xy, strain_12, stress_12 = (np.empty(shape) for _ in range(4))
    for k, ply in enumerate(plies):
        q_bar = transformed_reduced_stiffness(ply.material, ply.angle_deg)
        t_sigma = stress_transformation(ply.angle_deg)
        t_eps = strain_transformation(ply.angle_deg)
        for face, z_m in enumerate((z[k], z[k + 1])):
            strain = eps0 + z_m * kappa
            stress = (q_bar @ strain[:, :, None])[:, :, 0]
            strain_xy[:, k, face] = strain
            stress_xy[:, k, face] = stress
            strain_12[:, k, face] = (t_eps @ strain[:, :, None])[:, :, 0]
            stress_12[:, k, face] = (t_sigma @ stress[:, :, None])[:, :, 0]
    return strain_xy, stress_xy, strain_12, stress_12
