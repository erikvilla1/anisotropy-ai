"""Ply stresses in material axes and first-ply failure, per element, through the engine (ADR-0029, chunk 3; faces since ADR-0053).

A membrane state has no curvature, so every ply of an element carries the same strain and the engine's `ply_surfaces` with zero
curvature gives each ply's strain and stress in laminate and material axes; the bottom and top faces are equal and one value per
ply is kept. A shell state carries a curvature too, so each ply's strain varies through its thickness and both faces are kept, the
bottom face first. The strength ratio of each ply, or of each face, comes from the engine's criterion dispatcher, so the four
criteria mean exactly what they mean in a laminate analysis. The problem is linear, so the smallest ratio over the mesh is the factor
on the applied displacement or load at which the first ply fails.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from anisotropy_engine.failure import CRITERIA, check_criterion, face_strength_ratio
from anisotropy_engine.response import PlySurface, ply_surfaces

from .mesh import KernelError
from .model import Deck, ElementKey
from .results import MembraneSolution, ShellSolution, Solution

ZERO = np.zeros(3)
FACES = ("bottom", "top")  # the two faces of a ply in a shell state, in the order the engine lists them
TIE_TOLERANCE = 1e-9  # relative: ratios this close to the minimum count as tied and are resolved by position


@dataclass(frozen=True)
class PlyField:
    """Per element, per ply (bottom first): strain and stress in laminate (xy) and material (12) axes, SI. In a membrane state each
    array is (plies, 3); in a shell state it is (plies, 2, 3), the bottom face then the top face of every ply, and `faces` says so."""

    angles_deg: list[np.ndarray]  # element -> (plies,)
    strain_xy: list[np.ndarray]  # element -> (plies, 3) or (plies, 2, 3)
    stress_xy: list[np.ndarray]  # Pa
    strain_12: list[np.ndarray]
    stress_12: list[np.ndarray]  # Pa
    faces: tuple[str, ...] | None = None  # None for one state per ply; FACES for a shell state


@dataclass(frozen=True)
class FailureField:
    """Strength ratio of every ply of every element by one criterion, and the first ply to fail."""

    criterion: str
    ratio: list[np.ndarray]  # element -> (plies,) or (plies, 2): R such that R times the applied loading fails that ply (face)
    mode: list[list]  # element -> governing mode per ply ("F1t", ..., or "interactive"), per face in a shell state
    factor: float  # the smallest ratio: the first-ply-failure factor on the applied displacement or load
    element: ElementKey
    ply: int  # bottom ply is 1
    governing_mode: str
    face: str | None = None  # the face of the first ply to fail in a shell state; None in a membrane state


def ply_ratio_per_ply(ratio: np.ndarray) -> np.ndarray:
    """One ratio per ply: the array itself for a membrane state, the smaller face for a shell state."""
    ratio = np.asarray(ratio)
    return ratio.min(axis=1) if ratio.ndim == 2 else ratio


def element_ply_states(solution: Solution) -> PlyField:
    """Each element's centroid strain pushed through its plies: with zero curvature for a membrane state, one face per ply; with the
    element's curvature for a shell state, both faces of every ply."""
    mesh = solution.mesh
    shell = isinstance(solution, ShellSolution)
    angles, strain_xy, stress_xy, strain_12, stress_12 = [], [], [], [], []
    for e in range(mesh.element_count):
        plies = mesh.sections[mesh.element_section[e]].plies
        if shell:
            surfaces = ply_surfaces(plies, solution.strain[e], solution.curvature[e])
            pairs = [surfaces[2 * k: 2 * k + 2] for k in range(len(plies))]
            angles.append(np.array([pair[0].angle_deg for pair in pairs]))
            strain_xy.append(np.array([[s.strain_xy for s in pair] for pair in pairs]))
            stress_xy.append(np.array([[s.stress_xy for s in pair] for pair in pairs]))
            strain_12.append(np.array([[s.strain_12 for s in pair] for pair in pairs]))
            stress_12.append(np.array([[s.stress_12 for s in pair] for pair in pairs]))
        else:
            bottoms = ply_surfaces(plies, solution.strain[e], ZERO)[0::2]  # one face per ply; the top face is identical
            angles.append(np.array([surface.angle_deg for surface in bottoms]))
            strain_xy.append(np.array([surface.strain_xy for surface in bottoms]))
            stress_xy.append(np.array([surface.stress_xy for surface in bottoms]))
            strain_12.append(np.array([surface.strain_12 for surface in bottoms]))
            stress_12.append(np.array([surface.stress_12 for surface in bottoms]))
    return PlyField(angles_deg=angles, strain_xy=strain_xy, stress_xy=stress_xy, strain_12=strain_12, stress_12=stress_12,
                    faces=FACES if shell else None)


def ply_mises(field: PlyField) -> list[np.ndarray]:
    """Von Mises stress of each ply's in-plane state, element -> (plies, 1) or (plies, 2, 1): an invariant, so the same in laminate or
    material axes; Abaqus's S-Mises at a shell section point is this plane-stress value."""
    out = []
    for s in field.stress_12:
        out.append(np.sqrt(s[..., 0] ** 2 - s[..., 0] * s[..., 1] + s[..., 1] ** 2 + 3.0 * s[..., 2] ** 2)[..., None])
    return out


def deck_f12_star(deck: Deck) -> float | None:
    """The Tsai-Wu interaction term the deck states (`*Fail Stress` sixth value), if every material states the same one."""
    values = {material.fail_stress.f_star for material in deck.materials.values() if material.fail_stress is not None}
    values.discard(None)
    if len(values) > 1:
        raise KernelError(f"materials state different Tsai-Wu f* values {sorted(values)}; the kernel takes one per model")
    return values.pop() if values else None


def _ratio(criterion: str, ply, k: int, strain_xy, stress_xy, strain_12, stress_12, f12_star) -> tuple[float, str]:
    loaded = PlySurface(k, ply.angle_deg, 0.0, strain_xy, stress_xy, strain_12, stress_12)
    unloaded = PlySurface(k, ply.angle_deg, 0.0, ZERO, ZERO, ZERO, ZERO)
    return face_strength_ratio(criterion, ply.material, unloaded, loaded, f12_star)


def strength_ratios(solution: Solution, criterion: str, f12_star: float | None = None, ply_field: PlyField | None = None) -> FailureField:
    """Every ply's strength ratio by the engine's criterion functions, on both faces in a shell state, and the first ply to fail over the mesh."""
    if criterion not in CRITERIA:
        raise KernelError(f"unknown failure criterion {criterion!r}; use one of {', '.join(CRITERIA)}")
    mesh = solution.mesh
    for section in mesh.sections:
        try:
            check_criterion(section.plies, criterion, f12_star)
        except ValueError as exc:
            raise KernelError(f"section {section.name!r}: {exc}") from None
    field = ply_field if ply_field is not None else element_ply_states(solution)
    faces = field.faces
    ratios: list[np.ndarray] = []
    modes: list[list] = []
    for e in range(mesh.element_count):
        plies = mesh.sections[mesh.element_section[e]].plies
        if faces is None:
            element_ratios = np.empty(len(plies))
            element_modes = []
            for k, ply in enumerate(plies):
                ratio, mode = _ratio(criterion, ply, k, field.strain_xy[e][k], field.stress_xy[e][k], field.strain_12[e][k], field.stress_12[e][k], f12_star)
                element_ratios[k] = ratio
                element_modes.append(mode)
        else:
            element_ratios = np.empty((len(plies), len(faces)))
            element_modes = []
            for k, ply in enumerate(plies):
                face_modes = []
                for f in range(len(faces)):
                    ratio, mode = _ratio(criterion, ply, k, field.strain_xy[e][k, f], field.stress_xy[e][k, f], field.strain_12[e][k, f],
                                         field.stress_12[e][k, f], f12_star)
                    element_ratios[k, f] = ratio
                    face_modes.append(mode)
                element_modes.append(face_modes)
        ratios.append(element_ratios)
        modes.append(element_modes)
    factor = float(min(r.min() for r in ratios))
    # Ties (identical plies in a uniform state) are decided by position, not roundoff: the first element in deck order,
    # then the bottom-most ply, then the bottom face, among all ratios within TIE_TOLERANCE of the minimum.
    for e, element_ratios in enumerate(ratios):
        tied = np.argwhere(element_ratios <= factor * (1.0 + TIE_TOLERANCE))
        if tied.size:
            if faces is None:
                k = int(tied[0][0])
                return FailureField(criterion=criterion, ratio=ratios, mode=modes, factor=factor, element=mesh.element_keys[e], ply=k + 1,
                                    governing_mode=modes[e][k])
            k, f = (int(v) for v in tied[0])
            return FailureField(criterion=criterion, ratio=ratios, mode=modes, factor=factor, element=mesh.element_keys[e], ply=k + 1,
                                governing_mode=modes[e][k][f], face=faces[f])
    raise KernelError("no ply has a finite strength ratio; the mesh is unstressed")  # pragma: no cover


__all__ = ["FACES", "FailureField", "MembraneSolution", "PlyField", "deck_f12_star", "element_ply_states", "ply_mises", "ply_ratio_per_ply",
           "strength_ratios"]
