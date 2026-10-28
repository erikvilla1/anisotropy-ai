"""What the studio's viewer shows after a solve (ADR-0051): every field of the solution and a summary of its extremes, as one
JSON-ready dict in the deck's units.

The fields are the kernel's and the engine's (`membrane.solve_membrane`, `recovery.element_ply_states`, `recovery.strength_ratios`):
nodal displacement and reaction; per element the membrane strain, the section forces, every ply's stress and strain in material
and laminate axes, the ply von Mises stress, and per criterion every ply's strength ratio R and failure index 1/R. The browser draws
them and computes nothing. Smooth contours need one value per node, so the mean over the elements that share a node is written here
too, under `nodal.averages`, and labelled a display average: the element values are the result.

The summary names the largest displacement, the largest ply stresses, and per criterion the first ply to fail, with its element,
ply, mode and place in the words the coupon document uses (`report.fpf_place`). Every number comes from the solve; a non-finite one
is refused.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from anisotropy_engine.failure import CRITERIA

from .cases import element_name
from .mesh import KernelError
from .model import Deck, node_name
from .quality import QualityField, quality_summary
from .recovery import FailureField, PlyField, deck_f12_star, element_ply_states, ply_mises, strength_ratios
from .report import fpf_place, gripped_groups
from .results import MembraneSolution
from .units import UNIT_LABEL, from_si

MODES = ("longitudinal tension", "longitudinal compression", "transverse tension", "transverse compression", "in-plane shear", "interactive",
         "none")  # the engine's governing modes; "none" is an unstressed ply, whose ratio is infinite
STRESS_NAMES = ("S11", "S22", "S12")  # the material-axis stress components, as the team's CAE exports name them
DIGITS = 9  # significant digits written for the arrays; the summary keeps full precision


def rounded(values: np.ndarray) -> list:
    """An array as nested lists of floats at DIGITS significant digits; a value JSON cannot carry becomes None: NaN at a node no element
    touches, an infinite strength ratio in an unstressed ply."""
    flat = np.asarray(values, dtype=float).reshape(-1)
    out = [None if not np.isfinite(v) else float(f"{v:.{DIGITS}g}") for v in flat]
    return np.asarray(out, dtype=object).reshape(np.shape(values)).tolist()


def nodal_averages(connectivity: np.ndarray, node_count: int, element_values: np.ndarray) -> np.ndarray:
    """The mean over the elements that share each corner node, for display; NaN at a node no element touches."""
    values = np.asarray(element_values, dtype=float)
    corners = np.asarray(connectivity)[:, :4]
    totals = np.zeros((node_count, *values.shape[1:]))
    counts = np.zeros(node_count)
    for k in range(4):
        np.add.at(totals, corners[:, k], values)
        np.add.at(counts, corners[:, k], 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return totals / counts.reshape((node_count,) + (1,) * (values.ndim - 1))


def _finite(name: str, values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(values)):
        raise KernelError(f"{name} holds a non-finite value; the solve is not usable")
    return values


def applied_loading(deck: Deck, solution: MembraneSolution) -> tuple[str, float]:
    """What the deck applies along the coupon, SI: ("displacement", the pull between the grips in m) or ("force", the summed dof-2 load in N)."""
    bottom, top = gripped_groups(deck, solution)
    pull = float(np.mean(list(top.values())) - np.mean(list(bottom.values())))
    if pull != 0.0:
        return "displacement", pull
    return "force", float(sum(load.value for step in deck.steps for load in step.cloads if load.dof == 2))


def failures_of(deck: Deck, solution: MembraneSolution, field: PlyField, criteria: tuple[str, ...] | None = None) -> dict[str, FailureField]:
    """The strength ratios by every criterion the deck allows, or by the criteria named (each must be computable)."""
    f12_star = deck_f12_star(deck)
    out: dict[str, FailureField] = {}
    for criterion in (criteria if criteria is not None else tuple(c for c in CRITERIA if c != "max_strain")):
        try:
            out[criterion] = strength_ratios(solution, criterion, f12_star, field)
        except KernelError:
            if criteria is not None:
                raise
    return out


def field_data(deck: Deck, solution: MembraneSolution, units: str, criteria: tuple[str, ...] | None = None, quality: QualityField | None = None,
               coupon: dict[str, Any] | None = None) -> dict[str, Any]:
    """The solved deck as the viewer reads it. `criteria` names the first-ply-failure criteria to report (default: every one the deck
    allows); `coupon` is the identity the preview carries, passed through."""
    mesh = solution.mesh
    n, ne = mesh.node_count, mesh.element_count
    lab = UNIT_LABEL[units]
    length = lambda a: from_si(np.asarray(a, dtype=float), "length", units)  # noqa: E731
    stress = lambda a: from_si(np.asarray(a, dtype=float), "stress", units)  # noqa: E731
    per_length = lambda a: from_si(np.asarray(a, dtype=float), "force_per_length", units)  # noqa: E731
    displacement = _finite("displacement", solution.displacement)
    reaction = _finite("reaction", solution.reaction)
    strain = _finite("strain", solution.strain)
    section_force = _finite("section force", solution.section_force)
    field = element_ply_states(solution)
    plies = field.stress_12[0].shape[0]
    if any(s.shape[0] != plies for s in field.stress_12):
        raise KernelError("the elements carry different ply counts; the viewer shows one laminate")
    angles = np.asarray(field.angles_deg[0], dtype=float)
    stress_12 = _finite("ply stress", np.stack(field.stress_12))  # (ne, plies, 3)
    stress_xy = _finite("ply stress", np.stack(field.stress_xy))
    strain_12 = _finite("ply strain", np.stack(field.strain_12))
    mises = _finite("ply Mises", np.stack(ply_mises(field))[:, :, 0])  # (ne, plies)
    failures = failures_of(deck, solution, field, criteria)
    corners = mesh.connectivity[:, :4]
    centroids = mesh.xy[corners].mean(axis=1)
    magnitude = np.linalg.norm(displacement, axis=1)

    failure: dict[str, Any] = {}
    failure_average: dict[str, Any] = {}
    for criterion, found in failures.items():
        ratio = np.stack(found.ratio)  # (ne, plies); infinite in an unstressed ply (a rigidly gripped tab), never NaN
        if np.any(np.isnan(ratio)):
            raise KernelError(f"{criterion} ratio holds a NaN; the solve is not usable")
        mode = [[MODES.index(m) for m in modes] for modes in found.mode]
        with np.errstate(divide="ignore"):
            index = np.where(np.isinf(ratio), 0.0, 1.0 / ratio)  # the failure index of an unstressed ply is 0
        failure[criterion] = {"ratio": rounded(ratio), "index": rounded(index), "mode": mode, "worst_ply": (np.argmin(ratio, axis=1) + 1).tolist(),
                              "element_index": rounded(index.max(axis=1))}
        failure_average[criterion] = rounded(nodal_averages(corners, n, index.max(axis=1)))

    # the summary: where the extremes are
    control, applied = applied_loading(deck, solution)
    _, top = gripped_groups(deck, solution)
    top_reaction = float(reaction[list(top)].sum(axis=0)[1])
    at = int(np.argmax(magnitude))
    summary: dict[str, Any] = {
        "max_displacement": {"value": float(length(magnitude[at])), "node": at, "label": node_name(mesh.node_keys[at]),
                             "xy": length(mesh.xy[at]).tolist(), "components": length(displacement[at]).tolist()},
        "reaction": {"set": "the top grip", "value": float(from_si(top_reaction, "force", units)), "sense": "tension" if top_reaction > 0 else "compression"},
        "applied": {"control": control, "value": float(from_si(applied, "length" if control == "displacement" else "force", units)),
                    "unit": lab["length" if control == "displacement" else "force"]},
        "max_ply": {},
        "fpf": {},
        "equilibrium_residual": float(from_si(float(np.max(np.abs(reaction.sum(axis=0) + np.array(
            [0.0, applied if control == "force" else 0.0])))), "force", units)),
        "free_residual": float(from_si(solution.free_residual, "force", units)),
    }
    for i, name in enumerate(STRESS_NAMES):
        e, k = np.unravel_index(np.argmax(np.abs(stress_12[:, :, i])), stress_12.shape[:2])
        summary["max_ply"][name] = {"value": float(stress(stress_12[e, k, i])), "element": int(e), "label": element_name(mesh.element_keys[e]),
                                    "ply": int(k) + 1, "angle": float(angles[k]), "xy": length(centroids[e]).tolist()}
    e, k = np.unravel_index(np.argmax(mises), mises.shape)
    summary["max_ply"]["mises"] = {"value": float(stress(mises[e, k])), "element": int(e), "label": element_name(mesh.element_keys[e]), "ply": int(k) + 1,
                                   "angle": float(angles[k]), "xy": length(centroids[e]).tolist()}
    for criterion, found in failures.items():
        e = mesh.element_keys.index(found.element)
        place, touches_grip, tied = fpf_place(deck, solution, found, units)
        summary["fpf"][criterion] = {"factor": float(found.factor), "index": 1.0 / float(found.factor), "element": int(e),
                                     "label": element_name(found.element), "ply": int(found.ply), "angle": float(angles[found.ply - 1]),
                                     "mode": found.governing_mode, "place": place, "touches_grip": touches_grip, "tied_plies": list(tied),
                                     "xy": length(centroids[e]).tolist()}
    summary["earliest"] = min(failures, key=lambda c: failures[c].factor) if failures else None

    data: dict[str, Any] = {
        "units": units, "labels": {**lab, "strain": "-", "ratio": "-"},
        "coupon": coupon or {},
        "mesh": {"nodes": rounded(length(mesh.xy)), "quads": corners.tolist(), "node_labels": [node_name(k) for k in mesh.node_keys],
                 "element_labels": [element_name(k) for k in mesh.element_keys],
                 "node_sets": {name: [mesh.node(key) for key in keys] for name, keys in deck.nsets.items()},
                 "element_sets": {name: [mesh.element(key) for key in keys] for name, keys in deck.elsets.items()},
                 "node_count": n, "element_count": ne, "plies": int(plies), "angles": angles.tolist()},
        "nodal": {"displacement": rounded(length(displacement)), "magnitude": rounded(length(magnitude)), "reaction": rounded(reaction),
                  "averages": {"strain": rounded(nodal_averages(corners, n, strain)), "section_force": rounded(nodal_averages(corners, n, per_length(section_force))),
                               "ply_stress_12": rounded(nodal_averages(corners, n, stress(stress_12))), "ply_mises": rounded(nodal_averages(corners, n, stress(mises))),
                               "failure_index": failure_average},
                  "averages_note": "display averages: the mean over the elements sharing each node, for smooth contours; the element values are the result"},
        "element": {"strain": rounded(strain), "section_force": rounded(per_length(section_force)), "centroids": rounded(length(centroids)),
                    "ply": {"stress_12": rounded(stress(stress_12)), "stress_xy": rounded(stress(stress_xy)), "strain_12": rounded(strain_12),
                            "mises": rounded(stress(mises))},
                    "failure": failure, "modes": list(MODES)},
        "summary": summary,
    }
    if quality is not None:
        data["quality"] = quality_summary(quality)
    return data
