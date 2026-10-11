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
from .lamina import Lamina, StrainLimits, Strengths, reduced_compliance
from .laminate import Ply
from .response import Loads, PlySurface, midplane_response, ply_surfaces
from .thermal import thermal_ply_surfaces, thermomechanical_response

Criterion = Literal["max_stress", "max_strain", "tsai_hill", "tsai_wu"]
CRITERIA: tuple[Criterion, ...] = ("max_stress", "max_strain", "tsai_hill", "tsai_wu")


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


def max_strain_ratio(strain_12: np.ndarray, limits: StrainLimits) -> tuple[float, str]:
    """Smallest strength ratio over the five maximum-strain limits, and the mode that governs.

    strain_12 is the mechanical strain in fiber axes [eps1, eps2, gamma12] (Daniel & Ishai
    Eq. 6.6): the strain the stresses produce, not the free thermal strain.
    """
    return max_strain_ratio_combined(np.zeros(3), strain_12, limits)


def max_strain_ratio_combined(fixed_12: np.ndarray, variable_12: np.ndarray, limits: StrainLimits) -> tuple[float, str]:
    """Smallest R >= 0 at which the mechanical strain fixed_12 + R * variable_12 reaches a strain limit.

    Same structure as max_stress_ratio_combined: strain is linear in the loads, so each limit
    gives one ratio and the smallest governs. R = 0 means the fixed strain alone reaches a limit.
    """
    s1, s2, s6 = finite_vector(fixed_12, "fixed_12")
    v1, v2, v6 = finite_vector(variable_12, "variable_12")
    candidates = []
    for fixed, variable, tension, compression, modes in (
        (s1, v1, limits.eps1t, limits.eps1c, ("longitudinal tensile strain", "longitudinal compressive strain")),
        (s2, v2, limits.eps2t, limits.eps2c, ("transverse tensile strain", "transverse compressive strain")),
        (s6, v6, limits.gamma12, limits.gamma12, ("in-plane shear strain", "in-plane shear strain")),
    ):
        if fixed >= tension:
            candidates.append((0.0, modes[0]))
        elif fixed <= -compression:
            candidates.append((0.0, modes[1]))
        elif variable > 0:
            candidates.append(((tension - fixed) / variable, modes[0]))
        elif variable < 0:
            candidates.append(((-compression - fixed) / variable, modes[1]))
    return min(candidates, key=lambda limit: limit[0]) if candidates else (math.inf, "none")


def _tsai_hill_quadratic(x, y, X: float, Y: float, S: float) -> float:
    """Bilinear form of the Tsai-Hill criterion (Daniel & Ishai Eq. 6.16) with chosen X and Y."""
    return x[0] * y[0] / X**2 - (x[0] * y[1] + x[1] * y[0]) / (2 * X**2) + x[1] * y[1] / Y**2 + x[2] * y[2] / S**2


def tsai_hill_index(stress_12: np.ndarray, strengths: Strengths) -> float:
    """Tsai-Hill failure index (Daniel & Ishai Eq. 6.16), plane stress.

    FI = (s1/X)^2 - s1 s2/X^2 + (s2/Y)^2 + (t12/S)^2 with X = F1t or F1c by the sign of s1 and
    Y = F2t or F2c by the sign of s2. Failure at FI = 1. Zero stress selects the tensile strengths.
    """
    s = finite_vector(stress_12, "stress_12")
    st = strengths
    X = st.F1c if s[0] < 0 else st.F1t
    Y = st.F2c if s[1] < 0 else st.F2t
    return _tsai_hill_quadratic(s, s, X, Y, st.F6)


def tsai_hill_ratio(stress_12: np.ndarray, strengths: Strengths) -> float:
    """Load multiplier at which the Tsai-Hill index reaches 1: R = 1/sqrt(FI), since the index is
    a homogeneous quadratic and scaling the load does not change the strength selection."""
    index = tsai_hill_index(stress_12, strengths)
    return 1 / math.sqrt(index) if index > 0 else math.inf


def tsai_hill_ratio_combined(fixed_12: np.ndarray, variable_12: np.ndarray, strengths: Strengths) -> float:
    """Smallest R >= 0 at which the Tsai-Hill index of fixed_12 + R * variable_12 reaches 1.

    The strengths X and Y depend on the signs of the stresses at failure, which are not known
    in advance when a fixed stress and a variable stress have opposite signs. Each of the four
    sign choices gives a quadratic a R^2 + b R + c = 0; a root counts only when the stress at
    that root has the signs assumed. The smallest such root governs. R = 0 when the fixed
    stresses alone reach the criterion.
    """
    s = finite_vector(fixed_12, "fixed_12")
    v = finite_vector(variable_12, "variable_12")
    st = strengths
    if tsai_hill_index(s, st) >= 1:
        return 0.0
    roots = []
    for X, sign1 in ((st.F1t, 1), (st.F1c, -1)):
        for Y, sign2 in ((st.F2t, 1), (st.F2c, -1)):
            a = _tsai_hill_quadratic(v, v, X, Y, st.F6)
            b = 2 * _tsai_hill_quadratic(s, v, X, Y, st.F6)
            c = _tsai_hill_quadratic(s, s, X, Y, st.F6) - 1
            if a > 0:
                candidates = [(-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)] if b * b - 4 * a * c >= 0 else []
            elif b > 0:
                candidates = [-c / b]
            else:
                candidates = []
            for r in candidates:
                if r < 0:
                    continue
                at_failure = s + r * v
                if (at_failure[0] * sign1 >= 0 or at_failure[0] == 0) and (at_failure[1] * sign2 >= 0 or at_failure[1] == 0):
                    roots.append(r)
    return min(roots) if roots else math.inf


def _mechanical_strain_12(material: Lamina, stress_12: np.ndarray) -> np.ndarray:
    """Strain the stresses produce in fiber axes; with a temperature change this excludes the free thermal strain."""
    return reduced_compliance(material) @ stress_12


def _check_criterion(plies: list[Ply], criterion: str, f12_star: float | None) -> None:
    if criterion not in CRITERIA:
        raise ValueError(f"Unknown criterion {criterion!r}; use one of {CRITERIA}")
    if criterion == "tsai_wu" and f12_star is None:
        raise ValueError("Tsai-Wu needs an explicit f12_star, measured or assumed")
    if criterion == "max_strain":
        missing = [k for k, ply in enumerate(plies) if ply.material.strain_limits is None]
        if missing:
            raise ValueError(f"Plies {missing} have no strain limits; give them or state strain_limits = \"from-strengths\"")
    else:
        missing = [k for k, ply in enumerate(plies) if ply.material.strengths is None]
        if missing:
            raise ValueError(f"Plies {missing} have no strengths")


def _face_ratio(criterion: str, material: Lamina, held: PlySurface, scaled: PlySurface, f12_star: float | None) -> tuple[float, str]:
    """Strength ratio on one face for fixed + R * variable stress, by the chosen criterion."""
    if criterion == "max_stress":
        return max_stress_ratio_combined(held.stress_12, scaled.stress_12, material.strengths)
    if criterion == "max_strain":
        return max_strain_ratio_combined(_mechanical_strain_12(material, held.stress_12),
                                         _mechanical_strain_12(material, scaled.stress_12), material.strain_limits)
    if criterion == "tsai_hill":
        return tsai_hill_ratio_combined(held.stress_12, scaled.stress_12, material.strengths), "interactive"
    return tsai_wu_ratio_combined(held.stress_12, scaled.stress_12, material.strengths, f12_star), "interactive"


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
    _check_criterion(plies, criterion, f12_star)
    if not np.any(loads.as_vector()):
        raise ValueError("Apply at least one nonzero load")

    eps0, kappa = midplane_response(plies, loads)
    checks = []
    zero = np.zeros(3)
    for surface in ply_surfaces(plies, eps0, kappa):
        material = plies[surface.ply_index].material
        unloaded = PlySurface(surface.ply_index, surface.angle_deg, surface.z_m, zero, zero, zero, zero)
        ratio, mode = _face_ratio(criterion, material, unloaded, surface, f12_star)
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
    _check_criterion(plies, criterion, f12_star)
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
        ratio, mode = _face_ratio(criterion, plies[held.ply_index].material, held, scaled, f12_star)
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
