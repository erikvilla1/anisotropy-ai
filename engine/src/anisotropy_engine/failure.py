"""Ply failure checks: strength ratios, margins of safety and first-ply failure.

The strength ratio R is the factor by which every applied load can be multiplied
before a criterion predicts failure. Daniel & Ishai call it the safety factor S_f
(Eqs. 6.57-6.59). The analysis is linear elastic with mechanical loads only, so
ply stresses scale with the load. Thermal residual stresses are not included yet.
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .lamina import Strengths
from .laminate import Ply
from .response import Loads, midplane_response, ply_surfaces

Criterion = Literal["max_stress", "tsai_wu"]


def max_stress_ratio(stress_12: np.ndarray, strengths: Strengths) -> tuple[float, str]:
    """Smallest strength ratio over the five maximum-stress limits, and the mode that governs."""
    sigma1, sigma2, tau12 = stress_12
    s = strengths
    limits = [
        (s.F1t / sigma1 if sigma1 > 0 else math.inf, "longitudinal tension"),
        (s.F1c / -sigma1 if sigma1 < 0 else math.inf, "longitudinal compression"),
        (s.F2t / sigma2 if sigma2 > 0 else math.inf, "transverse tension"),
        (s.F2c / -sigma2 if sigma2 < 0 else math.inf, "transverse compression"),
        (s.F6 / abs(tau12) if tau12 != 0 else math.inf, "in-plane shear"),
    ]
    ratio, mode = min(limits, key=lambda limit: limit[0])
    return (ratio, mode) if math.isfinite(ratio) else (math.inf, "none")


def tsai_wu_ratio(stress_12: np.ndarray, strengths: Strengths, f12_star: float) -> float:
    """Load multiplier at which the Tsai-Wu failure index reaches 1 (Daniel & Ishai Eqs. 6.57-6.59).

    f12_star = f12 / sqrt(f11 * f22) must be measured or explicitly assumed. Daniel & Ishai
    Eq. 6.40 suggests -0.5. It must lie strictly between -1 and 1 for a closed failure envelope.
    """
    if not -1 < f12_star < 1:
        raise ValueError(f"f12_star must be between -1 and 1, got {f12_star}")
    s = strengths
    f1 = 1 / s.F1t - 1 / s.F1c
    f2 = 1 / s.F2t - 1 / s.F2c
    f11 = 1 / (s.F1t * s.F1c)
    f22 = 1 / (s.F2t * s.F2c)
    f66 = 1 / s.F6**2
    f12 = f12_star * math.sqrt(f11 * f22)
    sigma1, sigma2, tau12 = stress_12
    a = f11 * sigma1**2 + f22 * sigma2**2 + f66 * tau12**2 + 2 * f12 * sigma1 * sigma2
    b = f1 * sigma1 + f2 * sigma2
    # Positive root of a R^2 + b R - 1 = 0, rearranged to avoid cancellation when b < 0.
    denominator = b + math.sqrt(b * b + 4 * a)
    return 2 / denominator if denominator > 0 else math.inf


def margin_of_safety(strength_ratio: float, factor_of_safety: float) -> float:
    """MS = R / FS - 1. The check passes when MS >= 0."""
    if not factor_of_safety >= 1:
        raise ValueError(f"Factor of safety must be at least 1, got {factor_of_safety}")
    return strength_ratio / factor_of_safety - 1


@dataclass(frozen=True)
class PlyCheck:
    """Strength ratio on one face of one ply under the applied loads."""

    ply_index: int
    angle_deg: float
    z_m: float
    stress_12: np.ndarray  # [sigma1, sigma2, tau12], Pa
    strength_ratio: float
    mode: str  # governing maximum-stress mode, or "interactive" for Tsai-Wu


@dataclass(frozen=True)
class FirstPlyFailure:
    """Lowest strength ratio in the laminate and the loads at which the first ply fails."""

    criterion: str
    strength_ratio: float
    governing: PlyCheck
    failure_loads: Loads
    checks: list[PlyCheck]


def first_ply_failure(
    plies: list[Ply], loads: Loads, criterion: Criterion = "max_stress", f12_star: float | None = None
) -> FirstPlyFailure:
    """Check both faces of every ply; the smallest strength ratio gives first-ply failure.

    First-ply failure is the onset of damage in one ply, not the ultimate strength of the laminate.
    """
    if criterion not in ("max_stress", "tsai_wu"):
        raise ValueError(f"Unknown criterion {criterion!r}")
    if criterion == "tsai_wu" and f12_star is None:
        raise ValueError("Tsai-Wu needs an explicit f12_star, measured or assumed")
    missing = [k for k, ply in enumerate(plies) if ply.material.strengths is None]
    if missing:
        raise ValueError(f"Plies {missing} have no strengths")
    if not np.any(loads.as_vector()):
        raise ValueError("Apply at least one nonzero load")

    eps0, kappa = midplane_response(plies, loads)
    checks = []
    for surface in ply_surfaces(plies, eps0, kappa):
        strengths = plies[surface.ply_index].material.strengths
        if criterion == "max_stress":
            ratio, mode = max_stress_ratio(surface.stress_12, strengths)
        else:
            ratio, mode = tsai_wu_ratio(surface.stress_12, strengths, f12_star), "interactive"
        checks.append(PlyCheck(
            ply_index=surface.ply_index,
            angle_deg=surface.angle_deg,
            z_m=surface.z_m,
            stress_12=surface.stress_12,
            strength_ratio=ratio,
            mode=mode,
        ))

    governing = min(checks, key=lambda check: check.strength_ratio)
    scaled = {name: value * governing.strength_ratio for name, value in loads.model_dump().items()}
    return FirstPlyFailure(
        criterion=criterion,
        strength_ratio=governing.strength_ratio,
        governing=governing,
        failure_loads=Loads(**scaled),
        checks=checks,
    )
