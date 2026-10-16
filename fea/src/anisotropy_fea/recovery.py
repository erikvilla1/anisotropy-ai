"""Ply stresses in material axes and first-ply failure, per element, through the engine (ADR-0029, chunk 3).

A membrane state has no curvature, so every ply of an element carries the same strain and the
engine's `ply_surfaces` with zero curvature gives each ply's strain and stress in laminate and material
axes; the bottom and top faces are equal and one value per ply is kept. The strength ratio of each ply
comes from the engine's criterion dispatcher, so the four criteria mean exactly what they mean in a
laminate analysis. The problem is linear, so the smallest ratio over the mesh is the factor on the
applied displacement or load at which the first ply fails.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from anisotropy_engine.failure import CRITERIA, check_criterion, face_strength_ratio
from anisotropy_engine.response import PlySurface, ply_surfaces

from .mesh import KernelError
from .model import Deck, ElementKey
from .results import MembraneSolution

ZERO = np.zeros(3)
TIE_TOLERANCE = 1e-9  # relative: ratios this close to the minimum count as tied and are resolved by position


@dataclass(frozen=True)
class PlyField:
    """Per element, per ply (bottom first): strain and stress in laminate (xy) and material (12) axes, SI."""

    angles_deg: list[np.ndarray]  # element -> (plies,)
    strain_xy: list[np.ndarray]  # element -> (plies, 3)
    stress_xy: list[np.ndarray]  # Pa
    strain_12: list[np.ndarray]
    stress_12: list[np.ndarray]  # Pa


@dataclass(frozen=True)
class FailureField:
    """Strength ratio of every ply of every element by one criterion, and the first ply to fail."""

    criterion: str
    ratio: list[np.ndarray]  # element -> (plies,), R such that R times the applied loading fails that ply
    mode: list[list[str]]  # element -> governing mode per ply ("F1t", ..., or "interactive")
    factor: float  # the smallest ratio: the first-ply-failure factor on the applied displacement or load
    element: ElementKey
    ply: int  # bottom ply is 1
    governing_mode: str


def element_ply_states(solution: MembraneSolution) -> PlyField:
    """Each element's centroid strain pushed through its plies with zero curvature."""
    mesh = solution.mesh
    angles, strain_xy, stress_xy, strain_12, stress_12 = [], [], [], [], []
    for e in range(mesh.element_count):
        plies = mesh.sections[mesh.element_section[e]].plies
        bottoms = ply_surfaces(plies, solution.strain[e], ZERO)[0::2]  # one face per ply; the top face is identical
        angles.append(np.array([surface.angle_deg for surface in bottoms]))
        strain_xy.append(np.array([surface.strain_xy for surface in bottoms]))
        stress_xy.append(np.array([surface.stress_xy for surface in bottoms]))
        strain_12.append(np.array([surface.strain_12 for surface in bottoms]))
        stress_12.append(np.array([surface.stress_12 for surface in bottoms]))
    return PlyField(angles_deg=angles, strain_xy=strain_xy, stress_xy=stress_xy, strain_12=strain_12, stress_12=stress_12)


def deck_f12_star(deck: Deck) -> float | None:
    """The Tsai-Wu interaction term the deck states (`*Fail Stress` sixth value), if every material states the same one."""
    values = {material.fail_stress.f_star for material in deck.materials.values() if material.fail_stress is not None}
    values.discard(None)
    if len(values) > 1:
        raise KernelError(f"materials state different Tsai-Wu f* values {sorted(values)}; the kernel takes one per model")
    return values.pop() if values else None


def strength_ratios(solution: MembraneSolution, criterion: str, f12_star: float | None = None,
                    ply_field: PlyField | None = None) -> FailureField:
    """Every ply's strength ratio by the engine's criterion functions, and the first ply to fail over the mesh."""
    if criterion not in CRITERIA:
        raise KernelError(f"unknown failure criterion {criterion!r}; use one of {', '.join(CRITERIA)}")
    mesh = solution.mesh
    for section in mesh.sections:
        try:
            check_criterion(section.plies, criterion, f12_star)
        except ValueError as exc:
            raise KernelError(f"section {section.name!r}: {exc}") from None
    field = ply_field if ply_field is not None else element_ply_states(solution)
    ratios: list[np.ndarray] = []
    modes: list[list[str]] = []
    for e in range(mesh.element_count):
        plies = mesh.sections[mesh.element_section[e]].plies
        element_ratios = np.empty(len(plies))
        element_modes = []
        for k, ply in enumerate(plies):
            loaded = PlySurface(k, ply.angle_deg, 0.0, field.strain_xy[e][k], field.stress_xy[e][k], field.strain_12[e][k], field.stress_12[e][k])
            unloaded = PlySurface(k, ply.angle_deg, 0.0, ZERO, ZERO, ZERO, ZERO)
            ratio, mode = face_strength_ratio(criterion, ply.material, unloaded, loaded, f12_star)
            element_ratios[k] = ratio
            element_modes.append(mode)
        ratios.append(element_ratios)
        modes.append(element_modes)
    factor = float(min(r.min() for r in ratios))
    # Ties (identical plies in a uniform state) are decided by position, not roundoff: the first element in deck order,
    # then the bottom-most ply, among all ratios within TIE_TOLERANCE of the minimum.
    for e, element_ratios in enumerate(ratios):
        tied = np.flatnonzero(element_ratios <= factor * (1.0 + TIE_TOLERANCE))
        if tied.size:
            k = int(tied[0])
            return FailureField(criterion=criterion, ratio=ratios, mode=modes, factor=factor, element=mesh.element_keys[e], ply=k + 1,
                                governing_mode=modes[e][k])
    raise KernelError("no ply has a finite strength ratio; the mesh is unstressed")  # pragma: no cover
