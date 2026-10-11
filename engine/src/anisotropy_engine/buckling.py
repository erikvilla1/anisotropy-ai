"""Buckling of a simply supported rectangular laminated plate under uniform in-plane loads.

Classical laminated plate theory, midplane-symmetric laminates (B = 0), all four edges simply
supported, uniform resultants Nx, Ny and Nxy. The plate occupies 0 <= x <= a, 0 <= y <= b.
Reference loads follow the engine's sign convention, tension positive, so compression is
negative. The result is the load factor lambda such that lambda * (Nx, Ny, Nxy) is the lowest
load at which a slightly bent shape is in equilibrium with the flat one.

Two solutions (Whitney, Structural Analysis of Laminated Anisotropic Plates, 1987):

- Navier closed form for a specially orthotropic plate, D16 = D26 = 0 and Nxy = 0 (Section 5.5,
  Eq. 5.72): one mode sin(m pi x/a) sin(n pi y/b) per (m, n), the smallest factor governs.
- Ritz (Galerkin) double sine series for a general symmetric laminate with D16, D26 and shear
  (Sections 6.5 and 6.6, Eq. 6.38): K w = lambda G w with analytic integrals; the series only
  satisfies the geometric boundary conditions, so the factor converges from above as the
  number of terms grows and is an upper bound on the exact value.

Not covered: other edge conditions, unsymmetric laminates (Whitney Chapter 7), postbuckling,
transverse shear deformation, imperfections.
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from ._validation import finite_vector
from .laminate import Ply, abd_matrices

Method = Literal["navier", "ritz"]
ORTHOTROPIC_TOLERANCE = 1e-9  # |D16|, |D26| relative to the largest D entry
SYMMETRY_TOLERANCE = 1e-9  # |B| relative to max|A| * h


@dataclass(frozen=True)
class BucklingResult:
    """Lowest buckling load of the plate under the reference loads, and how it was found."""

    method: Method
    load_factor: float  # lambda: critical resultants = lambda * reference
    critical_loads: np.ndarray  # [Nx, Ny, Nxy] at buckling, N/m, tension positive
    mode: tuple[int, int] | None  # (m, n) half-waves for the Navier solution
    terms: int | None  # Ritz terms per direction
    mode_shape: np.ndarray | None  # Ritz coefficients W[m-1, n-1], largest normalized to 1
    orthotropic_factor: float | None  # Navier factor with D16 and D26 dropped, for comparison


def plate_bending_stiffness(plies: list[Ply]) -> np.ndarray:
    """D of a symmetric laminate. An unsymmetric laminate couples bending to stretching and is refused."""
    A, B, D = abd_matrices(plies)
    h = sum(ply.thickness_m for ply in plies)
    if np.abs(B).max() > SYMMETRY_TOLERANCE * np.abs(A).max() * h:
        raise ValueError("Plate buckling needs a midplane-symmetric laminate (B = 0); "
                         "the stability of unsymmetric laminates is not implemented")
    return D


def is_specially_orthotropic(D: np.ndarray) -> bool:
    return max(abs(D[0, 2]), abs(D[1, 2])) <= ORTHOTROPIC_TOLERANCE * np.abs(D).max()


def _check_plate(D, a, b, loads) -> tuple[np.ndarray, float, float, np.ndarray]:
    D = np.asarray(D, dtype=float)
    if D.shape != (3, 3) or not np.all(np.isfinite(D)) or not np.allclose(D, D.T):
        raise ValueError("D must be a finite symmetric 3x3 bending stiffness matrix")
    if not (math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0):
        raise ValueError("Plate dimensions a and b must be positive")
    loads = finite_vector(loads, "reference loads [Nx, Ny, Nxy]")
    if not np.any(loads):
        raise ValueError("Give at least one nonzero reference load")
    return D, float(a), float(b), loads


def navier_buckling(D, a: float, b: float, loads, max_half_waves: tuple[int, int] = (10, 10)) -> BucklingResult:
    """Closed-form buckling of a specially orthotropic simply supported plate, Whitney Eq. 5.72.

    For the mode (m, n), with alpha = m pi/a and beta = n pi/b,
      lambda(m, n) = [D11 alpha^4 + 2 (D12 + 2 D66) alpha^2 beta^2 + D22 beta^4] / (-Nx alpha^2 - Ny beta^2),
    counted only when the denominator is positive (the load does compress that mode). The
    smallest lambda over 1 <= m, n <= max_half_waves governs. Nxy must be zero: the sine
    series does not solve the shear problem (Whitney Section 5.7).
    """
    D, a, b, loads = _check_plate(D, a, b, loads)
    if not is_specially_orthotropic(D):
        raise ValueError("Navier buckling needs D16 = D26 = 0 (specially orthotropic); use the Ritz solution")
    if loads[2] != 0:
        raise ValueError("Navier buckling takes Nx and Ny only; shear needs the Ritz solution")
    best = None
    for m in range(1, max_half_waves[0] + 1):
        for n in range(1, max_half_waves[1] + 1):
            alpha, beta = m * math.pi / a, n * math.pi / b
            denominator = -loads[0] * alpha**2 - loads[1] * beta**2
            if denominator <= 0:
                continue
            factor = (D[0, 0] * alpha**4 + 2 * (D[0, 1] + 2 * D[2, 2]) * alpha**2 * beta**2 + D[1, 1] * beta**4) / denominator
            if best is None or factor < best[0]:
                best = (factor, (m, n))
    if best is None:
        raise ValueError("The reference loads do not compress the plate in any mode; no buckling")
    factor, mode = best
    return BucklingResult("navier", factor, factor * loads, mode, None, None, factor)


def _sine_integrals(length: float, terms: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """1D integrals over [0, L] of products of sin(i pi x/L) and cos(p pi x/L), i, p = 1..terms.

    SS[i,p] = int sin_i sin_p, CC[i,p] = int cos_i cos_p (both L/2 on the diagonal, else 0);
    SC[i,p] = int sin_i cos_p = 2 L i / (pi (i^2 - p^2)) when i + p is odd, else 0.
    """
    i = np.arange(1, terms + 1)
    SS = CC = np.eye(terms) * length / 2
    I, P = np.meshgrid(i, i, indexing="ij")
    with np.errstate(divide="ignore", invalid="ignore"):
        SC = np.where((I + P) % 2 == 1, 2 * length * I / (math.pi * (I**2 - P**2)), 0.0)
    return SS, CC, SC


def ritz_buckling(D, a: float, b: float, loads, terms: int) -> BucklingResult:
    """Buckling of a simply supported symmetric laminate by a double sine series (Whitney Eq. 6.38).

    w = sum W_mn sin(m pi x/a) sin(n pi y/b), m, n = 1..terms. The bending energy gives
    K_ij = int [D11 w_i,xx w_j,xx + D12 (w_i,xx w_j,yy + w_i,yy w_j,xx) + D22 w_i,yy w_j,yy
                + 4 D66 w_i,xy w_j,xy + 2 D16 (w_i,xx w_j,xy + w_i,xy w_j,xx)
                + 2 D26 (w_i,yy w_j,xy + w_i,xy w_j,yy)] dA
    and the in-plane loads (tension positive) give
    G_ij = -int [Nx w_i,x w_j,x + Ny w_i,y w_j,y + Nxy (w_i,x w_j,y + w_i,y w_j,x)] dA.
    K w = lambda G w; the smallest positive lambda governs. With D16 = D26 = 0 and Nxy = 0 the
    equations uncouple and reproduce navier_buckling exactly. The D16 and D26 terms couple
    modes whose m (or n) differ by an odd number, and so does Nxy.
    """
    D, a, b, loads = _check_plate(D, a, b, loads)
    if not isinstance(terms, int) or isinstance(terms, bool) or terms < 1:
        raise ValueError("terms must be a positive integer (terms per direction)")
    SSx, CCx, SCx = _sine_integrals(a, terms)
    SSy, CCy, SCy = _sine_integrals(b, terms)
    alpha = np.arange(1, terms + 1) * math.pi / a
    beta = np.arange(1, terms + 1) * math.pi / b
    n = terms * terms
    K = np.zeros((n, n))
    G = np.zeros((n, n))
    Nx, Ny, Nxy = loads
    for i in range(terms):
        for j in range(terms):
            r = i * terms + j
            for p in range(terms):
                for q in range(terms):
                    c = p * terms + q
                    ai, aj, bp, bq = alpha[i], beta[j], alpha[p], beta[q]
                    # Products of derivatives integrate to products of 1D integrals.
                    xx_xx = ai**2 * bp**2 * SSx[i, p] * SSy[j, q]
                    xx_yy = ai**2 * bq**2 * SSx[i, p] * SSy[j, q]
                    yy_xx = aj**2 * bp**2 * SSx[i, p] * SSy[j, q]
                    yy_yy = aj**2 * bq**2 * SSx[i, p] * SSy[j, q]
                    xy_xy = ai * aj * bp * bq * CCx[i, p] * CCy[j, q]
                    xx_xy = -ai**2 * bp * bq * SCx[i, p] * SCy[j, q]  # w_i,xx (sin sin) times w_j,xy (cos cos)
                    xy_xx = -ai * aj * bp**2 * SCx[p, i] * SCy[q, j]
                    yy_xy = -aj**2 * bp * bq * SCx[i, p] * SCy[j, q]
                    xy_yy = -ai * aj * bq**2 * SCx[p, i] * SCy[q, j]
                    K[r, c] = (D[0, 0] * xx_xx + D[0, 1] * (xx_yy + yy_xx) + D[1, 1] * yy_yy + 4 * D[2, 2] * xy_xy
                               + 2 * D[0, 2] * (xx_xy + xy_xx) + 2 * D[1, 2] * (yy_xy + xy_yy))
                    x_x = ai * bp * CCx[i, p] * SSy[j, q]
                    y_y = aj * bq * SSx[i, p] * CCy[j, q]
                    x_y = ai * bq * SCx[p, i] * SCy[j, q]  # w_i,x (cos sin) times w_j,y (sin cos)
                    y_x = aj * bp * SCx[i, p] * SCy[q, j]
                    G[r, c] = -(Nx * x_x + Ny * y_y + Nxy * (x_y + y_x))
    # K is symmetric positive definite for a stable laminate. Reduce K w = lambda G w to a symmetric
    # standard problem: with K = L L^T, (L^-1 G L^-T) v = mu v and lambda = 1/mu for mu > 0.
    L = np.linalg.cholesky((K + K.T) / 2)
    Linv = np.linalg.inv(L)
    M = Linv @ ((G + G.T) / 2) @ Linv.T
    mu, vectors = np.linalg.eigh(M)
    positive = mu > 1e-12 * np.abs(mu).max()
    if not np.any(positive):
        raise ValueError("The reference loads do not compress the plate in any mode; no buckling")
    k = int(np.argmax(np.where(positive, mu, -np.inf)))
    factor = 1 / mu[k]
    w = Linv.T @ vectors[:, k]
    shape = w.reshape(terms, terms)
    shape = shape / shape.flat[np.argmax(np.abs(shape))]
    orthotropic = None
    if loads[2] == 0:
        D0 = D.copy()
        D0[0, 2] = D0[2, 0] = D0[1, 2] = D0[2, 1] = 0.0
        orthotropic = navier_buckling(D0, a, b, loads, (terms, terms)).load_factor
    return BucklingResult("ritz", float(factor), factor * loads, None, terms, shape, orthotropic)


def plate_buckling(plies: list[Ply], a: float, b: float, loads, terms: int | None = None) -> BucklingResult:
    """Buckling of a simply supported plate made of the given laminate.

    A specially orthotropic laminate without shear uses the closed form. Otherwise the Ritz
    solution is used and `terms` must be given; the engine does not pick a series length.
    """
    D = plate_bending_stiffness(plies)
    loads = finite_vector(loads, "reference loads [Nx, Ny, Nxy]")
    if is_specially_orthotropic(D) and loads[2] == 0:
        return navier_buckling(D, a, b, loads)
    if terms is None:
        raise ValueError("This laminate has bending-twisting coupling (D16, D26) or the loads include shear: "
                         "give the number of Ritz terms per direction, and check convergence by increasing it")
    return ritz_buckling(D, a, b, loads, terms)
