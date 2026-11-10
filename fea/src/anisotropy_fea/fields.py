"""What the studio's viewer shows after a solve (ADR-0051, faces and bending since ADR-0053): every field of the solution and a summary of
its extremes, as one JSON-ready dict in the deck's units.

The fields are the kernel's and the engine's (`kernel.solve_deck`, `recovery.element_ply_states`, `recovery.strength_ratios`): nodal
displacement and reaction; per element the membrane strain, the section forces, every ply's stress and strain in material and laminate
axes, the ply von Mises stress, and per criterion every ply's strength ratio R and failure index 1/R. A shell solve adds the deflection w
and the rotations at the nodes, the curvature, the moments and the transverse shear forces per element, and keeps both faces of every ply
(`mesh.faces` names them; a membrane solve has one value per ply and `faces` is null). The browser draws them and computes nothing.
Smooth contours need one value per node, so the mean over the elements that share a node is written here too, under `nodal.averages`,
and labelled a display average: the element values are the result. `ranges` holds the smallest and largest value of every field the
viewer can show, element values and display averages apart, per ply and face where the field is per ply, so the legend's ends are
written here and the browser derives none (ADR-0063).

The summary names the applied loading, the reaction that balances it, the largest displacement, the largest ply stresses, and per
criterion the first ply to fail, with its element, ply, face, mode and place in the words the coupon document uses (`report.fpf_place`).
It also names, per criterion, the first ply to fail in the gauge section alone (`gauge_failures`: the deck's `Gauge` elements that touch
no gripped node), the number a test is compared with, away from the clamped edge of a tab.
Every number comes from the solve; a non-finite one is refused.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from anisotropy_engine.failure import CRITERIA
from anisotropy_engine.response import Loads, midplane_response, ply_surfaces

from .cases import element_name
from .mesh import KernelError
from .model import Deck, all_boundaries, node_name, resolve_elements, resolve_nodes
from .quality import QualityField, quality_summary
from .recovery import FACES, FailureField, PlyField, deck_f12_star, element_ply_states, ply_mises, ply_ratio_per_ply, strength_ratios
from .report import edge_widths, fpf_place, gripped_groups
from .results import ShellSolution, Solution
from .test_quantities import MethodInputs, method_summary
from .units import UNIT_LABEL, from_si

MODES = ("longitudinal tension", "longitudinal compression", "transverse tension", "transverse compression", "in-plane shear", "interactive",
         "none")  # the engine's governing modes; "none" is an unstressed ply, whose ratio is infinite
STRESS_NAMES = ("S11", "S22", "S12")  # the material-axis stress components, as the team's CAE exports name them
DIGITS = 9  # significant digits written for the arrays; the summary keeps full precision
SENSE = {2: ("in tension", "in compression"), 3: ("lifting the coupon", "pressing the coupon down")}  # by the sign of the reaction, positive first
SUPPORT_SENSE = {1: ("pushing along +x", "pushing along -x"), 2: ("pushing along +y", "pushing along -y"), 3: ("pushing the plate up", "holding the plate down")}


def rounded(values: np.ndarray) -> list:
    """An array as nested lists of floats at DIGITS significant digits; a value JSON cannot carry becomes None: NaN at a node no element
    touches, an infinite strength ratio in an unstressed ply."""
    flat = np.asarray(values, dtype=float).reshape(-1)
    out = [None if not np.isfinite(v) else float(f"{v:.{DIGITS}g}") for v in flat]
    return np.asarray(out, dtype=object).reshape(np.shape(values)).tolist()


def span(values: np.ndarray) -> list:
    """The smallest and largest finite entry of an array, at DIGITS significant digits, so each end equals the array's own extreme as
    written; [None, None] when no entry is finite (a nodal average at a node no element touches)."""
    flat = np.asarray(values, dtype=float).reshape(-1)
    finite = flat[np.isfinite(flat)]
    return rounded(np.array([finite.min(), finite.max()])) if finite.size else [None, None]


def per_ply_spans(values: np.ndarray) -> list:
    """`span` of each ply's values in an array shaped (count, plies[, faces]): a [min, max] per ply, or per ply and face."""
    values = np.asarray(values, dtype=float)
    if values.ndim == 3:
        return [[span(values[:, k, f]) for f in range(values.shape[2])] for k in range(values.shape[1])]
    return [span(values[:, k]) for k in range(values.shape[1])]


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
    try:
        bottom, top = gripped_groups(deck, solution)
    except KernelError:  # a plate loaded in its plane (ADR-0054): the loads say what is applied, every support carries the reaction
        forces = applied_forces(deck, solution)
        dof = int(np.argmax(np.abs(forces[:2]))) + 1 if np.any(forces[:2] != 0.0) else 2
        held = [i for i in range(mesh.node_count) if solution.reaction[i, dof - 1] != 0.0]
        if forces[dof - 1] != 0.0:
            return {"control": "force", "value": float(forces[dof - 1]), "dof": dof, "set": "the supports", "nodes": held, "direction": f"along {'xyz'[dof - 1]}"}
        moved = {}
        for boundary in all_boundaries(deck):
            if boundary.value != 0.0 and boundary.dof_first <= 2:
                for key in resolve_nodes(deck, boundary.target, boundary.line):
                    moved[mesh.node(key)] = (boundary.dof_first, boundary.value)
        if moved:
            dof, value = next(iter(moved.values()))
            return {"control": "displacement", "value": value, "dof": dof, "set": "the moved region", "nodes": sorted(moved), "direction": f"along {'xyz'[dof - 1]}"}
        return {"control": "force", "value": 0.0, "dof": 2, "set": "the supports", "nodes": held, "direction": "along y"}
    pull = float(np.mean(list(top.values())) - np.mean(list(bottom.values())))
    if pull != 0.0:
        return {"control": "displacement", "value": pull, "dof": 2, "set": "the top grip", "nodes": sorted(top), "direction": "along the coupon"}
    total = float(sum(load.value for step in deck.steps for load in step.cloads if load.dof == 2))
    return {"control": "force", "value": total, "dof": 2, "set": "the top grip", "nodes": sorted(top), "direction": "along the coupon"}


def gauge_elements(deck: Deck, solution: Solution) -> list[int]:
    """The mesh indices of the gauge section's elements that touch no gripped node: the deck's `Gauge` set less the row along each tab
    line, whose nodes the grips hold. Empty for a deck without that set or without grips (a plate, a bending coupon)."""
    mesh = solution.mesh
    keys = deck.elsets.get("Gauge")
    if not keys:
        return []
    try:
        bottom, top = gripped_groups(deck, solution)
    except KernelError:
        return []
    gripped = {i for i in (*bottom, *top) if mesh.node_keys[i][0] is not None}
    inside = []
    for key in keys:
        e = mesh.element(key)
        if not gripped & set(mesh.connectivity[e, :4].tolist()):
            inside.append(e)
    return inside


def elements_touching_grips(deck: Deck, solution: Solution) -> set[int]:
    """The mesh indices of the elements with a gripped node: the row along each tab line, the clamped edge (ADR-0066). Empty for a deck
    without grips (a plate, a bending coupon)."""
    mesh = solution.mesh
    try:
        bottom, top = gripped_groups(deck, solution)
    except KernelError:
        return set()
    gripped = {i for i in (*bottom, *top) if mesh.node_keys[i][0] is not None}
    return {e for e in range(mesh.element_count) if gripped & set(mesh.connectivity[e, :4].tolist())}


def classical_laminate_check(solution: Solution, applied: dict[str, Any], reaction_si: float, angles: np.ndarray, units: str,
                             deck: Deck | None = None) -> dict[str, Any] | None:
    """Classical laminate theory for a gripped coupon pulled or pushed along its length (ADR-0066): the reaction over the width as N_y with
    N_x = N_xy = 0 (free edges), the mid-plane strain from the laminate's ABD and every ply's stresses in its fibre axes at its middle, so
    the engineer's hand check sits beside the two solvers in the fields' units. None for another loading (a plate, a bending coupon) or
    a mesh of more than one laminate; the same column the Summary leaves empty. A coupon that narrows (a dog-bone, ADR-0075, read from the
    deck's edge rows) carries the reaction over its narrowest width, where the gauge is."""
    mesh = solution.mesh
    if applied.get("dof") != 2 or applied.get("set") != "the top grip" or len(mesh.sections) != 1:
        return None
    section = mesh.sections[0]
    width = float(mesh.xy[:, 0].max() - mesh.xy[:, 0].min())
    rows = edge_widths(deck, solution) if deck is not None else None
    if rows is not None:
        width = min(width, float(rows[1].min()))
    if width <= 0.0:
        return None
    eps0, kappa = midplane_response(section.plies, Loads(Ny=reaction_si / width))
    surfaces = ply_surfaces(section.plies, eps0, kappa)
    per_ply = []
    for k in range(len(section.plies)):
        bottom, top = surfaces[2 * k], surfaces[2 * k + 1]
        middle = (np.asarray(bottom.stress_12) + np.asarray(top.stress_12)) / 2.0
        per_ply.append({"ply": k + 1, "angle": float(angles[k]), "stress_12": from_si(middle, "stress", units).tolist()})
    return {"Ny": float(from_si(reaction_si / width, "force_per_length", units)), "width": float(from_si(width, "length", units)),
            "strain": [float(eps0[0]), float(eps0[1]), float(eps0[2])], "plies": per_ply,
            "note": "classical laminate theory: the reaction over the width as N_y, N_x = N_xy = 0, each ply at its middle"}


def gauge_failures(deck: Deck, solution: Solution, failures: dict[str, FailureField], shell: bool) -> dict[str, FailureField]:
    """Per criterion, the first ply to fail among the gauge elements alone (`gauge_elements`), as a FailureField with that element, ply,
    face and mode; a criterion whose gauge plies are all unstressed (an infinite ratio) is left out."""
    inside = gauge_elements(deck, solution)
    out: dict[str, FailureField] = {}
    for criterion, found in failures.items():
        if not inside:
            continue
        per_ply = np.stack([ply_ratio_per_ply(found.ratio[e]) for e in inside])  # (inside, plies)
        if not np.isfinite(per_ply).any():
            continue
        i, k = (int(v) for v in np.unravel_index(int(np.argmin(per_ply)), per_ply.shape))
        e = inside[i]
        if shell:
            face_index = int(np.argmin(np.asarray(found.ratio[e])[k]))
            face, mode = FACES[face_index], found.mode[e][k][face_index]
        else:
            face, mode = None, found.mode[e][k]
        out[criterion] = dataclasses.replace(found, factor=float(per_ply[i, k]), element=solution.mesh.element_keys[e], ply=k + 1, governing_mode=mode, face=face)
    return out


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
               coupon: dict[str, Any] | None = None, method: MethodInputs | None = None) -> dict[str, Any]:
    """The solved deck as the viewer reads it. `criteria` names the first-ply-failure criteria to report (default: every one the deck
    allows); `coupon` is the identity the preview carries, passed through; `method`, from `test_quantities.method_inputs(spec)`, adds the
    test-method quantities as `summary["test_method"]` (ADR-0072) for a coupon that names a standard or states a strain measurement."""
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
    failure_ranges: dict[str, Any] = {}
    failure_ply_ranges: dict[str, Any] = {}
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
        element_index = index.reshape(ne, -1).max(axis=1)
        index_average = nodal_averages(corners, n, element_index)
        failure_average[criterion] = rounded(index_average)
        failure_ranges[criterion] = {"element": span(element_index), "nodal": span(index_average)}
        failure_ply_ranges[criterion] = {"element": per_ply_spans(index.max(axis=2) if shell else index)}  # the worse face of each ply

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
                     "sense": (SUPPORT_SENSE if applied["set"] in ("the supports", "the moved region") else SENSE)[dof][0 if reaction_value > 0 else 1]},
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
    # every ply's own peaks at the element centroids (ADR-0066): the stress concentration an engineer compares across solvers ply by ply,
    # each marked when its element touches a gripped node, the clamped edge where the value grows with the mesh
    gripped = elements_touching_grips(deck, solution)
    summary["ply_peaks"] = []
    for k in range(plies):
        peak: dict[str, Any] = {"ply": k + 1, "angle": float(angles[k])}
        for i, name in enumerate(STRESS_NAMES):
            component = stress_12[:, k, ..., i]  # (ne,) or (ne, 2) for a shell state
            flat = int(np.argmax(np.abs(component)))
            where = np.unravel_index(flat, component.shape)
            e = int(where[0])
            peak[name] = {"value": float(stress(component.reshape(-1)[flat])), "element": e, "label": element_name(mesh.element_keys[e]),
                          "xy": length(centroids[e]).tolist(), "face": FACES[int(where[1])] if shell else None, "touches_grip": e in gripped}
        summary["ply_peaks"].append(peak)
    summary["clt"] = classical_laminate_check(solution, applied, reaction_value, angles, units, deck)
    for criterion, found in failures.items():
        e = mesh.element_keys.index(found.element)
        place, touches_grip, tied = fpf_place(deck, solution, found, units)
        summary["fpf"][criterion] = {"factor": float(found.factor), "index": 1.0 / float(found.factor), "element": int(e),
                                     "label": element_name(found.element), "ply": int(found.ply), "angle": float(angles[found.ply - 1]),
                                     "face": found.face, "mode": found.governing_mode, "place": place, "touches_grip": touches_grip,
                                     "tied_plies": list(tied), "xy": length(centroids[e]).tolist()}
    summary["earliest"] = min(failures, key=lambda c: failures[c].factor) if failures else None
    # the same, over the gauge section alone: the number a test is compared with, away from the clamped edge of a gripped tab
    summary["fpf_gauge"] = {}
    for criterion, found in gauge_failures(deck, solution, failures, shell).items():
        e = mesh.element_keys.index(found.element)
        place, touches_grip, tied = fpf_place(deck, solution, found, units)
        summary["fpf_gauge"][criterion] = {"factor": float(found.factor), "index": 1.0 / float(found.factor), "element": int(e),
                                           "label": element_name(found.element), "ply": int(found.ply), "angle": float(angles[found.ply - 1]),
                                           "face": found.face, "mode": found.governing_mode, "place": place, "touches_grip": touches_grip,
                                           "tied_plies": list(tied), "xy": length(centroids[e]).tolist()}
    summary["earliest_gauge"] = min(summary["fpf_gauge"], key=lambda c: summary["fpf_gauge"][c]["factor"]) if summary["fpf_gauge"] else None
    if method is not None and applied["dof"] == 2 and len(mesh.sections) == 1:
        # the force along the coupon: the moving grip's reaction under a displacement, the applied total under a force (ADR-0072)
        force = reaction_value if applied["set"] == "the top grip" else float(applied["value"])
        probes = {name[len("Probe-"):]: mesh.node(keys[0]) for name, keys in deck.nsets.items() if name.startswith("Probe-") and len(keys) == 1}
        basis, found = ("the gauge section", summary["fpf_gauge"]) if summary["fpf_gauge"] else ("the whole coupon", summary["fpf"])
        summary["test_method"] = method_summary(method, mesh.xy, displacement, probes, force, mesh.sections[0].plies, found, basis, units,
                                                [node_name(k) for k in mesh.node_keys])

    section_force_out, stress_12_out, mises_out, displacement_out = per_length(section_force), stress(stress_12), stress(mises), length(displacement)
    strain_average = nodal_averages(corners, n, strain)
    section_force_average = nodal_averages(corners, n, section_force_out)
    stress_12_average = nodal_averages(corners, n, stress_12_out)
    mises_average = nodal_averages(corners, n, mises_out)
    averages: dict[str, Any] = {
        "strain": rounded(strain_average), "section_force": rounded(section_force_average),
        "ply_stress_12": rounded(stress_12_average), "ply_mises": rounded(mises_average),
        "failure_index": failure_average,
    }
    element: dict[str, Any] = {
        "strain": rounded(strain), "section_force": rounded(section_force_out), "centroids": rounded(length(centroids)),
        "ply": {"stress_12": rounded(stress_12_out), "stress_xy": rounded(stress(stress_xy)), "strain_12": rounded(strain_12), "mises": rounded(mises_out)},
        "failure": failure, "modes": list(MODES),
    }
    nodal: dict[str, Any] = {"displacement": rounded(displacement_out), "magnitude": rounded(length(magnitude)), "reaction": rounded(reaction)}

    # the ends of every field the viewer can show, as written above: the element values and the display averages apart (ADR-0063)
    def both(element_values: np.ndarray, average_values: np.ndarray) -> dict[str, list]:
        return {"element": span(element_values), "nodal": span(average_values)}

    ranges: dict[str, Any] = {"u_mag": {"nodal": span(length(magnitude))}}
    for i, name in enumerate(("u_x", "u_y", "u_z")[:translations]):
        ranges[name] = {"nodal": span(displacement_out[:, i])}
    for i, name in enumerate(("eps_x", "eps_y", "gamma_xy")):
        ranges[name] = both(strain[:, i], strain_average[:, i])
    for i, name in enumerate(("N_x", "N_y", "N_xy")):
        ranges[name] = both(section_force_out[:, i], section_force_average[:, i])
    for i, name in enumerate(STRESS_NAMES):
        ranges[name] = {"element": per_ply_spans(stress_12_out[..., i]), "nodal": per_ply_spans(stress_12_average[..., i])}
    ranges["mises"] = {"element": per_ply_spans(mises_out), "nodal": per_ply_spans(mises_average)}
    ranges["failure_index"] = failure_ranges
    ranges["failure_index_ply"] = failure_ply_ranges

    if shell:
        curvature = _finite("curvature", solution.curvature)
        moment = _finite("moment", solution.moment)
        shear_force = _finite("shear force", solution.shear_force)
        curvature_out, shear_force_out = curvature_units(curvature), per_length(shear_force)
        curvature_average = nodal_averages(corners, n, curvature_out)
        moment_average = nodal_averages(corners, n, moment)
        shear_force_average = nodal_averages(corners, n, shear_force_out)
        element.update({"curvature": rounded(curvature_out), "moment": rounded(moment), "shear_force": rounded(shear_force_out),
                        "shear_strain": rounded(_finite("shear strain", solution.shear_strain))})
        nodal["rotation"] = rounded(rotation)
        nodal["moment_reaction"] = rounded(solution.reaction[:, 3:5])
        averages.update({"curvature": rounded(curvature_average), "moment": rounded(moment_average), "shear_force": rounded(shear_force_average)})
        for i, name in enumerate(("theta_x", "theta_y")):
            ranges[name] = {"nodal": span(rotation[:, i])}
        for i, name in enumerate(("kappa_x", "kappa_y", "kappa_xy")):
            ranges[name] = both(curvature_out[:, i], curvature_average[:, i])
        for i, name in enumerate(("M_x", "M_y", "M_xy")):
            ranges[name] = both(moment[:, i], moment_average[:, i])
        for i, name in enumerate(("Q_x", "Q_y")):
            ranges[name] = both(shear_force_out[:, i], shear_force_average[:, i])
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
        "ranges": ranges,
        "ranges_note": "the smallest and largest value of each field as written here, element values and display averages apart, per ply and face "
                       "where the field is per ply: the legend's ends",
        "summary": summary,
    }
    if quality is not None:
        data["quality"] = quality_summary(quality)
    return data
