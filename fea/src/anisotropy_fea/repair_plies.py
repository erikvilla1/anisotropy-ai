"""A repair's slice carried until the plies and the bond together cannot hold the load (ADR-0141).

The slice and the bond are the bond run's own (`repair_bond`, ADR-0140); what is added is that every ply may damage
(`ply_damage`): a break across the fibres and a crack along them, each softening over its fracture energy. The load is
raised from the first softening of anything, bond or ply, until the slice cannot hold it, and what the run gives is the
largest load it does hold, the smallest it does not, and what had failed at the largest.

A ply's crack softens over a band of elements one element wide (`ply_damage`), so an element must be short enough along
the load for its crack to soften in it at all: `longest_element` is that length, and the run shortens its elements to it.
The load's own direction matters, so a crack whose plane holds it is not followed: in a 0 degree ply the matrix crack, in a
90 degree ply the fibre break.

    python -m anisotropy_fea.repair_plies <repair.toml> [--out DIR] [--size mm] [--fine mm] [--meshes N] [--finer N]
        [--seconds S] [--most N] [--result outcome.json --progress progress.json]

The command prints the answer in the file's units and, with --out, keeps `repair-plies.json` there. With --meshes it runs
the same repair on that many meshes, each a little finer, and reports the spread of the load: a load this run gives is to
be read with that spread beside it (AGENTS.md, no number without its mesh study). As a job of the page (ADR-0141 amendment
1) it is one mesh at a time, the run's own or one `--finer`, within a time (`--seconds`) and a number of elements
(`--most`), and it writes its stage and its outcome as a wing's check does (`--progress`, `--result`).

What this does not do: a ply parting from its neighbour (delamination), a ply crushing across its fibres, and a saturation
of matrix cracking. Where the panel's far field itself cracks, the number of cracked elements grows with the mesh, so the
mesh study is what says whether a load may be read.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path as FilePath

import numpy as np
from anisotropy_engine.repair.description import Repair, RepairError, RepairMaterial
from anisotropy_engine.repair.repair_file import ply_needs, repair_from_dict
from anisotropy_engine.repair.solid import ply_compliance
from anisotropy_engine.units import UNIT_SYSTEMS

from .bond_solver import BondError, BondModel
from .ply_damage import Held, Holder, PlyDamage
from .repair_bond import BondRunError, RepairBondModel, build_bond_model, check_far_field, unit_system
from .repair_model import MOST_ELEMENTS
from .repair_shape import MM, REFUSED, ShapeError, read_repair_file

REPORT = "repair-plies.json"
# Of the longest element a crack can soften in at all, what the run takes. An element at the bound softens over no strain
# at all and one near it over almost none, which takes the load the slice holds far below where a finer mesh puts it (the
# example repair gave 852 N/mm at four fifths of the bound against 1,186 to 1,206 N/mm on three finer meshes, ADR-0141). At
# this fraction a crack softens over at least two and a half times the strain at which it begins.
SHORTEN = 0.4
RISE = 1.15  # the load is raised by this much at a time while the slice holds it
WITHIN = 0.005  # of the load: how near the largest load held and the smallest not held are brought
MESH_STEP = 0.8  # each mesh of a study has elements this much shorter than the one before
EQUILIBRIUM_TOLERANCE = 1e-3  # of the load: how nearly the plies' forces must add up to it at the largest load held
STAGES = ("build", "soften", "raise", "close")  # a job's steps: the model, the first softening held, the load raised, the largest closed in on
OUTPUT_KEY = "repair_plies"  # the key a job's outcome lists the report under
CRACKS = ("fibre_tension", "fibre_compression", "matrix")  # a ply's damages as the report names them
CRACK_WORDS = {"fibre_tension": "broken across the fibres", "fibre_compression": "crushed along the fibres", "matrix": "cracked along the fibres"}
PART_WORDS = {"parent": "the laminate", "patch": "the patch", "cover": "a cover ply"}


def material_energies(material: RepairMaterial) -> tuple[float, float, float, float]:
    """A ply material's four fracture energies, J/m^2."""
    energies = material.energies
    if energies is None:
        raise BondRunError(f"The plies of {material.name!r} have no fracture energies")
    return energies.fibre_tension, energies.fibre_compression, energies.matrix_tension, energies.matrix_shear


def longest_element(repair: Repair) -> float:
    """The longest element along the load whose every crack can still soften in it, m. A crack softens over a band as wide
    as the element, and its fracture energy must be above the energy the ply holds when it reaches its strength
    (G > X^2 b / 2 E), so the band, and with it the element, has an upper bound; the smallest bound of the four cracks of
    every material is the answer."""
    smallest = None
    for material in (repair.parent_material, repair.patch_material):
        lamina = material.lamina
        if lamina.strengths is None:
            raise BondRunError(f"The plies of {material.name!r} have no strengths")
        strengths = lamina.strengths
        fibre_t, fibre_c, matrix_t, matrix_s = material_energies(material)
        for energy, strength, modulus in ((fibre_t, strengths.F1t, lamina.E1), (fibre_c, strengths.F1c, lamina.E1),
                                          (matrix_t, strengths.F2t, lamina.E2), (matrix_s, strengths.F6, lamina.G12)):
            bound = 2 * energy * modulus / strength**2
            smallest = bound if smallest is None else min(smallest, bound)
    return float(smallest)


@dataclass(frozen=True)
class RepairPliesModel:
    """A repair's slice whose plies may damage. `built` is the bond run's own model of the slice; `model` is it again with
    the plies' damage and with the load on the panel's end alone (the stress the width strain makes is the plies' own now,
    and moves with their damage). `ply` names the ply of every element: its angle, and its number in the laminate or the
    patch as the slice's rectangles give them."""

    built: RepairBondModel
    model: BondModel
    plies: PlyDamage
    element_size_m: float
    kind: tuple[str, ...]
    angle_deg: np.ndarray
    ply: np.ndarray

    @property
    def repair(self) -> Repair:
        return self.built.repair

    @property
    def end(self) -> np.ndarray:
        """The movements along the load of the nodes on the panel's end. The run holds them to one movement: the end moves
        as one, and each ply there takes the share of the load its stiffness gives it, with its damage."""
        along = self.model.nodes[:, 0]
        return 2 * np.flatnonzero(np.isclose(along, along.max(), rtol=0.0, atol=1e-9 * along.max()))

    def place(self, element: int) -> dict:
        """Where an element is: the kind of part, its ply and angle, and its distance from the repair's middle (m)."""
        middle = self.model.nodes[self.model.elements[element]][:4, 0].mean()
        return {"kind": self.kind[element], "ply": int(self.ply[element]), "angle": float(self.angle_deg[element]), "r": float(middle)}

    def where(self, element: int, units: str = "mm-MPa") -> str:
        """Where an element is, in the customer's words and a unit system's length: the part, its ply and its distance from
        the repair's middle."""
        at = self.place(element)
        scale, label = unit_system(units)["length"]
        return f"{PART_WORDS[at['kind']]}, ply {at['ply']} at {at['angle']:g} degrees, {at['r'] / scale:.3g} {label} from the middle"


def _too_many(elements: int, most: int, size_m: float, units: str, at_least: bool = False) -> BondRunError:
    """The refusal of a slice larger than a run takes, with what makes it large (ADR-0141 amendment 1)."""
    scale, label = unit_system(units)["length"]
    return BondRunError(f"The slice would have {'more than ' if at_least else ''}{elements:,} elements, and this run takes at most {most:,}. For "
                        f"a crack to soften in them its elements are {size_m / scale:.3g} {label} long at most, over half the panel's length: "
                        "shorten the panel")


def build_plies_model(repair: Repair, *, element_size_m: float | None = None, fine_m: float | None = None, units: str = "SI",
                      most_elements: int | None = None) -> RepairPliesModel:
    """The model of a repair's slice whose plies may damage. `element_size_m` is the longest element along the slice, cut
    down to what lets every crack soften (`longest_element`); `fine_m` and `units` are as in `build_bond_model`. With
    `most_elements`, a slice with more elements than that is refused, one far larger before it is meshed."""
    needs = ply_needs(repair)
    if needs:
        raise BondRunError("To carry the repair until the plies and the bond cannot hold the load it needs "
                           + "; ".join(need["words"] for need in needs))
    longest = SHORTEN * longest_element(repair)
    size = longest if element_size_m is None else min(element_size_m, longest)
    if most_elements is not None and size > 0 and repair.panel_length_m / 2 / size > most_elements:  # at least this many columns
        raise _too_many(int(repair.panel_length_m / 2 / size), most_elements, size, units, at_least=True)
    built = build_bond_model(repair, element_size_m=size, fine_m=fine_m, units=units)
    if most_elements is not None and len(built.model.elements) > most_elements:
        raise _too_many(len(built.model.elements), most_elements, size, units)
    mesh, old = built.mesh, built.model
    count = len(old.elements)
    compliance, angle, strength, energy = np.empty((count, 6, 6)), np.empty(count), np.empty((count, 4)), np.empty((count, 4))
    kind, ply = [], np.empty(count, dtype=int)
    for element in range(count):
        part = mesh.regions[mesh.region[element]]
        material = repair.parent_material if part.kind == "parent" else repair.patch_material
        try:
            compliance[element] = ply_compliance(material.lamina, material.through)
        except RepairError as error:  # pragma: no cover - ply_needs has asked for the constants already
            raise BondRunError(str(error)) from error
        strengths = material.lamina.strengths
        angle[element], ply[element] = part.angle_deg, part.ply
        strength[element] = strengths.F1t, strengths.F1c, strengths.F2t, strengths.F6
        energy[element] = material_energies(material)
        kind.append(part.kind)
    plies = PlyDamage(compliance, angle, strength[:, 0], strength[:, 1], strength[:, 2], strength[:, 3], energy[:, 0], energy[:, 1],
                      energy[:, 2], energy[:, 3], np.ones(count, dtype=bool), built.far.strain_width)
    try:
        model = BondModel(old.nodes, old.elements, old.stiffness, old.under, old.over, old.weight, old.law, old.fixed, built.end_load,
                          plies=plies)
    except BondError as error:
        raise BondRunError(str(error)) from error
    return RepairPliesModel(built, model, plies, size, tuple(kind), angle, ply)


@dataclass(frozen=True)
class PliesState:
    """The slice at one load: the load per unit width (N/m), the movement of the panel's end along the load (m), how much of
    the bond has begun to soften and how much carries nothing, and for every element its three damages."""

    load: float
    end_movement_m: float
    softening_m: float
    parted_m: float
    fibre_tension: np.ndarray
    fibre_compression: np.ndarray
    matrix: np.ndarray


@dataclass(frozen=True)
class PliesAnswer:
    """A repair carried until its plies and its bond cannot hold the load.

    `onset` is the load at which anything first softens, `onset_words` what it was and `onset_place` where (None for the
    bond); `held` is the largest load the slice holds and `not_held` the smallest it does not, so the load it carries in this
    model lies between them. `ended` says how the search stopped: "closed" (the two loads are as near as asked), "levels"
    (the limit of loads tried came first) or "time" (the run's time came first); `not_held` is None when the time came before
    any load the slice does not hold was found, and `held` is then a load it holds and no more. `equilibrium_error` is the
    run's check, as a fraction."""

    built: RepairPliesModel
    seconds: float
    onset: float
    onset_words: str
    held: PliesState
    not_held: float | None
    why: str
    levels: tuple[PliesState, ...]
    solves: int
    equilibrium_error: float
    ended: str = "closed"
    onset_place: dict | None = None
    onset_crack: str = "bond"

    @property
    def load(self) -> float:
        """The load the repair carries in this model: the largest the slice holds."""
        return self.held.load

    @property
    def spread(self) -> float | None:
        """How wide the bracket around that load is, as a fraction of it; None when no load it does not hold was found."""
        return None if self.not_held is None else (self.not_held - self.held.load) / self.held.load


def _state(built: RepairPliesModel, held: Held) -> PliesState:
    weight, bond = built.model.weight, held.damage.bond
    fibre_t, fibre_c, matrix = held.damage.plies
    return PliesState(float(held.load), float(built.built.end_load @ held.displacement),
                      float(weight[(bond > 0) & (bond < 1)].sum()), float(weight[bond >= 1].sum()),
                      fibre_t.copy(), fibre_c.copy(), matrix.copy())


def _forces_along(built: RepairPliesModel, held: Held) -> np.ndarray:
    """The force along the load the plies carry across every station (N/m), at a state with its damage: each element's mean
    stress along the load times its height, summed through the thickness."""
    plies, mesh = built.plies, built.built.mesh
    own = plies.own_strain(held.displacement, held.load)
    pulled = plies.pulled(own, held.damage.plies, (np.ones(len(own), dtype=bool),) * 2)
    stress = plies.stress(own, held.damage.plies, pulled)
    slice_stress = plies.in_slice_axes(stress)[:, 0]
    height = np.diff(mesh.z_lines_m)[mesh.cell[:, 1]]
    return np.bincount(mesh.cell[:, 0], weights=slice_stress * height, minlength=len(mesh.r_lines_m) - 1)


def run_plies(repair: Repair, *, element_size_m: float | None = None, fine_m: float | None = None, most: int = 60,
              solves: int = 400, units: str = "SI", seconds: float | None = None, most_elements: int | None = None,
              on_stage=None) -> PliesAnswer:
    """Build the repair's slice with its plies able to damage and raise the load until it cannot hold it. Before any load is
    raised the elastic slice is held to ADR-0140's far-field check, so a panel too short round its repair is refused in the
    time of one solve. `units` is the system a refusal states its numbers in.

    `seconds` is the time the whole run is given (ADR-0141 amendment 1): when it comes, the load being tried is dropped,
    since nothing is known of it, and the answer is what was found by then, `ended` by "time". `most_elements` refuses a
    larger slice before anything is solved. `on_stage` is called with each of `STAGES` as it begins."""
    started = time.perf_counter()
    until = None if seconds is None else started + seconds
    stage = on_stage or (lambda name: None)
    force, label = unit_system(units)["N"]
    stage("build")
    built = build_plies_model(repair, element_size_m=element_size_m, fine_m=fine_m, units=units, most_elements=most_elements)
    try:
        holder = Holder(built.model, tied=built.end)
    except BondError as error:
        raise BondRunError(str(error)) from error
    check_far_field(built.built, holder.unit, 1.0)
    stage("soften")
    damage = holder.begin()
    first = holder.hold(holder.onset_load / (1 + 1e-3), damage, solves, until)
    if first.why == "time":
        raise BondRunError("The run's time came before the slice had been carried to its first softening: a shorter panel makes a model it gets through")
    if not first.held:
        raise BondRunError("The slice does not hold the load at which it first softens: the model cannot be carried from there")
    plies = built.plies
    fibre, matrix = plies.nearness(plies.own_strain(holder.unit, 1.0), damage.plies)
    # the first softening is a ply's when a ply reaches its onset at the load the whole model first softens at
    ply_first = holder.onset_load >= min(1.0 / max(fibre.max(), 1e-300), 1.0 / max(matrix.max(), 1e-300)) * (1 - 1e-9)
    place, crack = None, "bond"
    if ply_first:
        element = int(np.argmax(np.where(fibre > matrix, fibre, matrix)))
        crack = "fibre" if fibre[element] > matrix[element] else "matrix"
        place = built.place(element)
        onset_words = ("a break across the fibres of " if crack == "fibre" else "a crack along the fibres of ") + built.where(element, units)
    else:
        onset_words = "the bond, " + built.built.stretches[0].name if len(built.built.stretches) == 1 else "the bond"
    held, not_held, why, ended = [first], None, "held", "levels"
    stage("raise")
    for _ in range(most):
        last = held[-1]
        if not_held is not None and not_held <= last.load * (1 + WITHIN):
            ended = "closed"
            break
        aim = last.load * RISE if not_held is None else 0.5 * (last.load + not_held)
        now = holder.hold(aim, last.damage, solves, until)
        if now.why == "time":  # nothing is known of this load: the answer is what was found before it
            ended = "time"
            break
        if now.held:
            held.append(now)
        else:
            if not_held is None:
                stage("close")
            not_held, why = now.load, now.why
    if not_held is None and ended != "time":
        raise BondRunError(f"The slice held every load tried, up to {held[-1].load / force:.4g} {label} of width")
    top = held[-1]
    error = float(np.max(np.abs(_forces_along(built, top) - top.load))) / abs(top.load)
    if not error < EQUILIBRIUM_TOLERANCE:
        raise BondRunError(f"At the largest load it holds the plies' forces along the load do not add up to the load at every station "
                           f"(off by {error:.2e} of it)")
    return PliesAnswer(built, time.perf_counter() - started, holder.onset_load, onset_words, _state(built, top),
                       None if not_held is None else float(not_held), why, tuple(_state(built, one) for one in held), holder.solves, error,
                       ended, place, crack)


def failed_table(answer: PliesAnswer) -> dict:
    """What had failed at the largest load the slice holds, as numbers in SI: the bond's lengths softening and parted, and
    for each of a ply's damages that has begun, how many elements, how many of them through, and where the worst is."""
    built, state = answer.built, answer.held
    plies = []
    for name in CRACKS:
        damage = getattr(state, name)
        begun = int((damage > 0).sum())
        if begun:
            plies.append({"crack": name, "elements": begun, "through": int((damage >= 1).sum()), "worst": built.place(int(np.argmax(damage)))})
    return {"bond": {"softening": state.softening_m, "parted": state.parted_m, "length": float(built.model.weight.sum())}, "plies": plies,
            "elements": len(built.model.elements)}


def what_failed(answer: PliesAnswer, units: str = "mm-MPa") -> list[str]:
    """What had failed at the largest load the slice holds, in the customer's words and a unit system's length, most of it
    first."""
    table = failed_table(answer)
    scale, label = unit_system(units)["length"]
    bond, words = table["bond"], []
    if bond["parted"] > 0:
        words.append(f"{bond['parted'] / scale:.3g} {label} of the {bond['length'] / scale:.3g} {label} of bond carries nothing any more")
    if bond["softening"] > 0:
        words.append(f"{bond['softening'] / scale:.3g} {label} of the bond is past its strength and still carrying")
    for row in table["plies"]:
        at = row["worst"]
        where = f"{PART_WORDS[at['kind']]}, ply {at['ply']} at {at['angle']:g} degrees, {at['r'] / scale:.3g} {label} from the middle"
        words.append(f"{row['elements']} of the {table['elements']} elements of ply are {CRACK_WORDS[row['crack']]} ({row['through']} of them "
                     f"through), the worst in {where}")
    return words or ["nothing had failed yet: the slice came apart within one step of the load"]


def mesh_study(repair: Repair, meshes: int, *, element_size_m: float | None = None, fine_m: float | None = None,
               units: str = "SI", **options) -> list[PliesAnswer]:
    """The same repair run on `meshes` meshes, each with elements `MESH_STEP` of the one before; `options` are `run_plies`'s."""
    answers = []
    size = element_size_m
    for _ in range(max(meshes, 1)):
        answer = run_plies(repair, element_size_m=size, fine_m=fine_m, units=units, **options)
        answers.append(answer)
        size = MESH_STEP * answer.built.element_size_m
    return answers


def plies_report(answer: PliesAnswer, units: str, study: list[PliesAnswer] | None = None) -> dict:
    """The run as a table of plain values in the given unit system, for the page and the report."""
    system = UNIT_SYSTEMS[units]
    length, force = 1 / system["length"][0], 1 / system["N"][0]
    built, repair = answer.built, answer.built.repair
    state, table = answer.held, failed_table(answer)
    report = {
        "units": {"system": units, "length": system["length"][1], "force": system["N"][1], "stress": system["stress"][1]},
        "model": {"elements": len(built.model.elements), "pairs": len(built.model.weight), "element_size": answer.built.element_size_m * length,
                  "fine_size": built.built.fine_m * length, "bond_length": float(built.model.weight.sum()) * length,
                  "longest_element": longest_element(repair) * length, "solves": answer.solves, "seconds": answer.seconds},
        "onset": {"load": answer.onset * force, "what": answer.onset_words, "crack": answer.onset_crack,
                  "place": None if answer.onset_place is None else {**answer.onset_place, "r": answer.onset_place["r"] * length}},
        "load": {"held": state.load * force, "not_held": None if answer.not_held is None else answer.not_held * force, "spread": answer.spread,
                 "why": answer.why, "end_movement": state.end_movement_m * length},
        "ended": answer.ended,
        "failed": what_failed(answer, units),
        "at_held": {"bond": {key: value * length for key, value in table["bond"].items()}, "elements": table["elements"],
                    "plies": [{**row, "worst": {**row["worst"], "r": row["worst"]["r"] * length}} for row in table["plies"]]},
        "levels": [{"load": one.load * force, "end_movement": one.end_movement_m * length, "bond_parted": one.parted_m * length,
                    "bond_softening": one.softening_m * length, "matrix_cracked": int((one.matrix > 0).sum()),
                    "fibre_broken": int((one.fibre_tension > 0).sum())} for one in answer.levels],
        "checks": {"equilibrium": answer.equilibrium_error},
    }
    if study:
        loads = np.array([one.load for one in study])
        report["study"] = {"meshes": [{"element_size": one.built.element_size_m * length, "elements": len(one.built.model.elements),
                                       "held": one.load * force, "not_held": None if one.not_held is None else one.not_held * force,
                                       "ended": one.ended} for one in study],
                           "spread": float((loads.max() - loads.min()) / loads.mean())}
    return report


ENDED_WORDS = {"levels": "the run's limit of loads tried came before the two were brought nearer",
               "time": "the run's time came before the two were brought nearer"}


def headline(report: dict) -> str:
    """The run in one line, in the report's units: the load held and the load not held to four figures, so the two can be
    told apart, and never as the repair's strength."""
    u, load = report["units"], report["load"]
    study = report.get("study")
    spread = f" ({study['spread']:.1%} across {len(study['meshes'])} meshes)" if study else ""
    first = f"the first softening is at {report['onset']['load']:.4g} {u['force']} ({report['onset']['what']})"
    if load["not_held"] is None:
        return (f"The slice carries at least {load['held']:.4g} {u['force']} in this model{spread}: the run's time came before a load it "
                f"cannot hold was found; {first}.")
    why = ENDED_WORDS.get(report.get("ended", "closed"))
    return (f"The slice carries {load['held']:.4g} {u['force']} in this model and not {load['not_held']:.4g}{spread}"
            + (f": {why}" if why else "") + f"; {first}.")


def _write(path: FilePath, data: dict) -> None:
    """A status file written whole: beside its place first, then moved there, so a reader never finds half of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(data), encoding="utf-8")
    partial.replace(path)


def main(argv: list[str] | None = None) -> int:
    """`python -m anisotropy_fea.repair_plies <repair.toml> [--out DIR] [--size mm] [--fine mm] [--meshes N] [--finer N]
    [--seconds S] [--most N] [--result FILE --progress FILE]`: carry the repair until its plies and its bond cannot hold the
    load and print the answer in the file's units; with --out, keep repair-plies.json there, the report with the run in one
    line as its `headline`. Ends with status 2 and "refused: ..." when the repair cannot be read, modelled or carried.

    --finer N runs a mesh N steps finer than the run's own (each step `MESH_STEP` of the one before), --seconds gives each
    run a time and --most a limit on its elements. With --result and --progress the run is a job (ADR-0141 amendment 1): its
    stage is written as it goes and its outcome at the end, done, refused or stopped, as a wing's check writes them."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m anisotropy_fea.repair_plies",
                                     description="Carry a stepped patch repair until its plies and its bond cannot hold the load (ADR-0141).")
    parser.add_argument("repair", type=FilePath, help="the repair, a TOML file (engine/examples/example-patch-repair.toml) or the same table as .json")
    parser.add_argument("--out", type=FilePath, help="folder for repair-plies.json")
    parser.add_argument("--size", type=float, help="the longest element along the slice, mm (cut down to what lets every crack soften)")
    parser.add_argument("--fine", type=float, help="the element length beside every edge, mm")
    parser.add_argument("--meshes", type=int, default=1, help="run the repair on this many meshes, each finer, and report the spread (default 1)")
    parser.add_argument("--finer", type=int, default=0, help="run a mesh this many steps finer than the run's own (default 0)")
    parser.add_argument("--seconds", type=float, help="the time each run is given; a run not ended by then answers with what it found")
    parser.add_argument("--most", type=int, nargs="?", const=MOST_ELEMENTS, help=f"refuse a slice of more elements than this ({MOST_ELEMENTS:,} when no number is given)")
    parser.add_argument("--result", type=FilePath, help="a job's outcome, written at the end")
    parser.add_argument("--progress", type=FilePath, help="a job's stage, rewritten at every step")
    args = parser.parse_args(argv)
    job = args.result is not None
    done: list[str] = []
    current: list[str | None] = [None]

    def stage(name: str | None) -> None:
        if current[0] is not None and current[0] not in done:
            done.append(current[0])
        current[0] = name
        if args.progress is not None:
            _write(args.progress, {"stage": name, "done": list(done), "stages": list(STAGES), "outputs": {}, "coupon": None, "attempt": None})

    def end(status: str, message: str, outputs: dict | None = None) -> int:
        stage(None)
        if job:
            _write(args.result, {"status": status, "message": message, "result": message if status == "done" else None, "coupon": None,
                                 "attempt": None, "outputs": outputs or {}, "documents": None})
            print(f"{status}: {message}", flush=True)
        return 0 if status == "done" else REFUSED

    stage(None)
    try:
        case = read_repair_file(args.repair)
        repair, _ = repair_from_dict(case)
        units = case["units"]
        fine = None if args.fine is None else args.fine * MM
        size = None if args.size is None else args.size * MM
        if args.finer > 0:
            size = MESH_STEP ** args.finer * min(SHORTEN * longest_element(repair), size or float("inf"))
        options = {"units": units, "seconds": args.seconds, "most_elements": args.most, "on_stage": stage}
        study = mesh_study(repair, args.meshes, element_size_m=size, fine_m=fine, **options) if args.meshes > 1 else None
        answer = study[0] if study else run_plies(repair, element_size_m=size, fine_m=fine, **options)
        report = plies_report(answer, units, study)
    except (BondRunError, BondError, RepairError, ShapeError, OSError) as error:
        words = (str(error).splitlines() or [type(error).__name__])[0]
        print(f"refused: {words}")
        return end("refused", words)
    except Exception as error:  # a fault of ours or the machine's: a job ends with the cause in its log and row, a command as it would
        if not job:
            raise
        return end("stopped", f"The repair could not be carried: {(str(error).splitlines() or [type(error).__name__])[0]}")
    u, model, load = report["units"], report["model"], report["load"]
    print(case.get("title") or args.repair.stem)
    print(f"{model['elements']} elements {model['fine_size']:.3g} to {model['element_size']:.3g} {u['length']} long (a crack softens in an element "
          f"up to {model['longest_element']:.3g} {u['length']}), {model['pairs']} pairs along {model['bond_length']:.4g} {u['length']} of bond; "
          f"{model['solves']} solves, {model['seconds']:.1f} s")
    print(headline(report))
    print(f"What had failed at {load['held']:.4g} {u['force']}:")
    for line in report["failed"]:
        print(f"  {line}")
    if report.get("study"):
        print("The same repair on finer meshes:")
        for mesh in report["study"]["meshes"]:
            not_held = "no load found" if mesh["not_held"] is None else f"{mesh['not_held']:.4g}"
            print(f"  {mesh['elements']:6d} elements, {mesh['element_size']:.3g} {u['length']}: carries {mesh['held']:.4g}, not {not_held}")
    print(f"Check: the plies' forces add up to the load within {report['checks']['equilibrium']:.1e} of it.")
    outputs = {}
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / REPORT).write_text(json.dumps({**report, "headline": headline(report)}, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.out / REPORT}")
        outputs = {OUTPUT_KEY: str((args.out / REPORT).resolve())}
    return end("done", headline(report), outputs)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
