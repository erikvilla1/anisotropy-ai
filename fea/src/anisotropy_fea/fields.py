"""What the studio's viewer shows after a solve (ADR-0051, faces and bending since ADR-0053): every field of the solution and a summary of
its extremes, as one JSON-ready dict in the deck's units.

The fields are the kernel's and the engine's (`kernel.solve_deck`, `recovery.element_ply_states`, `recovery.strength_ratios`): nodal
displacement and reaction; per element the membrane strain, the section forces, every ply's stress and strain in material and laminate
axes, the ply von Mises stress, and per criterion every ply's strength ratio R and failure index 1/R. A shell solve adds the deflection w
and the rotations at the nodes, the curvature, the moments and the transverse shear forces per element, and keeps both faces of every ply
(`mesh.faces` names them; a membrane solve has one value per ply and `faces` is null). The browser draws them and computes nothing.
Smooth contours need one value per node, so the mean over the elements that share a node is written here too, under `nodal.averages`,
and labelled a display average: the element values are the result.

The summary names the applied loading, the reaction that balances it, the largest displacement, the largest ply stresses, and per
criterion the first ply to fail, with its element, ply, face, mode and place in the words the coupon document uses (`report.fpf_place`).
Every number comes from the solve; a non-finite one is refused.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from anisotropy_engine.failure import CRITERIA

from .cases import element_name
from .mesh import KernelError
from .model import Deck, all_boundaries, node_name, resolve_elements, resolve_nodes
from .quality import QualityField, quality_summary
from .recovery import FACES, FailureField, PlyField, deck_f12_star, element_ply_states, ply_mises, ply_ratio_per_ply, strength_ratios
from .report import fpf_place, gripped_groups
from .results import ShellSolution, Solution
from .units import UNIT_LABEL, from_si

MODES = ("longitudinal tension", "longitudinal compression", "transverse tension", "transverse compression", "in-plane shear", "interactive",
         "none")  # the engine's governing modes; "none" is an unstressed ply, whose ratio is infinite
STRESS_NAMES = ("S11", "S22", "S12")  # the material-axis stress components, as the team's CAE exports name them
DIGITS = 9  # significant digits written for the arrays; the summary keeps full precision
SENSE = {2: ("in tension", "in compression"), 3: ("lifting the coupon", "pressing the coupon down")}  # by the sign of the reaction, positive first


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


def polygon_areas(xy: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """The area of every quadrilateral by the shoelace formula."""
    x, y = xy[corners, 0], xy[corners, 1]
    return 0.5 * np.abs(np.sum(x * np.roll(y, -1, axis=1) - y * np.roll(x, -1, axis=1), axis=1))


def applied_forces(deck: Deck, solution: Solution) -> np.ndarray:
    """The external forces along x, y, z the deck applies, SI: concentrated loads on dofs 1 to 3 and the total of every pressure."""
    mesh = solution.mesh
    total = np.zeros(3)
    for step in deck.steps:
        for load in step.cloads:
            if load.dof <= 3:
                total[load.dof - 1] += load.value * len(resolve_nodes(deck, load.target, load.line))
        for dload in step.dloads:
            elements = [mesh.element(key) for key in resolve_elements(deck, dload.target, dload.line)]
            total[2] += -dload.value * polygon_areas(mesh.xy, mesh.connectivity[elements, :4]).sum()
    return total


def applied_loading(deck: Deck, solution: Solution) -> dict[str, Any]:
    """What the deck applies, SI, and where its reaction is read: a prescribed pull between the grips or a load along the coupon (dof 2);
    for a shell solve a prescribed deflection at the loading nose, a load along z or a pressure (dof 3)."""
    mesh = solution.mesh
    if isinstance(solution, ShellSolution):
        nose: dict[int, float] = {}
        for boundary in all_boundaries(deck):
            if boundary.dof_first <= 3 <= boundary.dof_last and boundary.value != 0.0:
                for key in resolve_nodes(deck, boundary.target, boundary.line):
                    nose[mesh.node(key)] = boundary.value
        if nose:
            values = sorted(set(nose.values()))
            return {"control": "displacement", "value": values[0] if len(values) == 1 else float(np.mean(values)), "dof": 3, "set": "the loading nose",
                    "nodes": sorted(nose), "direction": "along z, down onto the coupon" if values[0] < 0 else "along z, up"}
        forces = applied_forces(deck, solution)
        if any(step.dloads for step in deck.steps):
            pressure = next(load.value for step in deck.steps for load in step.dloads)
            return {"control": "pressure", "value": pressure, "dof": 3, "set": "the supports", "nodes": [i for i in range(mesh.node_count) if solution.reaction[i, 2] != 0.0],
                    "direction": "on the whole plate, against its normal" if pressure > 0 else "on the whole plate, along its normal", "total_force": float(forces[2])}
        if forces[2] != 0.0:
            return {"control": "force", "value": float(forces[2]), "dof": 3, "set": "the supports",
                    "nodes": [i for i in range(mesh.node_count) if solution.reaction[i, 2] != 0.0], "direction": "along z"}
    bottom, top = gripped_groups(deck, solution)
    pull = float(np.mean(list(top.values())) - np.mean(list(bottom.values())))
    if pull != 0.0:
        return {"control": "displacement", "value": pull, "dof": 2, "set": "the top grip", "nodes": sorted(top), "direction": "along the coupon"}
    total = float(sum(load.value for step in deck.steps for load in step.cloads if load.dof == 2))
    return {"control": "force", "value": total, "dof": 2, "set": "the top grip", "nodes": sorted(top), "direction": "along the coupon"}


def failures_of(deck: Deck, solution: Solution, field: PlyField, criteria: tuple[str, ...] | None = None) -> dict[str, FailureField]:
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


def field_data(deck: Deck, solution: Solution, units: str, criteria: tuple[str, ...] | None = None, quality: QualityField | None = None,
               coupon: dict[str, Any] | None = None) -> dict[str, Any]:
    """The solved deck as the viewer reads it. `criteria` names the first-ply-failure criteria to report (default: every one the deck
    allows); `coupon` is the identity the preview carries, passed through."""
    mesh = solution.mesh
    shell = isinstance(solution, ShellSolution)
    n, ne = mesh.node_count, mesh.element_count
    lab = UNIT_LABEL[units]
    length = lambda a: from_si(np.asarray(a, dtype=float), "length", units)  # noqa: E731
    stress = lambda a: from_si(np.asarray(a, dtype=float), "stress", units)  # noqa: E731
    per_length = lambda a: from_si(np.asarray(a, dtype=float), "force_per_length", units)  # noqa: E731
    curvature_units = lambda a: from_si(np.asarray(a, dtype=float), "per_length", units)  # noqa: E731
    translations = 3 if shell else 2
    displacement = _finite("displacement", solution.displacement[:, :translations])
    rotation = _finite("rotation", solution.displacement[:, 3:5]) if shell else None
    reaction = _finite("reaction", solution.reaction[:, :translations])
    strain = _finite("strain", solution.strain)
    section_force = _finite("section force", solution.section_force)
    field = element_ply_states(solution)
    plies = field.stress_12[0].shape[0]
    if any(s.shape[0] != plies for s in field.stress_12):
        raise KernelError("the elements carry different ply counts; the viewer shows one laminate")
    angles = np.asarray(field.angles_deg[0], dtype=float)
    stress_12 = _finite("ply stress", np.stack(field.stress_12))  # (ne, plies, 3) or (ne, plies, 2, 3)
    stress_xy = _finite("ply stress", np.stack(field.stress_xy))
    strain_12 = _finite("ply strain", np.stack(field.strain_12))
    mises = _finite("ply Mises", np.stack(ply_mises(field))[..., 0])  # (ne, plies) or (ne, plies, 2)
    failures = failures_of(deck, solution, field, criteria)
    corners = mesh.connectivity[:, :4]
    centroids = mesh.xy[corners].mean(axis=1)
    magnitude = np.linalg.norm(displacement, axis=1)

    failure: dict[str, Any] = {}
    failure_average: dict[str, Any] = {}
    for criterion, found in failures.items():
        ratio = np.stack(found.ratio)  # (ne, plies[, 2]); infinite in an unstressed ply (a rigidly gripped tab, a midplane face), never NaN
        if np.any(np.isnan(ratio)):
            raise KernelError(f"{criterion} ratio holds a NaN; the solve is not usable")
        if shell:
            mode = [[[MODES.index(m) for m in faces] for faces in modes] for modes in found.mode]
        else:
            mode = [[MODES.index(m) for m in modes] for modes in found.mode]
        with np.errstate(divide="ignore"):
            index = np.where(np.isinf(ratio), 0.0, 1.0 / ratio)  # the failure index of an unstressed ply is 0
        per_ply = np.stack([ply_ratio_per_ply(r) for r in found.ratio])  # (ne, plies): the smaller face in a shell state
        entry: dict[str, Any] = {"ratio": rounded(ratio), "index": rounded(index), "mode": mode, "worst_ply": (np.argmin(per_ply, axis=1) + 1).tolist(),
                                 "element_index": rounded(index.reshape(ne, -1).max(axis=1))}
        if shell:
            worst = np.argmin(per_ply, axis=1)
            entry["worst_face"] = [FACES[int(np.argmin(ratio[e, k]))] for e, k in enumerate(worst)]
        failure[criterion] = entry
        failure_average[criterion] = rounded(nodal_averages(corners, n, index.reshape(ne, -1).max(axis=1)))

    # the summary: where the extremes are
    applied = applied_loading(deck, solution)
    dof = applied["dof"]
    reaction_value = float(reaction[applied["nodes"]].sum(axis=0)[dof - 1]) if applied["nodes"] else float(reaction[:, dof - 1].sum())
    applied_kind = {"displacement": "length", "force": "force", "pressure": "stress"}[applied["control"]]
    at = int(np.argmax(magnitude))
    axis = "xyz"[int(np.argmax(np.abs(displacement[at])))]
    external = applied_forces(deck, solution)
    balance = reaction.sum(axis=0) + external[:translations]
    summary: dict[str, Any] = {
        "max_displacement": {"value": float(length(magnitude[at])), "node": at, "label": node_name(mesh.node_keys[at]),
                             "xy": length(mesh.xy[at]).tolist(), "components": length(displacement[at]).tolist(), "axis": axis},
        "reaction": {"set": applied["set"], "value": float(from_si(reaction_value, "force", units)), "dof": dof,
                     "sense": SENSE[dof][0 if reaction_value > 0 else 1]},
        "applied": {"control": applied["control"], "value": float(from_si(applied["value"], applied_kind, units)), "unit": lab[applied_kind], "dof": dof,
                    "direction": applied["direction"]},
        "max_ply": {},
        "fpf": {},
        "equilibrium_residual": float(from_si(float(np.max(np.abs(balance))), "force", units)),
        "free_residual": float(from_si(solution.free_residual, "force", units)),
    }
    if "total_force" in applied:
        summary["applied"]["total_force"] = float(from_si(applied["total_force"], "force", units))

    def place_of(flat_index: int, array: np.ndarray) -> dict[str, Any]:
        where = np.unravel_index(flat_index, array.shape)
        e, k = int(where[0]), int(where[1])
        out = {"element": e, "label": element_name(mesh.element_keys[e]), "ply": k + 1, "angle": float(angles[k]), "xy": length(centroids[e]).tolist()}
        out["face"] = FACES[int(where[2])] if shell else None
        return out

    for i, name in enumerate(STRESS_NAMES):
        component = stress_12[..., i]
        flat = int(np.argmax(np.abs(component)))
        summary["max_ply"][name] = {"value": float(stress(component.reshape(-1)[flat])), **place_of(flat, component)}
    flat = int(np.argmax(mises))
    summary["max_ply"]["mises"] = {"value": float(stress(mises.reshape(-1)[flat])), **place_of(flat, mises)}
    for criterion, found in failures.items():
        e = mesh.element_keys.index(found.element)
        place, touches_grip, tied = fpf_place(deck, solution, found, units)
        summary["fpf"][criterion] = {"factor": float(found.factor), "index": 1.0 / float(found.factor), "element": int(e),
                                     "label": element_name(found.element), "ply": int(found.ply), "angle": float(angles[found.ply - 1]),
                                     "face": found.face, "mode": found.governing_mode, "place": place, "touches_grip": touches_grip,
                                     "tied_plies": list(tied), "xy": length(centroids[e]).tolist()}
    summary["earliest"] = min(failures, key=lambda c: failures[c].factor) if failures else None

    averages: dict[str, Any] = {
        "strain": rounded(nodal_averages(corners, n, strain)), "section_force": rounded(nodal_averages(corners, n, per_length(section_force))),
        "ply_stress_12": rounded(nodal_averages(corners, n, stress(stress_12))), "ply_mises": rounded(nodal_averages(corners, n, stress(mises))),
        "failure_index": failure_average,
    }
    element: dict[str, Any] = {
        "strain": rounded(strain), "section_force": rounded(per_length(section_force)), "centroids": rounded(length(centroids)),
        "ply": {"stress_12": rounded(stress(stress_12)), "stress_xy": rounded(stress(stress_xy)), "strain_12": rounded(strain_12), "mises": rounded(stress(mises))},
        "failure": failure, "modes": list(MODES),
    }
    nodal: dict[str, Any] = {"displacement": rounded(length(displacement)), "magnitude": rounded(length(magnitude)), "reaction": rounded(reaction)}
    if shell:
        curvature = _finite("curvature", solution.curvature)
        moment = _finite("moment", solution.moment)
        shear_force = _finite("shear force", solution.shear_force)
        element.update({"curvature": rounded(curvature_units(curvature)), "moment": rounded(moment), "shear_force": rounded(per_length(shear_force)),
                        "shear_strain": rounded(_finite("shear strain", solution.shear_strain))})
        nodal["rotation"] = rounded(rotation)
        nodal["moment_reaction"] = rounded(solution.reaction[:, 3:5])
        averages.update({"curvature": rounded(nodal_averages(corners, n, curvature_units(curvature))), "moment": rounded(nodal_averages(corners, n, moment)),
                         "shear_force": rounded(nodal_averages(corners, n, per_length(shear_force)))})
    nodal["averages"] = averages
    nodal["averages_note"] = "display averages: the mean over the elements sharing each node, for smooth contours; the element values are the result"

    data: dict[str, Any] = {
        "units": units, "labels": {**lab, "strain": "-", "ratio": "-"},
        "coupon": coupon or {},
        "kernel": "shell" if shell else "membrane",
        "mesh": {"nodes": rounded(length(mesh.xy)), "quads": corners.tolist(), "node_labels": [node_name(k) for k in mesh.node_keys],
                 "element_labels": [element_name(k) for k in mesh.element_keys],
                 "node_sets": {name: [mesh.node(key) for key in keys] for name, keys in deck.nsets.items()},
                 "element_sets": {name: [mesh.element(key) for key in keys] for name, keys in deck.elsets.items()},
                 "node_count": n, "element_count": ne, "plies": int(plies), "angles": angles.tolist(), "faces": list(FACES) if shell else None,
                 "translations": translations},
        "nodal": nodal,
        "element": element,
        "summary": summary,
    }
    if quality is not None:
        data["quality"] = quality_summary(quality)
    return data
