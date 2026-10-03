"""Rotation of ply stresses, strains and stiffness between fiber and laminate axes.

The ply angle theta is positive counterclockwise from laminate axis x to fiber
axis 1, in degrees. Shear strain is engineering gamma, as in lamina.py.
"""

import math

import numpy as np

from .lamina import Lamina, reduced_stiffness


def _direction_cosines(angle_deg: float) -> tuple[float, float]:
    """m = cos(theta) and n = sin(theta) for a ply angle in degrees."""
    if not math.isfinite(angle_deg):
        raise ValueError(f"Ply angle must be a finite number of degrees, got {angle_deg}")
    theta = math.radians(angle_deg)
    return math.cos(theta), math.sin(theta)


def stress_transformation(angle_deg: float) -> np.ndarray:
    """[sigma1, sigma2, tau12] = T_sigma @ [sigma_x, sigma_y, tau_xy]"""
    m, n = _direction_cosines(angle_deg)
    return np.array([
        [m * m, n * n, 2 * m * n],
        [n * n, m * m, -2 * m * n],
        [-m * n, m * n, m * m - n * n],
    ])


def strain_transformation(angle_deg: float) -> np.ndarray:
    """[eps1, eps2, gamma12] = T_eps @ [eps_x, eps_y, gamma_xy]"""
    m, n = _direction_cosines(angle_deg)
    return np.array([
        [m * m, n * n, m * n],
        [n * n, m * m, -m * n],
        [-2 * m * n, 2 * m * n, m * m - n * n],
    ])


def transformed_reduced_stiffness(ply: Lamina, angle_deg: float) -> np.ndarray:
    """[sigma_x, sigma_y, tau_xy] = Q_bar @ [eps_x, eps_y, gamma_xy]

    Q_bar = inverse(T_sigma) @ Q @ T_eps, and rotating back by -theta inverts T_sigma.
    """
    return stress_transformation(-angle_deg) @ reduced_stiffness(ply) @ strain_transformation(angle_deg)
