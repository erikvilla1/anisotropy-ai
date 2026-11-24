"""A stepped patch repair's bond followed until it lets go (ADR-0137): the model built from the repair's description, the
path, and the answer read from it.

The slice is the one CalculiX solves in the repair's elastic state (ADR-0132, `repair_model`): the same grid, the same
eight-node elements, the same holds, the laminate's far-field width strain on every part and the load on the panel's end as
each ply's far-field stress. Two things differ.

- The adhesive is not solid elements. Along every flat bond, where the patch or a cover ply lies on the laminate, each node
  on the laminate's side is paired with the node above it on the patch's side, and the pair carries the bond's law
  (`bond_solver.BondLaw`): the adhesive's shear modulus over the bondline's thickness in shear, its modulus when kept from
  straining in its plane over the thickness in peel, its two strengths and its two fracture energies. The bondline's
  thickness stays in the mesh as the gap between the two nodes. The adhesive on the cut faces carries nothing, as in the
  elastic solve's default.
- The load is not given. Every load and the width strain are those of one newton per metre of width, times a load factor
  that the path finds: the factor is the load per unit width.

The solve is our own (`bond_solver.follow`): elastic to the first point of the bond at onset, then along the path by the
energy the bond spends.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path as FilePath

import numpy as np
import scipy.sparse.linalg as spla

from anisotropy_engine.repair import FarField, Repair, RepairError, adhesive_stiffness, bond_needs, far_field, repair_from_dict
from anisotropy_engine.units import UNIT_SYSTEMS

from .bond_solver import FACTOR, BondError, BondLaw, BondModel, Path, element_strains, follow, solid_stiffness, stress_load
from .repair_model import HOLDS, SliceModel, SliceResults, _eight_node, _stress_in_slice_axes, _without_cut_faces, held_nodes, region_stiffness
from .repair_shape import MM, REFUSED, SliceMesh, read_repair_file, slice_mesh
from .wing_shape import ShapeError

FINE_PER_BONDLINE = 4  # the elements beside an edge are this fraction of the bondline's thickness long (ADR-0137's mesh study)
LET_GO_FALL = 0.05  # the load must fall by this much of a peak for the peak to be the load at which the bond lets go
RUN_ON = 0.10  # the path is followed until the load has fallen this far below the largest it reached
FAR_FIELD_TOLERANCE = 0.01  # as the elastic solve's: how far the strain midway to the panel's end may be from the laminate theory's
EQUILIBRIUM_TOLERANCE = 1e-4  # of the load: how far the plies' forces at a station may be from adding up to it
REPORT = "repair-bond.json"
PLANE = [0, 2, 4]  # of a stiffness's six rows (xx, yy, zz, yz, xz, xy): along the load, through the thickness, the shear between


class BondRunError(ValueError):
    """The repair's bond cannot be followed as stated."""


@dataclass(frozen=True)
class BondStretch:
    """One flat bond of the repair: its name and step as the slice's rectangles give them, and which of the model's pairs are
    its own, in order from the repair's middle outward."""

    name: str
    step: int | None
    pairs: np.ndarray


@dataclass(frozen=True)
class RepairBondModel:
    """A repair's slice with its bond as pairs. `mesh` is the slice's grid less the adhesive; `model` what the solver
    follows, its unit load one newton per metre of width; `pair_r_m` each pair's distance from the repair's middle. `solid`
    is each rectangle's stiffness, six by six, and `end_load` the part of the unit load that is on the panel's end: times
    the displacements it is the end's movement along the load, each ply's weighed by the stress it carries there."""

    repair: Repair
    mesh: SliceMesh
    model: BondModel
    far: FarField
    law: BondLaw
    stretches: tuple[BondStretch, ...]
    pair_r_m: np.ndarray
    solid: tuple[np.ndarray, ...]
    end_load: np.ndarray

    @property
    def bond_length_m(self) -> float:
        return float(self.model.weight.sum())

    @property
    def fine_m(self) -> float:
        return float(np.min(np.diff(self.mesh.r_lines_m)))


def bond_law(repair: Repair) -> BondLaw:
    """The bond's six numbers from the repair's adhesive. Refused when one is missing or when they cannot make a law."""
    needs = [need for need in bond_needs(repair) if need["path"].startswith("adhesive.")]
    if needs:
        raise BondRunError("To follow the bond until it lets go the repair needs " + "; ".join(need["words"] for need in needs))
    adhesive = repair.adhesive
    solid = adhesive_stiffness(adhesive)
    try:
        return BondLaw(peel_stiffness=float(solid[2, 2]) / adhesive.thickness_m, shear_stiffness=float(solid[4, 4]) / adhesive.thickness_m,
                       peel_strength=adhesive.peel_strength_pa, shear_strength=adhesive.shear_strength_pa,
                       peel_energy=adhesive.peel_energy_j_m2, shear_energy=adhesive.shear_energy_j_m2)
    except BondError as error:
        raise BondRunError(str(error)) from error


def build_bond_model(repair: Repair, *, element_size_m: float | None = None, fine_m: float | None = None, hold: str = "bottom") -> RepairBondModel:
    """The model of a repair's slice with its bond as pairs. `element_size_m` is the longest element along the slice and
    `fine_m` the length of the elements beside every step's end, cut and edge (a quarter of the bondline's thickness unless
    said), as in `build_slice_model`. With `hold="everywhere"` no node moves through the thickness: not a repair, the stepped
    lap's own assumptions, used to check the model against the lap's closed form."""
    if hold not in HOLDS:
        raise BondRunError(f"hold must be one of {', '.join(HOLDS)}, got {hold!r}")
    needs = bond_needs(repair)
    if needs:
        raise BondRunError("To follow the bond until it lets go the repair needs " + "; ".join(need["words"] for need in needs))
    law = bond_law(repair)
    try:
        far = far_field(repair, 1.0)
        if fine_m is None:
            fine_m = repair.adhesive.thickness_m / FINE_PER_BONDLINE
        whole = _without_cut_faces(repair, slice_mesh(repair, element_size_m, fine_m=fine_m, adhesive_layers=1))
        solid = [region_stiffness(repair, part) for part in whole.regions]
    except (RepairError, ShapeError) as error:
        raise BondRunError(str(error)) from error
    nodes, elements = _eight_node(whole)
    column, layer = whole.cell[:, 0], whole.cell[:, 1]
    kinds = np.array([part.kind for part in whole.regions])[whole.region]
    kind_at = {(int(c), int(k)): str(kind) for c, k, kind in zip(column, layer, kinds)}
    length = np.diff(whole.r_lines_m)

    # every flat bond: the adhesive's elements with the patch (or a cover ply) on them and the laminate under them
    weight: dict[tuple[int, int], float] = {}
    owner: dict[tuple[int, int], int] = {}
    found = []
    for index, part in enumerate(whole.regions):
        rows = np.flatnonzero((whole.region == index) & (kinds == "adhesive"))
        inside = [e for e in rows if kind_at.get((int(column[e]), int(layer[e]) + 1)) in ("patch", "cover")
                  and kind_at.get((int(column[e]), int(layer[e]) - 1)) == "parent"]
        if not inside:
            continue
        found.append((index, part))
        for e in sorted(inside, key=lambda e: column[e]):
            q, size = elements[e], float(length[column[e]])
            for under, over, share in ((q[0], q[3], 1 / 6), (q[4], q[6], 4 / 6), (q[1], q[2], 1 / 6)):
                key = (int(under), int(over))
                weight[key] = weight.get(key, 0.0) + share * size
                owner.setdefault(key, index)
    if not weight:
        raise BondRunError("The repair has no flat bondline to follow")

    keep = kinds != "adhesive"
    used = np.unique(elements[keep])
    renumber = np.full(len(nodes), -1)
    renumber[used] = np.arange(len(used))
    pairs = sorted(weight, key=lambda key: (owner[key], nodes[key[0], 0]))
    under, over = renumber[[key[0] for key in pairs]], renumber[[key[1] for key in pairs]]
    if np.any(under < 0) or np.any(over < 0):
        raise BondRunError("A bond's node belongs to no ply: the slice's grid is not the one this model reads")
    nodes, elements = nodes[used], renumber[elements[keep]]
    mesh = SliceMesh(nodes_m=whole.nodes_m, quads=whole.quads[keep], region=whole.region[keep], regions=whole.regions, cell=whole.cell[keep],
                     r_lines_m=whole.r_lines_m, z_lines_m=whole.z_lines_m)
    stiffness = np.array([solid[index][np.ix_(PLANE, PLANE)] for index in mesh.region])

    end = end_forces(mesh, nodes, elements, far)
    unit = end - width_forces(mesh, nodes, elements, solid, far)
    middle, bottom = held_nodes(nodes)
    fixed = np.concatenate([2 * middle, 2 * (np.arange(len(nodes)) if hold == "everywhere" else bottom) + 1])
    try:
        model = BondModel(nodes, elements, stiffness, under, over, np.array([weight[key] for key in pairs]), law, fixed, unit)
    except BondError as error:
        raise BondRunError(str(error)) from error
    owners = np.array([owner[key] for key in pairs])
    stretches = tuple(BondStretch(part.name, part.step, np.flatnonzero(owners == index)) for index, part in found)
    return RepairBondModel(repair, mesh, model, far, law, stretches, nodes[under, 0].copy(), tuple(solid), end)


def end_forces(mesh: SliceMesh, nodes: np.ndarray, elements: np.ndarray, far: FarField) -> np.ndarray:
    """The nodal forces of the load on the panel's end (ADR-0132): each ply's far-field stress on its edge there."""
    load = np.zeros(2 * len(nodes))
    last = int(mesh.cell[:, 0].max())
    for e in np.flatnonzero(mesh.cell[:, 0] == last):
        part = mesh.regions[mesh.region[e]]
        if part.kind != "parent":
            raise BondRunError("The panel's end must be laminate only: the repair reaches the end of the panel")
        q = elements[e]
        height = float(nodes[q[2], 1] - nodes[q[1], 1])
        load[2 * q[[1, 5, 2]]] += float(far.ply_stress_x[part.ply - 1]) * height * np.array([1 / 6, 4 / 6, 1 / 6])
    return load


def width_forces(mesh: SliceMesh, nodes: np.ndarray, elements: np.ndarray, solid: list[np.ndarray], far: FarField) -> np.ndarray:
    """The nodal forces of the stress the far-field width strain makes in every element. The nodes must balance them, so
    they come off the load. `solid` is each rectangle's stiffness, six by six."""
    return stress_load(nodes, elements, np.array([solid[index][PLANE, 1] * far.strain_width for index in mesh.region]))


def elastic_slice(model: SliceModel) -> SliceResults:
    """The slice CalculiX solves (ADR-0132), solved by this package's own plane elements: the same nodes, elements,
    stiffnesses, holds and load. It is how the elements, the load and the holds of the bond's model are held to CalculiX's
    (`fea/tests/test_repair_bond.py`); the product's elastic answer stays CalculiX's."""
    started = time.perf_counter()
    nodes, elements, mesh = model.nodes_m, model.elements, model.mesh
    solid = list(model.stiffness)
    matrix = solid_stiffness(nodes, elements, np.array([solid[index][np.ix_(PLANE, PLANE)] for index in mesh.region]))
    load = end_forces(mesh, nodes, elements, model.far) - width_forces(mesh, nodes, elements, solid, model.far)
    middle, bottom = held_nodes(nodes)
    fixed = np.concatenate([2 * middle, 2 * (np.arange(len(nodes)) if model.hold == "everywhere" else bottom) + 1])
    free = np.setdiff1d(np.arange(2 * len(nodes)), fixed)
    displacement = np.zeros(2 * len(nodes))
    displacement[free] = spla.splu(matrix[free][:, free].tocsc(), **FACTOR).solve(load[free])
    strain = element_strains(nodes, elements, displacement)
    stress = _stress_in_slice_axes(model, strain)[:, [0, 1, 2, 4]]
    return SliceResults(strain, stress, time.perf_counter() - started, len(free), "anisotropy_fea.bond_solver")


def follow_bond(built: RepairBondModel, *, steps: int = 1500, stop=None, **options) -> tuple[Path, float]:
    """The model's path and the seconds it took. Unless another `stop` is given the path ends once the load has fallen a
    tenth below the largest it reached: past the load at which the bond lets go, and far enough to say so."""
    largest = [0.0]

    def fallen(point, _points) -> bool:
        largest[0] = max(largest[0], point.load)
        return point.load < (1 - RUN_ON) * largest[0]

    started = time.perf_counter()
    try:
        path = follow(built.model, steps=steps, stop=fallen if stop is None else stop, **options)
    except BondError as error:
        raise BondRunError(str(error)) from error
    return path, time.perf_counter() - started


@dataclass(frozen=True)
class BondState:
    """The bond at one load: the load per unit width (N/m), the movement of the panel's end along the load (m), the energy
    the bond has spent (J per metre of width) and, for every pair, its damage, its shear stress (Pa, positive when it
    passes tension into the patch, as the elastic solve's) and its peel stress (Pa, positive when it pulls the patch off)."""

    load: float
    end_movement_m: float
    spent: float
    damage: np.ndarray
    shear_pa: np.ndarray
    peel_pa: np.ndarray


@dataclass(frozen=True)
class BondAnswer:
    """A repair's bond followed along its path.

    `onset` is the state at which the first point of the bond reaches the onset line (`onset_pair` says which pair);
    `let_go` the first state after which the load falls by more than a twentieth of it, the load at which the bond lets go
    in this model, or None when the load never fell that far; `largest` the state of the largest load on the path, and
    `last` the path's last state. `ended` says why the path stopped: "let_go", or the path's own "gone", "steps" or
    "stalled". `far_field_error` and `equilibrium_error` are the run's two checks, as fractions."""

    built: RepairBondModel
    path: Path
    seconds: float
    onset: BondState
    onset_pair: int
    let_go: BondState | None
    largest: BondState
    last: BondState
    ended: str
    loads: np.ndarray
    end_movements_m: np.ndarray
    far_field_error: float
    equilibrium_error: float

    def stretch_of(self, pair: int) -> BondStretch:
        return next(stretch for stretch in self.built.stretches if pair in stretch.pairs)

    def softening_m(self, state: BondState) -> float:
        """The length of bond that has begun to soften and has not parted, m."""
        return float(self.built.model.weight[(state.damage > 0) & (state.damage < 1)].sum())

    def parted_m(self, state: BondState) -> float:
        """The length of bond that carries nothing any more, m."""
        return float(self.built.model.weight[state.damage >= 1].sum())


def _state(built: RepairBondModel, load: float, displacement: np.ndarray, damage: np.ndarray, spent: float) -> BondState:
    opening, slip = built.model.jumps(displacement)
    peel, shear, _ = built.law.traction(opening, slip, damage)
    return BondState(float(load), float(built.end_load @ displacement), float(spent), damage.copy(), -shear, peel)


def _force_along(built: RepairBondModel, load: float, displacement: np.ndarray) -> np.ndarray:
    """The force along the load that the plies carry across every station (N/m): each element's mean stress along the load
    times its height, summed through the thickness. The bond's pairs carry none."""
    mesh, model = built.mesh, built.model
    strain = element_strains(model.nodes, model.elements, displacement)
    stress = np.empty(len(strain))
    for index, matrix in enumerate(built.solid):
        rows = mesh.region == index
        stress[rows] = strain[rows] @ matrix[0, PLANE] + matrix[0, 1] * built.far.strain_width * load
    height = np.diff(mesh.z_lines_m)[mesh.cell[:, 1]]
    return np.bincount(mesh.cell[:, 0], weights=stress * height, minlength=len(mesh.r_lines_m) - 1)


def bond_answer(built: RepairBondModel, path: Path, seconds: float = 0.0) -> BondAnswer:
    """Read a followed path: the onset, the load at which the bond lets go, and the run's two checks. Refused when the
    strain midway between the repair and the panel's end is not the laminate theory's while the bond is whole, or when the
    plies' forces do not add up to the load at every station of the last state read."""
    repair, mesh, model = built.repair, built.mesh, built.model
    first = path.points[0]
    scale = path.onset_load / first.load  # the first state is elastic, a little under the onset: the onset's is it, scaled
    onset = _state(built, path.onset_load, scale * first.displacement, first.damage, 0.0)
    opening, slip = model.jumps(scale * first.displacement)
    onset_pair = int(np.argmax(np.where(first.damage > 0, 0.0, built.law.index(opening, slip))))

    column = mesh.cell[:, 0]
    stations = (mesh.r_lines_m[:-1] + mesh.r_lines_m[1:]) / 2
    kinds = np.array([part.kind for part in mesh.regions])[mesh.region]
    outer = repair.patch_radius_m if repair.external else repair.cover_radius_m
    midway = int(np.argmin(np.abs(stations - (outer + repair.panel_length_m / 2) / 2)))
    there = (column == midway) & (kinds == "parent")
    strain = element_strains(model.nodes, model.elements, scale * first.displacement)[there, 0]
    far = built.far.strain_x * path.onset_load
    far_error = float(np.max(np.abs(strain - far))) / abs(far)
    if not far_error < FAR_FIELD_TOLERANCE:
        raise BondRunError(f"Midway between the repair and the panel's end the strain is not yet the laminate's far from a repair (off by "
                           f"{far_error:.1%}): the panel is too short around the repair for this model; give a longer panel")

    fell = path.first_peak(LET_GO_FALL)
    read = fell if fell is not None else path.peak
    equilibrium = float(np.max(np.abs(_force_along(built, read.load, read.displacement) - read.load))) / abs(read.load)
    if not equilibrium < EQUILIBRIUM_TOLERANCE:
        raise BondRunError(f"The plies' forces along the load do not add up to the load at every station (off by {equilibrium:.2e} of it)")

    def state(point) -> BondState:
        return _state(built, point.load, point.displacement, point.damage, point.spent)

    loads = np.concatenate([[0.0], path.loads])
    movements = np.concatenate([[0.0], [float(built.end_load @ point.displacement) for point in path.points]])
    return BondAnswer(built, path, float(seconds), onset, onset_pair, None if fell is None else state(fell), state(path.peak),
                      state(path.points[-1]), "let_go" if fell is not None else path.ended, loads, movements, far_error, equilibrium)


def run_bond(repair: Repair, *, element_size_m: float | None = None, fine_m: float | None = None, steps: int = 1500) -> BondAnswer:
    """Build the repair's bond model, follow its path and read the answer: `build_bond_model`, `follow_bond`, `bond_answer`."""
    built = build_bond_model(repair, element_size_m=element_size_m, fine_m=fine_m)
    path, seconds = follow_bond(built, steps=steps)
    return bond_answer(built, path, seconds)


def bond_report(answer: BondAnswer, units: str) -> dict:
    """The followed bond as plain numbers in a unit system (the systems of the engine's units.py): the model, the law, the
    two checks, the onset, the load at which the bond lets go with the bond's state there, and the curve: at every state
    of the path the load, the movement of the panel's end, the length of bond past its strength (softening or parted) and
    the length parted. A fracture energy is in the system's force per length, as the repair file states it."""
    if units not in UNIT_SYSTEMS:
        raise BondRunError(f"units must be one of {', '.join(UNIT_SYSTEMS)}, got {units!r}")
    system = UNIT_SYSTEMS[units]
    length, stress, force = system["length"][0], system["stress"][0], system["N"][0]
    built, path, law = answer.built, answer.path, answer.built.law
    model = built.model

    def where(pair: int) -> dict:
        stretch = answer.stretch_of(pair)
        return {"part": stretch.name, "step": stretch.step, "r": float(built.pair_r_m[pair]) / length}

    def state(found: BondState, lines: bool) -> dict:
        out = {"load": found.load / force, "end_movement": found.end_movement_m / length, "spent": found.spent / force,
               "softening_length": answer.softening_m(found) / length, "parted_length": answer.parted_m(found) / length,
               "damaged_length": float(model.weight[found.damage > 0].sum()) / length}
        if lines:
            out["lines"] = []
            for stretch in built.stretches:
                damage, share = found.damage[stretch.pairs], model.weight[stretch.pairs]
                out["lines"].append({"name": stretch.name, "step": stretch.step, "r": (built.pair_r_m[stretch.pairs] / length).tolist(),
                                     "shear": (found.shear_pa[stretch.pairs] / stress).tolist(), "peel": (found.peel_pa[stretch.pairs] / stress).tolist(),
                                     "damage": damage.tolist(), "length": float(share.sum()) / length,
                                     "softening_length": float(share[(damage > 0) & (damage < 1)].sum()) / length,
                                     "parted_length": float(share[damage >= 1].sum()) / length})
        return out

    worst = int(np.argmax(answer.last.damage))
    return {
        "units": {"length": system["length"][1], "stress": system["stress"][1], "force": system["N"][1], "energy": system["N"][1],
                  "stiffness": f"{system['stress'][1]}/{system['length'][1]}"},
        "model": {"solver": "anisotropy_fea.bond_solver", "element": "eight-node plane element, four integration points",
                  "elements": int(len(model.elements)), "nodes": int(len(model.nodes)), "pairs": int(len(model.weight)),
                  "bond_length": built.bond_length_m / length, "element_size": float(np.max(np.diff(built.mesh.r_lines_m))) / length,
                  "fine_size": built.fine_m / length, "seconds": round(answer.seconds, 2), "states": len(path.points), "solves": path.solves,
                  "steps_cut": path.cuts},
        "law": {"peel_stiffness": law.peel_stiffness / (stress / length), "shear_stiffness": law.shear_stiffness / (stress / length),
                "peel_strength": law.peel_strength / stress, "shear_strength": law.shear_strength / stress,
                "peel_energy": law.peel_energy / force, "shear_energy": law.shear_energy / force,
                "onset_opening": law.onset_opening / length, "onset_slip": law.onset_slip / length,
                "final_opening": law.final_opening / length, "final_slip": law.final_slip / length},
        "checks": {"far_field": answer.far_field_error, "equilibrium": answer.equilibrium_error},
        "onset": where(answer.onset_pair) | {"load": answer.onset.load / force, "shear": float(answer.onset.shear_pa[answer.onset_pair]) / stress,
                                             "peel": float(answer.onset.peel_pa[answer.onset_pair]) / stress,
                                             "lines": state(answer.onset, True)["lines"]},
        "let_go": None if answer.let_go is None else state(answer.let_go, True),
        "largest": state(answer.largest, False),
        "last": state(answer.last, False) | {"most_damaged": where(worst) | {"damage": float(answer.last.damage[worst])}},
        "ended": answer.ended,
        "curve": {"end_movement": (answer.end_movements_m / length).tolist(), "load": (answer.loads / force).tolist(),
                  "damaged_length": [0.0] + [float(model.weight[point.damage > 0].sum()) / length for point in path.points],
                  "parted_length": [0.0] + [float(model.weight[point.damage >= 1].sum()) / length for point in path.points]},
    }


ENDED_WORDS = {"gone": "the whole bond parted and the load never fell",
               "steps": "the path was not followed to a load at which the bond lets go: the run's limit of steps came first",
               "stalled": "the path could not be followed further, so no load at which the bond lets go was found"}


def headline(report: dict) -> str:
    """The run in one line."""
    u, onset, fell = report["units"], report["onset"], report["let_go"]
    line = f"The bond first softens at {onset['load']:.4g} {u['force']} (r = {onset['r']:.4g} {u['length']}, {onset['part']})"
    if fell is not None:
        return line + (f"; in this model it lets go at {fell['load']:.4g} {u['force']}, with {fell['softening_length']:.3g} {u['length']} of its "
                       f"{report['model']['bond_length']:.3g} {u['length']} softening and {fell['parted_length']:.3g} {u['length']} parted. "
                       "Not the repair's strength: the plies are not checked for damage")
    return line + f"; the largest load reached is {report['largest']['load']:.4g} {u['force']}: {ENDED_WORDS[report['ended']]}"


def main(argv: list[str] | None = None) -> int:
    """`python -m anisotropy_fea.repair_bond <repair.toml> [--out DIR] [--size mm] [--fine mm] [--steps N]`: follow the bond of
    a repair file until it lets go and print the answer in the file's units; with --out, keep repair-bond.json there, the
    report with the run in one line as its `headline`. Ends with status 2 and "refused: ..." when the repair cannot be read,
    modelled or followed, or fails a check of the run."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m anisotropy_fea.repair_bond", description="Follow a stepped patch repair's bond until it lets go (ADR-0137).")
    parser.add_argument("repair", type=FilePath, help="the repair, a TOML file (engine/examples/example-patch-repair.toml) or the same table as .json")
    parser.add_argument("--out", type=FilePath, help="folder for repair-bond.json")
    parser.add_argument("--size", type=float, help="the longest element along the slice, mm")
    parser.add_argument("--fine", type=float, help="the element length beside every edge, mm")
    parser.add_argument("--steps", type=int, default=1500, help="the most states the path may have (default 1500)")
    args = parser.parse_args(argv)
    try:
        case = read_repair_file(args.repair)
        repair, _ = repair_from_dict(case)
        answer = run_bond(repair, element_size_m=None if args.size is None else args.size * MM, fine_m=None if args.fine is None else args.fine * MM,
                          steps=args.steps)
        report = bond_report(answer, case["units"])
    except (BondRunError, RepairError, ShapeError, OSError) as error:
        print(f"refused: {(str(error).splitlines() or [type(error).__name__])[0]}")
        return REFUSED
    u, model, law = report["units"], report["model"], report["law"]
    length, stress, force = u["length"], u["stress"], u["force"]
    print(case.get("title") or args.repair.stem)
    print(f"{model['elements']} elements, {model['pairs']} pairs along {model['bond_length']:.4g} {length} of bond, elements {model['fine_size']:.3g} to "
          f"{model['element_size']:.3g} {length} long; {model['states']} states, {model['solves']} solves, {model['seconds']:.1f} s")
    print(f"The bond: {law['shear_strength']:g} {stress} and {law['shear_energy']:g} {u['energy']} in shear (gone at a slip of {law['final_slip']:.3g} {length}), "
          f"{law['peel_strength']:g} {stress} and {law['peel_energy']:g} {u['energy']} in peel (gone at an opening of {law['final_opening']:.3g} {length})")
    print(f"Checks: far-field strain within {report['checks']['far_field']:.1e} of the laminate theory's; the plies' forces add up to the load "
          f"within {report['checks']['equilibrium']:.1e} of it")
    print(f"\n{headline(report)}")
    fell = report["let_go"]
    if fell is not None:
        print(f"\n{'bond at that load':<36} {'length':>8} {'softening':>10} {'parted':>8} {'largest shear':>14} {'largest peel':>13}   ({length}, {stress})")
        for line in fell["lines"]:
            print(f"{line['name']:<36} {line['length']:>8.4g} {line['softening_length']:>10.3g} {line['parted_length']:>8.3g} "
                  f"{np.abs(line['shear']).max():>14.4g} {max(line['peel']):>13.4g}")
    worst = report["last"]["most_damaged"]
    print(f"\nWhen the run stops, at {report['last']['load']:.4g} {force}, the bond is most damaged at r = {worst['r']:.4g} {length} ({worst['part']})")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / REPORT).write_text(json.dumps(report | {"headline": headline(report)}, indent=1), encoding="utf-8")
        print(f"\n{args.out / REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
