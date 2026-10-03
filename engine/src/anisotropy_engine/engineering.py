"""Effective in-plane engineering constants of a laminate (Daniel & Ishai Section 7.12).

The laminate is treated as a homogeneous plate of thickness h, loaded in its plane
with no applied moments. The compliance comes from inverting the full 6x6 ABD matrix,
so an unsymmetric laminate is free to bend as it stretches (Section 7.12.3). For a
symmetric laminate this equals inverting A alone. A gripped test coupon restrains
bending, so for unsymmetric layups the measured modulus can be higher than predicted.
"""

from dataclasses import dataclass

import numpy as np

from .laminate import Ply
from .response import abd_matrix


@dataclass(frozen=True)
class EngineeringConstants:
    """Effective laminate constants. Moduli in Pa; the ratios are dimensionless."""

    Ex: float
    Ey: float
    Gxy: float
    nu_xy: float  # -eps_y / eps_x under a load in x
    nu_yx: float  # -eps_x / eps_y under a load in y
    eta_xs: float  # gamma_xy / eps_x under a load in x (shear-extension coupling)
    eta_ys: float  # gamma_xy / eps_y under a load in y


def engineering_constants(plies: list[Ply]) -> EngineeringConstants:
    """Daniel & Ishai Eq. 7.84, with a = the in-plane block of the inverted ABD matrix."""
    # Here the compliance entries are the result itself, so inverting is the right tool.
    a = np.linalg.inv(abd_matrix(plies))[:3, :3]
    h = sum(ply.thickness_m for ply in plies)
    return EngineeringConstants(
        Ex=float(1 / (h * a[0, 0])),
        Ey=float(1 / (h * a[1, 1])),
        Gxy=float(1 / (h * a[2, 2])),
        nu_xy=float(-a[1, 0] / a[0, 0]),
        nu_yx=float(-a[0, 1] / a[1, 1]),
        eta_xs=float(a[2, 0] / a[0, 0]),
        eta_ys=float(a[2, 1] / a[1, 1]),
    )
