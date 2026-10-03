"""Mixed conditions: for each load/deformation pair, either the load or the deformation is known.

The six pairs are (Nx, eps_x), (Ny, eps_y), (Nxy, gamma_xy), (Mx, kappa_x), (My, kappa_y) and
(Mxy, kappa_xy). A force may instead be given as an average stress through the thickness,
sigma = N / h, as lamina problems usually state it. Known loads are mechanical; a temperature
change adds its thermal resultants. All values are SI: N/m, N*m/m, Pa, strain and 1/m.
Examples: a lamina kept rectangular (gamma_xy = 0) under known normal stresses, a coupon
between rigid walls (eps_y = 0), and a cured laminate held flat in one direction only.
"""

from dataclasses import dataclass

import numpy as np

from ._validation import finite_vector
from .laminate import Ply
from .response import Loads, ResponseVerification, abd_matrix, forward_verification
from .thermal import thermal_resultants

PAIRS = (("Nx", "sigma_x", "eps_x"), ("Ny", "sigma_y", "eps_y"), ("Nxy", "tau_xy", "gamma_xy"),
         ("Mx", "kappa_x"), ("My", "kappa_y"), ("Mxy", "kappa_xy"))
DEFORMATIONS = ("eps_x", "eps_y", "gamma_xy", "kappa_x", "kappa_y", "kappa_xy")
AVERAGE_STRESSES = ("sigma_x", "sigma_y", "tau_xy")


@dataclass(frozen=True)
class MixedResult:
    """The full state once the unknown half of every pair is solved, in SI units."""

    loads: Loads  # mechanical resultants, given or solved
    midplane_strain: np.ndarray  # [eps_x, eps_y, gamma_xy]
    curvature: np.ndarray  # [kappa_x, kappa_y, kappa_xy], 1/m
    known: tuple[str, ...]  # the given quantity of each pair, in pair order
    verification: ResponseVerification


def mixed_response(plies: list[Ply], known: dict[str, float], delta_T: float | None) -> MixedResult:
    """Solve the ABD relation when each pair has exactly one known quantity.

    With total loads F + F_T = K d, rows with a known load give K_LL d_L = F_L + F_T,L - K_LD d_D,
    and rows with a known deformation then give F_D = K_D d - F_T,D. delta_T is the temperature
    change in K, or None for mechanical loading only. A full forward solve with the resulting
    total loads must recover the deformation (ADR-0013 tolerances), or the result is rejected.
    """
    names = [name for pair in PAIRS for name in pair]
    unknown = sorted(set(known) - set(names))
    if unknown:
        raise ValueError(f"Unknown quantities {unknown}; use names from {PAIRS}")
    chosen = []
    for pair in PAIRS:
        given = [name for name in pair if name in known]
        if len(given) != 1:
            raise ValueError(f"Give exactly one of {pair}; got {given or 'none'}")
        chosen.append(given[0])
    values = finite_vector([known[name] for name in chosen], "known values", 6)

    h = sum(ply.thickness_m for ply in plies)
    load_rows = [i for i, name in enumerate(chosen) if name not in DEFORMATIONS]
    deformation_rows = [i for i, name in enumerate(chosen) if name in DEFORMATIONS]
    loads, deformation = np.zeros(6), np.zeros(6)
    for i, name in enumerate(chosen):
        if name in DEFORMATIONS:
            deformation[i] = values[i]
        else:
            loads[i] = values[i] * h if name in AVERAGE_STRESSES else values[i]

    with np.errstate(over="raise", invalid="raise", divide="raise"):
        K = abd_matrix(plies)
        thermal = (np.concatenate(thermal_resultants(plies, delta_T)) if delta_T is not None else np.zeros(6))
        if load_rows:
            rhs = (loads[load_rows] + thermal[load_rows]
                   - K[np.ix_(load_rows, deformation_rows)] @ deformation[deformation_rows])
            deformation[load_rows] = np.linalg.solve(K[np.ix_(load_rows, load_rows)], rhs)
        loads[deformation_rows] = K[deformation_rows] @ deformation - thermal[deformation_rows]
        if not (np.isfinite(loads).all() and np.isfinite(deformation).all()):
            raise ValueError("Mixed-condition solve produced non-finite values")
        verification = forward_verification(plies, loads + thermal, deformation[:3], deformation[3:])
    return MixedResult(Loads(**dict(zip(("Nx", "Ny", "Nxy", "Mx", "My", "Mxy"), loads))),
                       deformation[:3], deformation[3:], tuple(chosen), verification)
