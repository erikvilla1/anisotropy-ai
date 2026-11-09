"""The mesh convergence study of a coupon (ADR-0068): the kernel solves the coupon on its own mesh and on refinements of it, and the
validation quantities of ADR-0066 are read on every mesh beside the clamped-edge peaks, so an engineer sees which numbers settle as the
mesh is refined and which keep growing.

The refinements divide every element of a structured mesh in two along each axis (the counts doubled, or the element size halved), so
the node rows on the tab lines stay where they are and the gauge-centre element shrinks around the same point. The quantities are the
reaction, the strain and every ply's sigma_1, sigma_2, tau_12 at the element nearest the centre probe, every ply's largest |sigma_1| over
the mesh (at the tab corner, the clamped edge), and the first-ply-failure factor over the whole mesh and over the gauge section. A
quantity has settled when its last refinement changes it by less than SETTLED of its value (a triple: of the triple's largest component,
so a component that is noise beside the others does not count). Nothing here judges a model: the page and the document print the table
and these flags, and the ADR says what they mean.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from .abaqus_reader import read_deck
from .femodel import FEModel, build_model
from .fields import elements_touching_grips, gauge_failures
from .mesher import MeshError
from .recovery import deck_f12_star, element_ply_states, strength_ratios
from .results import ShellSolution
from .spec import IN_PLANE_KINDS, CouponSpec, SpecError, mesh_counts
from .units import deck_units_of, from_si
from .write_abaqus import write_abaqus

FACTORS = (1, 2, 4)  # the spec's mesh, then each element split in two along both axes, then in four
CAP = 40_000  # elements: a refinement past this is left out of the study and the table says so
SETTLED = 0.01  # a quantity has settled when the last refinement moves it by less than this fraction of its value


class ConvergenceError(ValueError):
    """The study does not apply to this coupon as stated; the message says why, and the result carries it as `reason`."""


def refined(spec: CouponSpec, factor: int) -> CouponSpec:
    """The spec with every element of its structured mesh divided `factor` times along each axis: the counts multiplied, the seeds per
    segment multiplied, or the element size divided, so each tab line and partition line keeps its node row."""
    if factor < 1 or int(factor) != factor:
        raise ConvergenceError(f"a refinement factor is a whole number of 1 or more, not {factor!r}")
    m = spec.mesh
    if m.mesher != "structured":
        raise ConvergenceError(f"the study refines a structured mesh only; this coupon is meshed by {m.mesher} (the open-hole O-grid is a later step)")
    if factor == 1:
        return spec
    if m.y_seeds is not None:
        update = {"nx": m.nx * factor, "y_seeds": [n * factor for n in m.y_seeds]}
    elif m.nx is not None:
        update = {"nx": m.nx * factor, "ny": m.ny * factor}
    else:
        update = {"element_size": m.element_size / factor}
    return spec.model_copy(update={"mesh": m.model_copy(update=update)})


def solve(spec: CouponSpec) -> tuple[FEModel, Any, Any]:
    """The model, the deck our kernel read and its solution: the spec written as our Abaqus deck and read back, as every run does, so
    the study solves exactly what the job solves."""
    model = build_model(spec)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "convergence.inp"
        path.write_text(write_abaqus(model), encoding="utf-8", newline="\n")
        deck = read_deck(path, deck_units_of(spec.units))
    from .kernel import solve_deck  # noqa: E402  (the kernel imports the readers; kept local as build_model.py keeps it)

    return model, deck, solve_deck(deck)


def centroids(mesh) -> np.ndarray:
    return mesh.xy[mesh.connectivity[:, :4]].mean(axis=1)


def mesh_values(spec: CouponSpec, factor: int, model: FEModel, deck, solution) -> dict[str, Any]:
    """The quantities of ADR-0066 on one mesh, in the coupon's units, with the mesh's size and the solve's seconds filled in by the caller."""
    if isinstance(solution, ShellSolution):
        raise ConvergenceError("the study reads a membrane state; a bending coupon or a plate is a later step")
    units = spec.units
    mesh = solution.mesh
    g = spec.geometry
    xy = centroids(mesh)
    if "centre" in model.probe_elements:  # the record's gauge-centre element, by the deck label the model gives it (ADR-0066)
        label = model.probe_elements["centre"] + 1
        gauge = next(e for e, key in enumerate(mesh.element_keys) if key[1] == label)
    else:
        gauge = int(np.argmin(np.linalg.norm(xy - np.array([g.width / 2.0, g.length / 2.0]), axis=1)))
    moving = spec.loading.control == "displacement"
    reaction_set = ("RF-Top" if moving else "RF-Bottom") if model.couplings else ("Grip-Top" if moving else "Grip-Bottom")
    reaction = solution.reaction_of(deck.nsets[reaction_set])
    field = element_ply_states(solution)
    stress_12 = np.stack(field.stress_12)  # (ne, plies, 3), Pa
    angles = [float(a) for a in field.angles_deg[gauge]]
    gripped = elements_touching_grips(deck, solution)
    peaks = []
    for k in range(stress_12.shape[1]):
        e = int(np.argmax(np.abs(stress_12[:, k, 0])))
        peaks.append({"ply": k + 1, "angle": angles[k], "s1": float(from_si(stress_12[e, k, 0], "stress", units)), "element": int(mesh.element_keys[e][1]),
                      "touches_grip": e in gripped})
    f12 = deck_f12_star(deck)
    failures = {}
    for criterion in spec.output.fpf_criteria:
        try:
            failures[criterion] = strength_ratios(solution, criterion, f12, field)
        except Exception as exc:  # a criterion the deck's strengths do not allow: the summary leaves it out the same way (build_model.py)
            if "allow" not in str(exc) and "strength" not in str(exc).lower():
                raise
    in_gauge = gauge_failures(deck, solution, failures, shell=False)
    return {"factor": factor, "elements": int(mesh.element_count), "nodes": int(mesh.node_count),
            "reaction": float(abs(from_si(reaction[1], "force", units))), "reaction_set": reaction_set,
            "gauge_element": int(mesh.element_keys[gauge][1]), "gauge_xy": [float(from_si(v, "length", units)) for v in xy[gauge]],
            "gauge_strain": [float(v) for v in solution.strain[gauge]],
            "plies": [{"ply": k + 1, "angle": angles[k], "stress_12": [float(from_si(v, "stress", units)) for v in stress_12[gauge, k]]}
                      for k in range(stress_12.shape[1])],
            "peaks": peaks,
            "fpf": {criterion: float(f.factor) for criterion, f in failures.items()},
            "fpf_gauge": {criterion: float(f.factor) for criterion, f in in_gauge.items()}}


def relative_change(before: float, after: float, scale: float | None = None) -> float | None:
    """(after - before) as a fraction of |after| (or of `scale` when given, the triple's largest component); None when the scale is zero."""
    scale = abs(after) if scale is None else abs(scale)
    return None if scale == 0.0 else float((after - before) / scale)


def changes_of(meshes: list[dict[str, Any]]) -> dict[str, Any]:
    """Each quantity's change from one mesh to the next, as a fraction (None for the first mesh and where the value is zero)."""
    pairs = list(zip(meshes, meshes[1:]))

    def scalar(get) -> list[float | None]:
        return [None] + [relative_change(get(a), get(b)) for a, b in pairs]

    def triple(get) -> list[list[float | None] | None]:
        out: list[list[float | None] | None] = [None]
        for a, b in pairs:
            va, vb = get(a), get(b)
            scale = max(abs(float(v)) for v in vb)
            out.append([relative_change(float(x), float(y), scale) for x, y in zip(va, vb)])
        return out

    plies = range(len(meshes[0]["plies"]))
    criteria = [c for c in meshes[0]["fpf"] if all(c in m["fpf"] for m in meshes)]
    gauge_criteria = [c for c in meshes[0]["fpf_gauge"] if all(c in m["fpf_gauge"] for m in meshes)]
    return {"reaction": scalar(lambda m: m["reaction"]),
            "gauge_strain": triple(lambda m: m["gauge_strain"]),
            "plies": [{"ply": k + 1, "stress_12": triple(lambda m, k=k: m["plies"][k]["stress_12"])} for k in plies],
            "peaks": [{"ply": k + 1, "s1": scalar(lambda m, k=k: m["peaks"][k]["s1"])} for k in plies],
            "fpf": {c: scalar(lambda m, c=c: m["fpf"][c]) for c in criteria},
            "fpf_gauge": {c: scalar(lambda m, c=c: m["fpf_gauge"][c]) for c in gauge_criteria}}


def _last_settled(series: list) -> bool:
    last = series[-1]
    if last is None:
        return False
    values = last if isinstance(last, list) else [last]
    return all(v is None or abs(v) < SETTLED for v in values)


def settled_of(changes: dict[str, Any]) -> dict[str, bool]:
    """Per quantity group, whether the last refinement moved every value by less than SETTLED."""
    return {"reaction": _last_settled(changes["reaction"]),
            "gauge_strain": _last_settled(changes["gauge_strain"]),
            "plies": all(_last_settled(p["stress_12"]) for p in changes["plies"]),
            "peaks": all(_last_settled(p["s1"]) for p in changes["peaks"]),
            "fpf": all(_last_settled(s) for s in changes["fpf"].values()),
            "fpf_gauge": all(_last_settled(s) for s in changes["fpf_gauge"].values())}


def not_studied(reason: str, factors: tuple[int, ...] = FACTORS, cap: int = CAP, units: str | None = None) -> dict[str, Any]:
    return {"studied": False, "reason": reason, "units": units, "factors": list(factors), "cap": cap, "settled_below": SETTLED, "meshes": [], "left_out": []}


def convergence_study(spec: CouponSpec, factors: tuple[int, ...] = FACTORS, cap: int = CAP) -> dict[str, Any]:
    """The study: one mesh per factor, the finest left out past `cap` elements, the changes between meshes and the settled flags.
    A coupon the study does not cover gets `studied: false` with the reason, never an error, so a run reports the rest."""
    if spec.kind not in IN_PLANE_KINDS:
        return not_studied(f"the study covers gripped in-plane coupons; {spec.kind.replace('_', ' ')} is a later step", factors, cap, spec.units)
    if len(factors) < 2 or list(factors) != sorted(set(factors)):
        raise ConvergenceError(f"the factors are two or more distinct whole numbers in rising order, not {list(factors)}")
    meshes: list[dict[str, Any]] = []
    left_out: list[dict[str, Any]] = []
    for factor in factors:
        try:
            spec_f = refined(spec, factor)
            nx, ny = mesh_counts(spec_f)
        except ConvergenceError as exc:
            return not_studied(str(exc), factors, cap, spec.units)
        if nx * ny > cap:
            left_out.append({"factor": factor, "elements": nx * ny, "reason": f"{nx * ny} elements is past the study's cap of {cap}"})
            continue
        started = time.perf_counter()
        try:
            model, deck, solution = solve(spec_f)
            values = mesh_values(spec_f, factor, model, deck, solution)
        except (ConvergenceError, SpecError, MeshError) as exc:
            return not_studied(str(exc), factors, cap, spec.units)
        values["nx"], values["ny"], values["solve_s"] = nx, ny, round(time.perf_counter() - started, 2)
        meshes.append(values)
    if len(meshes) < 2:
        return {**not_studied("fewer than two meshes fit under the cap: nothing to compare", factors, cap, spec.units), "meshes": meshes, "left_out": left_out}
    changes = changes_of(meshes)
    return {"studied": True, "kernel": "membrane", "units": spec.units, "factors": list(factors), "cap": cap, "settled_below": SETTLED, "meshes": meshes,
            "left_out": left_out, "changes": changes, "settled": settled_of(changes),
            "note": ("the kernel on the coupon's mesh and on refinements that split every element along both axes; the validation quantities "
                     "of ADR-0066 at the element nearest the centre probe, every ply's largest |sigma_1| over the mesh (the clamped edge), and the "
                     "first-ply-failure factor over the mesh and over the gauge section; a change is the step from the previous mesh as a fraction "
                     "of the value (of a triple's largest component)")}
