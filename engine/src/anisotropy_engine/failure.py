"""Ply failure checks: strength ratios, margins of safety and first-ply failure.

The strength ratio R is the factor by which every applied load can be multiplied
before a criterion predicts failure. Daniel & Ishai call it the safety factor S_f
(Eqs. 6.57-6.59). The analysis is linear elastic, so ply stresses scale with the load.

When some loading stays constant, such as the residual stress of a temperature change
or a load held fixed, the stress at failure is fixed + R * variable and only the variable
part scales (Daniel & Ishai Section 9.8, Eqs. 9.25-9.28). The "combined" functions find
that R.
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from ._validation import finite_vector
from .lamina import Strengths
from .laminate import Ply
from .response import Loads, midplane_response, ply_surfaces
from .thermal import thermal_ply_surfaces, thermomechanical_response

Criterion = Literal["max_stress", "tsai_wu"]


def max_stress_ratio(stress_12: np.ndarray, strengths: Strengths) -> tuple[float, str]:
    """Smallest strength ratio over the five maximum-stress limits, and the mode that governs."""
    sigma1, sigma2, tau12 = finite_vector(stress_12, "stress_12")
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
    sigma1, sigma2, tau12 = finite_vector(stress_12, "stress_12")
    s = strengths
    f1 = 1 / s.F1t - 1 / s.F1c
    f2 = 1 / s.F2t - 1 / s.F2c
    f11 = 1 / (s.F1t * s.F1c)
    f22 = 1 / (s.F2t * s.F2c)
    f66 = 1 / s.F6**2
    f12 = f12_star * math.sqrt(f11 * f22)
    a = f11 * sigma1**2 + f22 * sigma2**2 + f66 * tau12**2 + 2 * f12 * sigma1 * sigma2
    b = f1 * sigma1 + f2 * sigma2
    # Positive root of a R^2 + b R - 1 = 0, rearranged to avoid numerator cancellation when b > 0.
    denominator = b + math.sqrt(b * b + 4 * a)
    return 2 / denominator if denominator > 0 else math.inf


def max_stress_ratio_combined(fixed_12: np.ndarray, variable_12: np.ndarray, strengths: Strengths) -> tuple[float, str]:
    """Smallest R >= 0 at which fixed_12 + R * variable_12 reaches a maximum-stress limit, and its mode.

    R = 0 means the fixed stresses alone reach a limit. Infinity means the variable stresses
    never do. With fixed_12 = 0 this equals max_stress_ratio(variable_12).
    """
    s1, s2, s6 = finite_vector(fixed_12, "fixed_12")
    v1, v2, v6 = finite_vector(variable_12, "variable_12")
    st = strengths
    limits = []
    for fixed, variable, tension, compression, modes in (
        (s1, v1, st.F1t, st.F1c, ("longitudinal tension", "longitudinal compression")),
        (s2, v2, st.F2t, st.F2c, ("transverse tension", "transverse compression")),
        (s6, v6, st.F6, st.F6, ("in-plane shear", "in-plane shear")),
    ):
        if fixed >= tension:
            limits.append((0.0, modes[0]))
        elif fixed <= -compression:
            limits.append((0.0, modes[1]))
        elif variable > 0:
            limits.append(((tension - fixed) / variable, modes[0]))
        elif variable < 0:
            limits.append(((-compression - fixed) / variable, modes[1]))
    return min(limits, key=lambda limit: limit[0]) if limits else (math.inf, "none")


def tsai_wu_ratio_combined(fixed_12: np.ndarray, variable_12: np.ndarray, strengths: Strengths,
                           f12_star: float) -> float:
    """Smallest R >= 0 at which the Tsai-Wu index of fixed_12 + R * variable_12 reaches 1.

    Substituting into Eq. 6.29 gives a R^2 + b R + c = 0 (Daniel & Ishai Eqs. 9.25-9.27), with
    c = index(fixed) - 1. R = 0 when the fixed stresses alone reach the criterion. With
    fixed_12 = 0 this equals tsai_wu_ratio(variable_12).
    """
    if not -1 < f12_star < 1:
        raise ValueError(f"f12_star must be between -1 and 1, got {f12_star}")
    s = finite_vector(fixed_12, "fixed_12")
    v = finite_vector(variable_12, "variable_12")
    st = strengths
    f1 = 1 / st.F1t - 1 / st.F1c
    f2 = 1 / st.F2t - 1 / st.F2c
    f11 = 1 / (st.F1t * st.F1c)
    f22 = 1 / (st.F2t * st.F2c)
    f66 = 1 / st.F6**2
    f12 = f12_star * math.sqrt(f11 * f22)

    def quadratic(x, y):
        return f11 * x[0] * y[0] + f22 * x[1] * y[1] + f66 * x[2] * y[2] + f12 * (x[0] * y[1] + x[1] * y[0])

    a = quadratic(v, v)
    b = f1 * v[0] + f2 * v[1] + 2 * quadratic(s, v)
    c = f1 * s[0] + f2 * s[1] + quadratic(s, s) - 1
    if c >= 0:
        return 0.0
    # a >= 0 because the quadratic part is positive definite for |f12_star| < 1, and c < 0,
    # so there is one positive root. This form avoids cancellation when b > 0.
    denominator = b + math.sqrt(b * b - 4 * a * c)
    return -2 * c / denominator if denominator > 0 else math.inf


def margin_of_safety(strength_ratio: float, factor_of_safety: float) -> float:
    """MS = R / FS - 1. Positive infinity is valid for an unstressed ply's ratio."""
    if not math.isfinite(factor_of_safety) or factor_of_safety < 1:
        raise ValueError(f"Factor of safety must be finite and at least 1, got {factor_of_safety}")
    if math.isnan(strength_ratio) or strength_ratio < 0:
        raise ValueError(f"Strength ratio must be nonnegative (positive infinity is allowed), got {strength_ratio}")
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


def first_ply_failure_combined(
    plies: list[Ply], fixed: Loads, variable: Loads, delta_T: float | None,
    criterion: Criterion = "max_stress", f12_star: float | None = None,
) -> FirstPlyFailure:
    """First-ply failure when only part of the loading grows: failure at fixed + R * variable.

    The fixed loads and the residual stress of delta_T (in K, or None for no temperature
    change) stay constant; the variable loads scale with R. Both faces of every ply are
    checked. Each check's stress_12 is the stress when that face reaches the criterion, and
    failure_loads is fixed + R * variable. With fixed = 0 and delta_T = None this equals
    first_ply_failure(plies, variable).
    """
    if criterion not in ("max_stress", "tsai_wu"):
        raise ValueError(f"Unknown criterion {criterion!r}")
    if criterion == "tsai_wu" and f12_star is None:
        raise ValueError("Tsai-Wu needs an explicit f12_star, measured or assumed")
    missing = [k for k, ply in enumerate(plies) if ply.material.strengths is None]
    if missing:
        raise ValueError(f"Plies {missing} have no strengths")
    if not np.any(variable.as_vector()):
        raise ValueError("Give at least one nonzero variable load")

    if delta_T is None:
        eps0, kappa = midplane_response(plies, fixed)
        fixed_faces = ply_surfaces(plies, eps0, kappa)
    else:
        eps0, kappa = thermomechanical_response(plies, fixed, delta_T)
        fixed_faces = thermal_ply_surfaces(plies, eps0, kappa, delta_T)
    eps0, kappa = midplane_response(plies, variable)
    variable_faces = ply_surfaces(plies, eps0, kappa)

    checks = []
    for held, scaled in zip(fixed_faces, variable_faces):
        strengths = plies[held.ply_index].material.strengths
        if criterion == "max_stress":
            ratio, mode = max_stress_ratio_combined(held.stress_12, scaled.stress_12, strengths)
        else:
            ratio = tsai_wu_ratio_combined(held.stress_12, scaled.stress_12, strengths, f12_star)
            mode = "interactive"
        stress = held.stress_12 + (ratio * scaled.stress_12 if math.isfinite(ratio) else 0.0)
        checks.append(PlyCheck(ply_index=held.ply_index, angle_deg=held.angle_deg, z_m=held.z_m,
                               stress_12=stress, strength_ratio=ratio, mode=mode))

    governing = min(checks, key=lambda check: check.strength_ratio)
    if not math.isfinite(governing.strength_ratio):
        raise ValueError("The variable loads produce no stress that can reach the criterion")
    total = fixed.as_vector() + governing.strength_ratio * variable.as_vector()
    return FirstPlyFailure(
        criterion=criterion,
        strength_ratio=governing.strength_ratio,
        governing=governing,
        failure_loads=Loads(**dict(zip(("Nx", "Ny", "Nxy", "Mx", "My", "Mxy"), total))),
        checks=checks,
    )
