"""Uniform temperature change in a laminate, by classical laminate theory.

A temperature change delta_T (in K, the same number as a change in degC) makes each ply
want to expand freely by alpha * delta_T. Bonded plies cannot all do that, so the
laminate settles at one mid-plane strain and curvature, and each ply carries the stress
of the difference. Plies are listed from the bottom face up, as in laminate.py. Units
are SI: alpha in 1/K, N_T in N/m and M_T in N*m/m. Mechanical-only functions elsewhere
are unchanged; thermal effects apply only where delta_T is passed explicitly.
"""

import math
from dataclasses import replace

import numpy as np

from .lamina import Lamina
from .laminate import Ply, ply_interfaces
from .response import Loads, PlySurface, abd_matrix, ply_surfaces
from .rotation import strain_transformation, stress_transformation, transformed_reduced_stiffness


def _temperature_change(delta_T) -> float:
    """Require a finite number; zero is a valid change, a missing one is not."""
    if isinstance(delta_T, bool) or not isinstance(delta_T, (int, float, np.integer, np.floating)):
        raise ValueError(f"delta_T must be a number of kelvin (or degC), got {delta_T!r}")
    if not math.isfinite(delta_T):
        raise ValueError(f"delta_T must be finite, got {delta_T}")
    return float(delta_T)


def thermal_expansion_xy(material: Lamina, angle_deg: float) -> np.ndarray:
    """[alpha_x, alpha_y, alpha_xy] in 1/K for a ply at angle_deg; alpha_xy is engineering shear.

    Expansion coefficients are strains per kelvin, so they rotate like strain, and
    inverse(T_eps) at theta is T_eps at -theta.
    """
    if material.thermal_expansion is None:
        raise ValueError("This material has no thermal expansion coefficients (alpha1, alpha2)")
    alpha_12 = np.array([material.thermal_expansion.alpha1, material.thermal_expansion.alpha2, 0.0])
    return strain_transformation(-angle_deg) @ alpha_12


def thermal_resultants(plies: list[Ply], delta_T: float) -> tuple[np.ndarray, np.ndarray]:
    """Thermal force N_T (N/m) and moment M_T (N*m/m) resultants for a uniform temperature change.

    They are the resultants that would hold every ply at its free thermal strain, not applied loads.
    """
    delta_T = _temperature_change(delta_T)
    missing = [k for k, ply in enumerate(plies) if ply.material.thermal_expansion is None]
    if missing:
        raise ValueError(f"Plies {missing} have no thermal expansion coefficients (alpha1, alpha2)")
    z = ply_interfaces(plies)
    N_T, M_T = np.zeros(3), np.zeros(3)
    for k, ply in enumerate(plies):
        bottom, top = z[k], z[k + 1]
        q_bar = transformed_reduced_stiffness(ply.material, ply.angle_deg)
        q_alpha = q_bar @ thermal_expansion_xy(ply.material, ply.angle_deg)
        N_T += q_alpha * delta_T * (top - bottom)
        M_T += q_alpha * delta_T * (top**2 - bottom**2) / 2
    return N_T, M_T


def thermomechanical_response(plies: list[Ply], loads: Loads, delta_T: float) -> tuple[np.ndarray, np.ndarray]:
    """Mid-plane strain and curvature (1/m) under mechanical loads plus a temperature change.

    Solves ABD [eps0; kappa] = [N + N_T; M + M_T]. With zero loads this is the free thermal
    response, for example the warping of an unsymmetric laminate after cure.
    """
    N_T, M_T = thermal_resultants(plies, delta_T)
    deformation = np.linalg.solve(abd_matrix(plies), loads.as_vector() + np.concatenate([N_T, M_T]))
    return deformation[:3], deformation[3:]


def thermal_ply_surfaces(plies: list[Ply], eps0: np.ndarray, kappa: np.ndarray, delta_T: float) -> list[PlySurface]:
    """ply_surfaces, with each ply's stress from its mechanical strain only.

    Strains remain total strains eps0 + z * kappa, as a strain gauge would read them.
    Stress is Q_bar (eps0 + z * kappa - alpha * delta_T): the strain the ply was forced
    to take beyond its free thermal strain.
    """
    delta_T = _temperature_change(delta_T)
    surfaces = []
    for surface in ply_surfaces(plies, eps0, kappa):
        ply = plies[surface.ply_index]
        free = thermal_expansion_xy(ply.material, ply.angle_deg) * delta_T
        stress_xy = transformed_reduced_stiffness(ply.material, ply.angle_deg) @ (surface.strain_xy - free)
        surfaces.append(replace(surface, stress_xy=stress_xy, stress_12=stress_transformation(ply.angle_deg) @ stress_xy))
    return surfaces
