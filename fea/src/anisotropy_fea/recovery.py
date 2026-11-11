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

from anisotropy_engine.failure import CRITERIA, check_criterion, scaled_strength_ratios
from anisotropy_engine.response import ply_surface_arrays

from .mesh import KernelError
from .model import Deck, ElementKey
from .results import MembraneSolution, ShellSolution, Solution

FACES = ("bottom", "top")  # the two faces of a ply in a shell state, in the order the engine lists them
TIE_TOLERANCE = 1e-9  # relative: ratios this close to the minimum count as tied and are resolved by position


@dataclass(frozen=True)
class PlyField:
    """Per element, per ply (bottom first): strain and stress in laminate (xy) and material (12) axes, SI. In a membrane state each
    array is (plies, 3); in a shell state it is (plies, 2, 3), the bottom face then the top face of every ply, and `faces` says so."""

    angles_deg: list[np.ndarray]  # element -> (plies,): the angles the deck states, for the labels; the 1-2 state is in the fibre axes (ADR-0065)
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
    element's curvature for a shell state, both faces of every ply. The engine takes every element of a section in one call
    (`ply_surface_arrays`, ADR-0073), the same numbers as one `ply_surfaces` call per element."""
    mesh = solution.mesh
    shell = isinstance(solution, ShellSolution)
    count = mesh.element_count
    angles: list = [None] * count
    strain_xy: list = [None] * count
    stress_xy: list = [None] * count
    strain_12: list = [None] * count
    stress_12: list = [None] * count
    element_section = np.asarray(mesh.element_section)
    for s, section in enumerate(mesh.sections):
        members = np.flatnonzero(element_section == s)
        if not members.size:
            continue
        curvature = solution.curvature[members] if shell else np.zeros((members.size, 3))
        states = ply_surface_arrays(section.plies, solution.strain[members], curvature)
        if not shell:
            states = tuple(state[:, :, 0] for state in states)  # one face per ply; the top face is identical
        for i, e in enumerate(members.tolist()):
            angles[e] = np.array(section.angles_deg, dtype=float)  # the stated angles; the engine rotates by the plies' own fibre angles
            strain_xy[e] = states[0][i].copy()
            stress_xy[e] = states[1][i].copy()
            strain_12[e] = states[2][i].copy()
            stress_12[e] = states[3][i].copy()
    return PlyField(angles_deg=angles, strain_xy=strain_xy, stress_xy=stress_xy, strain_12=strain_12, stress_12=stress_12,
                    faces=FACES if shell else None)


INVARIANTS = ("tresca", "max_principal", "mid_principal", "min_principal", "pressure")


def ply_invariants(field: PlyField) -> dict[str, list[np.ndarray]]:
    """What Abaqus prints beside Mises for a shell section point (ADR-0066 amendment 2), of each ply's in-plane state with the stress
    through the thickness zero (plane stress), element -> (plies,) or (plies, 2): the three principal stresses ordered with that zero
    among them, Tresca, the largest less the smallest of the three, and the pressure, minus their mean. Each is an invariant, the same
    in laminate or material axes; they are comparison quantities, not a composite's failure criterion."""
    out: dict[str, list[np.ndarray]] = {name: [] for name in INVARIANTS}
    for s in field.stress_12:
        s11, s22, s12 = s[..., 0], s[..., 1], s[..., 2]
        centre, radius = (s11 + s22) / 2.0, np.sqrt(((s11 - s22) / 2.0) ** 2 + s12 ** 2)
        principals = np.sort(np.stack([centre + radius, centre - radius, np.zeros_like(s11)], axis=-1), axis=-1)
        out["max_principal"].append(principals[..., 2])
        out["mid_principal"].append(principals[..., 1])
        out["min_principal"].append(principals[..., 0])
        out["tresca"].append(principals[..., 2] - principals[..., 0])
        out["pressure"].append(-(s11 + s22) / 3.0)
    return out


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
    count = mesh.element_count
    ratios: list = [None] * count
    modes: list = [None] * count
    element_section = np.asarray(mesh.element_section)
    for s, section in enumerate(mesh.sections):
        members = np.flatnonzero(element_section == s).tolist()
        if not members:
            continue
        plies = section.plies
        stress = np.stack([np.asarray(field.stress_12[e]) for e in members])  # (m, plies, 3) or (m, plies, faces, 3)
        ratio = np.empty(stress.shape[:-1])
        mode = np.empty(stress.shape[:-1], dtype=object)
        for k, ply in enumerate(plies):
            # Every element's ply k (each face in a shell state) in one engine call: `face_strength_ratio` with nothing held, row by row.
            rows = stress[:, k].reshape(-1, 3)
            r, m = scaled_strength_ratios(criterion, ply.material, rows, f12_star)
            ratio[:, k] = r.reshape(ratio[:, k].shape)
            mode[:, k] = np.array(m, dtype=object).reshape(ratio[:, k].shape)
        for i, e in enumerate(members):
            ratios[e] = ratio[i].copy()
            modes[e] = mode[i].tolist()
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
