"""Facts of a stack, not a response: thickness, symmetry, balance, kind, coupling, areal mass,
and first-ply failure under the one loading given, as the response endpoint reports them (ADR-0059).

Everything here is derived from the plies and the matrices the other modules compute. A flag
that compares a matrix entry with zero uses one relative tolerance, so roundoff in a symmetric
stack never reads as coupling. Plies are listed from the bottom face up (ADR-0004). Nothing is
assumed: a density the material does not carry leaves the areal mass out with the reason, and a
criterion the inputs cannot support is reported as not computed with the engine's own message.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .failure import CRITERIA, PlyCheck, check_criterion, first_ply_failure
from .laminate import Ply, abd_matrices, ply_interfaces
from .response import Loads

# An entry counts as zero when it is at most this fraction of its matrix's largest entry: the
# relative tolerance of the forward verification (ADR-0013). Angles compare in degrees, thicknesses
# relative to the larger of the two.
RELATIVE_TOLERANCE = 1e-9
ANGLE_TOLERANCE_DEG = 1e-9

Kind = Literal["unidirectional", "cross-ply", "angle-ply", "quasi-isotropic", "general"]
Face = Literal["bottom", "top"]


def _angle_difference_deg(a: float, b: float) -> float:
    """The smallest angle between two fiber directions; a fiber at theta is the fiber at theta + 180."""
    difference = (a - b) % 180.0
    return min(difference, 180.0 - difference)


def _same_angle(a: float, b: float) -> bool:
    return _angle_difference_deg(a, b) <= ANGLE_TOLERANCE_DEG


def _same_thickness(a: float, b: float) -> bool:
    return abs(a - b) <= RELATIVE_TOLERANCE * max(a, b)


def _same_ply(p: Ply, q: Ply) -> bool:
    return p.material == q.material and _same_angle(p.angle_deg, q.angle_deg) and _same_thickness(p.thickness_m, q.thickness_m)


def _mirrored_ply(p: Ply, q: Ply) -> bool:
    """Same material and thickness, the fiber at the opposite angle."""
    return p.material == q.material and _same_angle(p.angle_deg, -q.angle_deg) and _same_thickness(p.thickness_m, q.thickness_m)


def _on_axis(angle_deg: float) -> bool:
    """A 0 or 90 degree ply is its own mirror image."""
    return _same_angle(angle_deg, 0.0) or _same_angle(angle_deg, 90.0)


def total_thickness(plies: list[Ply]) -> float:
    """h = sum of the ply thicknesses, in m."""
    if not plies:
        raise ValueError("A laminate needs at least one ply")
    return float(sum(ply.thickness_m for ply in plies))


def is_symmetric(plies: list[Ply]) -> bool:
    """Ply k and ply n - 1 - k are the same ply: material, fiber angle and thickness. The middle ply of an
    odd count mirrors itself. A symmetric laminate has B = 0 (Daniel & Ishai Section 7.7)."""
    n = len(plies)
    return all(_same_ply(plies[k], plies[n - 1 - k]) for k in range(n // 2))


def is_antisymmetric(plies: list[Ply]) -> bool:
    """Ply k and ply n - 1 - k have the same material and thickness and opposite fiber angles, and the stack
    is not symmetric: at least one mirrored pair is off axis. A symmetric cross-ply stack, where every mirrored
    pair is at 0 or 90, is reported symmetric, not antisymmetric."""
    n = len(plies)
    pairs = [(plies[k], plies[n - 1 - k]) for k in range(n // 2)]
    if not all(_mirrored_ply(p, q) for p, q in pairs):
        return False
    if n % 2 and not _on_axis(plies[n // 2].angle_deg):
        return False
    return any(not _on_axis(p.angle_deg) for p, _ in pairs)


def is_balanced(plies: list[Ply]) -> bool:
    """Every off-axis ply at +theta has a partner at -theta of the same material and thickness, anywhere in the
    stack; plies at 0 and 90 need none. A balanced laminate has A16 = A26 = 0 (Daniel & Ishai Section 7.8)."""
    unmatched = [ply for ply in plies if not _on_axis(ply.angle_deg)]
    while unmatched:
        ply = unmatched.pop()
        partner = next((k for k, other in enumerate(unmatched) if _mirrored_ply(ply, other)), None)
        if partner is None:
            return False
        del unmatched[partner]
    return True


def _is_zero(value: float, scale: float, tolerance: float) -> bool:
    return abs(value) <= tolerance * scale


def laminate_kind(plies: list[Ply], A: np.ndarray, tolerance: float = RELATIVE_TOLERANCE) -> Kind:
    """The textbook name of the stack, judged first on A and then on the angles.

    Quasi-isotropic when A is isotropic to the tolerance: A11 = A22, A16 = A26 = 0 and A66 = (A11 - A12) / 2
    (Daniel & Ishai Section 7.10). Otherwise unidirectional (one fiber angle), cross-ply (only 0 and 90),
    angle-ply (only +theta and -theta), or general.
    """
    A = np.asarray(A, dtype=float)
    scale = float(np.abs(A).max())
    if (_is_zero(A[0, 0] - A[1, 1], scale, tolerance) and _is_zero(A[0, 2], scale, tolerance)
            and _is_zero(A[1, 2], scale, tolerance) and _is_zero(A[2, 2] - (A[0, 0] - A[0, 1]) / 2, scale, tolerance)):
        return "quasi-isotropic"
    distinct: list[float] = []
    for ply in plies:
        if not any(_same_angle(ply.angle_deg, angle) for angle in distinct):
            distinct.append(ply.angle_deg)
    if len(distinct) == 1:
        return "unidirectional"
    if all(_on_axis(angle) for angle in distinct):
        return "cross-ply"
    if len(distinct) == 2 and _same_angle(distinct[0], -distinct[1]):
        return "angle-ply"
    return "general"


@dataclass(frozen=True)
class Coupling:
    """Which couplings the matrices show, each judged to the tolerance."""

    extension_shear: bool  # A16 or A26 nonzero: an axial load shears the laminate
    extension_bending: bool  # any B nonzero: an in-plane load bends it
    bending_twisting: bool  # D16 or D26 nonzero: a bending moment twists it


def coupling_flags(A: np.ndarray, B: np.ndarray, D: np.ndarray, thickness_m: float,
                   tolerance: float = RELATIVE_TOLERANCE) -> Coupling:
    """A16 and A26 are judged against the largest entry of A, D16 and D26 against the largest entry of D, and B
    against max|A| h / 2, the size B would have if the whole stiffness sat on one face: B is exactly zero for a
    symmetric stack, so its own largest entry is no scale."""
    A, B, D = (np.asarray(m, dtype=float) for m in (A, B, D))
    a_scale, d_scale, b_scale = float(np.abs(A).max()), float(np.abs(D).max()), float(np.abs(A).max()) * thickness_m / 2
    return Coupling(
        extension_shear=not (_is_zero(A[0, 2], a_scale, tolerance) and _is_zero(A[1, 2], a_scale, tolerance)),
        extension_bending=not _is_zero(float(np.abs(B).max()), b_scale, tolerance),
        bending_twisting=not (_is_zero(D[0, 2], d_scale, tolerance) and _is_zero(D[1, 2], d_scale, tolerance)),
    )


def areal_mass(plies: list[Ply], densities_kg_per_m3: Sequence[float | None]) -> float:
    """Mass per unit area, sum of density times thickness over the plies, in kg/m^2.

    Every ply needs a finite positive density; the plies without one are named (ADR-0003).
    """
    if len(densities_kg_per_m3) != len(plies):
        raise ValueError(f"{len(plies)} plies need {len(plies)} densities, got {len(densities_kg_per_m3)}")
    missing = [k + 1 for k, rho in enumerate(densities_kg_per_m3) if rho is None]
    if missing:
        raise ValueError(f"plies {missing} have no density")
    bad = [k + 1 for k, rho in enumerate(densities_kg_per_m3) if not math.isfinite(rho) or rho <= 0]
    if bad:
        raise ValueError(f"plies {bad} have a density that is not a finite positive number")
    return float(sum(rho * ply.thickness_m for rho, ply in zip(densities_kg_per_m3, plies)))


@dataclass(frozen=True)
class LaminateSummary:
    """What the stack is, before any load: counts, symmetry, kind, coupling and mass per area."""

    ply_count: int
    total_thickness_m: float
    symmetric: bool
    antisymmetric: bool
    balanced: bool
    kind: Kind
    coupling: Coupling
    areal_mass_kg_per_m2: float | None  # None when a ply's material has no density; the reason is beside it
    areal_mass_missing: str | None
    tolerance: float


def laminate_summary(plies: list[Ply], densities_kg_per_m3: Sequence[float | None] | None = None,
                     tolerance: float = RELATIVE_TOLERANCE) -> LaminateSummary:
    """Describe the stack from its plies and its A, B, D. Without densities the areal mass is left out, with the reason."""
    h = total_thickness(plies)
    A, B, D = abd_matrices(plies)
    densities = list(densities_kg_per_m3) if densities_kg_per_m3 is not None else [None] * len(plies)
    mass: float | None
    try:
        mass, missing = areal_mass(plies, densities), None
    except ValueError as error:
        mass, missing = None, str(error)
    return LaminateSummary(
        ply_count=len(plies), total_thickness_m=h,
        symmetric=is_symmetric(plies), antisymmetric=is_antisymmetric(plies), balanced=is_balanced(plies),
        kind=laminate_kind(plies, A, tolerance), coupling=coupling_flags(A, B, D, h, tolerance),
        areal_mass_kg_per_m2=mass, areal_mass_missing=missing, tolerance=tolerance,
    )


def face_of(plies: list[Ply], check: PlyCheck) -> Face:
    """Which face of its ply a check sits on: the ply's interfaces are at z[k] (bottom) and z[k + 1] (top)."""
    z = ply_interfaces(plies)
    bottom, top = z[check.ply_index], z[check.ply_index + 1]
    if abs(check.z_m - bottom) <= abs(check.z_m - top):
        return "bottom"
    return "top"


@dataclass(frozen=True)
class CriterionResult:
    """First-ply failure by one criterion: the strength ratio and where the first ply fails."""

    criterion: str
    strength_ratio: float | None  # None when no face reaches the criterion under these loads
    ply_number: int  # 1 at the bottom
    angle_deg: float
    face: Face
    z_m: float
    mode: str
    failure_loads: Loads


@dataclass(frozen=True)
class NotComputed:
    criterion: str
    reason: str


@dataclass(frozen=True)
class FailureSummary:
    """First-ply failure under the loads given, by every criterion the inputs support.

    evaluated is False, with the reason, when there is no load to scale or a ply has no strengths.
    Each criterion the inputs cannot support is listed under not_computed with the engine's message.
    """

    evaluated: bool
    reason: str | None
    results: tuple[CriterionResult, ...]
    not_computed: tuple[NotComputed, ...]


def first_ply_failure_summary(plies: list[Ply], loads: Loads, f12_star: float | None = None) -> FailureSummary:
    """First-ply failure with every load scaling together (nothing held fixed, no temperature change).

    Maximum stress and Tsai-Hill run whenever the plies have strengths; maximum strain needs strain limits and
    Tsai-Wu an explicit f12_star, and without them they are reported as not computed, never assumed (ADR-0021).
    """
    if not np.any(loads.as_vector()):
        return FailureSummary(False, "no loads applied", (), ())
    missing = [k + 1 for k, ply in enumerate(plies) if ply.material.strengths is None]
    if missing:
        return FailureSummary(False, f"plies {missing} have no strengths", (), ())
    results: list[CriterionResult] = []
    skipped: list[NotComputed] = []
    for criterion in CRITERIA:
        try:
            check_criterion(plies, criterion, f12_star)
            fpf = first_ply_failure(plies, loads, criterion, f12_star)
        except ValueError as error:
            skipped.append(NotComputed(criterion, str(error)))
            continue
        governing = fpf.governing
        ratio = float(fpf.strength_ratio) if math.isfinite(fpf.strength_ratio) else None
        results.append(CriterionResult(
            criterion=criterion, strength_ratio=ratio, ply_number=governing.ply_index + 1,
            angle_deg=float(governing.angle_deg), face=face_of(plies, governing), z_m=float(governing.z_m),
            mode=governing.mode, failure_loads=fpf.failure_loads,
        ))
    return FailureSummary(True, None, tuple(results), tuple(skipped))
