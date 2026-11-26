"""A plate's whole answer with its shape followed as the load rises (ADR-0142, step 2; fea/docs/theory.md, Sections 14.7 to 14.11).

`large_displacement.py` asks CalculiX for a history at a few probes, for the cases that hold it to published answers. This module asks
for the whole plate, for the run an engineer starts with the Analysis step's switch on: CalculiX solves the spec's eight-node twin with a
large-displacement step and prints, at ten levels of the load, the displacement of every node, the reaction at every held node and the
Lagrangian strain at every integration point. From those strains, and nothing else of CalculiX's, come the numbers of the laminate:

- the strain of the middle of the plate and its curvature in each element, the straight line through the element's points in the height;
- every ply's stress in its own axes and its failure index, by the engine's ply law and criteria on that line, exactly as our kernel's
  own solve is read (`recovery.py`): the second Piola-Kirchhoff stress is the stress in the axes the ply has carried along as it turned;
- the section forces and moments, by the laminate's A, B and D, and the shear forces, each ply's shear stiffness times its own strain.

The result is written as the fields file the page reads for any solve (`fields.field_data`), with what only a followed solve has under
`summary["followed"]`: the load against the largest displacement, level by level, beside the straight line our linear kernel gives; the
failure index at each level; and, for a criterion a ply reaches before the full load, the share of the load at which it is reached.

A followed answer does not scale. The factor R of a ply is still one over its failure index at the loads applied, but R times the loads
is no longer where the ply fails, so no loading at first-ply failure is written unless the solve itself passed it.
"""

from __future__ import annotations

import dataclasses
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .abaqus_reader import parse_deck, to_si as deck_to_si, validate_deck
from .calculix import CalculixError, run_calculix
from .explain import explanation
from .femodel import FEModel, build_model
from .fields import applied_loading, field_data
from .kernel import solve_deck
from .large_displacement import eight_node_twin
from .mesh import KernelError, Mesh, layer_shear_stiffness, mesh_from_deck
from .model import Deck
from .quality import element_quality
from .recovery import deck_f12_star, element_ply_states, strength_ratios
from .results import ShellSolution
from .shell import element_sections, jacobians_all
from .spec import TEST_CODES, CouponSpec, element_estimate, follows_shape, full_angles, is_isotropic, layup_text
from .units import UNIT_LABEL, deck_units_of, from_si, unit_factors
from .write_abaqus import write_abaqus
from .write_calculix import LargeDisplacement, write_calculix

LEVELS = tuple(round(0.1 * i, 1) for i in range(1, 11))  # the fractions of the load the plate is read at
MOST_LAYERS = 13  # CalculiX 2.21 stops on a composite shell of 14 layers or more and solves 13 (ADR-0117 amendment 1)
MOST_BRICKS = 10_000  # solid elements, one per element and ply: 3,200 follow their load in 24 s and print 41 MB, 12,800 in 107 s and 163 MB (2026-11-25)
SOLVE_TIMEOUT_S = 480.0  # inside the hosted job's limit of twelve minutes, with room for the linear steps before it
JOB = "followed"
CORNERS = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))  # an element's corners in its own coordinates, as it lists its nodes
HEADER = re.compile(r"^(?P<name>[a-z][a-z ]*?)\s*\([^)]*\)\s*for set (?P<set>\S+) and time\s+(?P<time>\S+)$")
SOLVER_WORDS = "the plies are read from CalculiX's strains by our composite layer"


class FollowedError(ValueError):
    """A plate that cannot be followed here, or a run whose output does not hold the plate."""


class Stopped(FollowedError):
    """CalculiX stopped before the whole load. The message is for the engineer and names no program; `reached` is the last fraction of
    the load it printed (0 when none) and `detail` the solver's own words, for the run's log."""

    def __init__(self, message: str, reached: float = 0.0, detail: str = ""):
        super().__init__(message)
        self.reached = reached
        self.detail = detail


@dataclass(frozen=True)
class PlateLevel:
    """The whole plate at one fraction of its load, in SI, as CalculiX printed it and as its strains reduce in the height."""

    fraction: float
    displacement: np.ndarray  # (n, 3) m: every node of the eight-node mesh
    reaction: np.ndarray  # (n, 3) N: at the nodes of the support regions, zero elsewhere
    strain: np.ndarray  # (ne, 3): the Lagrangian strain of the middle of the plate, eps_x, eps_y and the engineering shear gamma_xy
    curvature: np.ndarray  # (ne, 3) 1/m: the slope of that strain in the height, the shear doubled as well
    shear: np.ndarray  # (ne, layers, 2): each ply's mean transverse shear strain, gamma_xz and gamma_yz
    fit: float  # how far the strain at an element's centre lies from its line in the height, at most, over the largest such strain


def why_not(spec: CouponSpec) -> str | None:
    """Why this plate is not followed here, in words for the setup check; None when it can be. Judged from the counts, before meshing."""
    layers = 1 if is_isotropic(spec) else len(full_angles(spec))
    if layers > MOST_LAYERS:
        return (f"the laminate has {layers} plies; the solver that follows the shape takes at most {MOST_LAYERS} in a shell: turn nonlinear "
                "geometry off to solve this plate")
    bricks = element_estimate(spec) * layers
    if bricks > MOST_BRICKS:
        g = spec.geometry
        f = unit_factors(spec.units) if spec.si else {"length": 1.0}
        fits = math.sqrt(g.length * g.width * layers / MOST_BRICKS) / f["length"]
        step = 10 ** math.floor(math.log10(fits) - 1)
        size = float(f"{math.ceil(fits / step) * step:.2g}")
        return (f"the mesh has about {element_estimate(spec):,} elements of {layers} {'ply' if layers == 1 else 'plies'}; following the shape takes at "
                f"most {MOST_BRICKS // layers:,} elements of this laminate: use an element size of {size:g} {UNIT_LABEL[spec.units]['length']} or more")
    return None


# --- what CalculiX printed --------------------------------------------------------------------------


def printed_blocks(path: Path | str) -> Iterator[tuple[str, str, float, np.ndarray]]:
    """Every block of a `.dat`, one at a time and nothing kept: what is printed, the set's name in capitals, the fraction of the load, and
    the rows as numbers (the labels first). A file of a hundred megabytes is read in the memory of one block. A block whose rows are not
    all of one width, the last of a run that was stopped while writing, ends the reading."""
    def block(header: re.Match, rows: list[str]) -> tuple[str, str, float, np.ndarray] | None:
        width = len(rows[0].split())
        values = np.array(" ".join(rows).split(), dtype=float)
        if values.size != width * len(rows):
            return None
        return re.sub(r"\s+", " ", header["name"]), header["set"].upper(), float(header["time"]), values.reshape(len(rows), width)

    with open(path, encoding="utf-8", errors="replace") as lines:
        header: re.Match | None = None
        rows: list[str] = []
        for line in lines:
            text = line.strip()
            match = HEADER.match(text) if "for set" in text else None
            if text and match is None:  # a row of the block that is open, or a line outside any block
                if header is not None:
                    rows.append(text)
                continue
            if header is not None and rows:  # a blank line or the next header closes the block
                found = block(header, rows)
                if found is None:
                    return
                yield found
                header, rows = None, []
            if match is not None:
                header, rows = match, []
        if header is not None and rows:
            found = block(header, rows)
            if found is not None:
                yield found


def through_the_height(strains: np.ndarray, places: np.ndarray, elements: int, thickness: np.ndarray, length: float) -> tuple[np.ndarray, ...]:
    """The printed strains of every integration point reduced in the height, element by element: the straight line through the points,
    its value at the middle of the plate and its slope, for exx, eyy and exy (the shear doubled, as a laminate's law takes it); each
    ply's mean exz and eyz, doubled; and how far the points lie from the line. `strains` and `places` are the rows of the two blocks
    (element, point, then six strains or x, y, z); `thickness` the plies' in metres, bottom first; `length` the deck's unit in metres."""
    if strains.shape[0] % elements or strains.shape != (places.shape[0], 8) or places.shape[1] != 5:
        raise FollowedError(f"the run printed {strains.shape[0]} strain rows and {places.shape[0]} places for {elements} elements")
    points = strains.shape[0] // elements
    order = np.lexsort((strains[:, 1], strains[:, 0]))
    where = np.lexsort((places[:, 1], places[:, 0]))
    if not np.array_equal(strains[order, :2], places[where, :2]) or not np.array_equal(strains[order, 0].reshape(elements, points)[:, 0], np.arange(1, elements + 1)):
        raise FollowedError("the run's strains and their places do not name the same points of every element")
    e = strains[order, 2:].reshape(elements, points, 6)
    z = places[where, 4].reshape(elements, points) * length
    mean_z = z.mean(axis=1, keepdims=True)
    dz = z - mean_z
    slope = (dz[:, :, None] * e).sum(axis=1) / (dz ** 2).sum(axis=1)[:, None]
    middle = e.mean(axis=1) - slope * mean_z
    # how straight the strain is in the height: the mean of the points at each height (the element's centre there) against the line
    heights, at = np.unique(np.round(z / thickness.sum(), 9), return_inverse=True)
    level = (at.reshape(elements, points)[:, :, None] == np.arange(heights.size)).astype(float)
    share = level / np.maximum(level.sum(axis=1, keepdims=True), 1.0)
    in_plane = [0, 1, 3]
    centre = np.einsum("epg,epc->egc", share, e[:, :, in_plane])
    line = middle[:, None, in_plane] + slope[:, None, in_plane] * (heights * thickness.sum())[None, :, None]
    present = level.sum(axis=1) > 0.0
    largest = float(np.abs(centre).max())
    fit = float(np.abs(centre - line)[present].max() / largest) if largest > 0.0 else 0.0
    tops = np.cumsum(thickness) - thickness.sum() / 2.0
    ply = np.searchsorted(tops[:-1], z)  # the ply each point lies in, bottom first
    member = (ply[:, :, None] == np.arange(thickness.size)).astype(float)
    count = member.sum(axis=1)
    if np.any(count == 0.0):
        raise FollowedError("a ply of an element holds none of the run's integration points")
    shear = np.stack([2.0 * (member * e[:, :, c, None]).sum(axis=1) / count for c in (4, 5)], axis=-1)
    return (np.column_stack([middle[:, 0], middle[:, 1], 2.0 * middle[:, 3]]), np.column_stack([slope[:, 0], slope[:, 1], 2.0 * slope[:, 3]]), shear,
            np.float64(fit))


def read_plate(model: FEModel, path: Path | str) -> tuple[PlateLevel, ...]:
    """The levels a whole-plate `.dat` holds (`write_calculix(..., large=LargeDisplacement(whole=True))`), in the order the load rose,
    in SI. A level that lacks any of its blocks, the one a stopped run was writing, is left out."""
    f = unit_factors(deck_units_of(model.spec.units))
    mesh = model.mesh
    n, ne = mesh.node_count, mesh.element_count
    whole = model.section.elset.upper()
    supports = {name.upper() for name in model.support_sets if name in model.node_sets}
    thickness = np.array([ply.thickness_m for ply in model.section.plies], dtype=float)
    levels: dict[float, dict[str, Any]] = {}
    for quantity, set_name, fraction, values in printed_blocks(path):
        level = levels.setdefault(fraction, {"reaction": np.zeros((n, 3)), "held": set()})
        if quantity == "displacements" and set_name == "NALL":
            level["displacement"] = np.zeros((n, 3))
            level["displacement"][values[:, 0].astype(int) - 1] = values[:, 1:4] * f["length"]
        elif quantity == "forces" and set_name in supports:
            level["reaction"][values[:, 0].astype(int) - 1] = values[:, 1:4] * f["force"]
            level["held"].add(set_name)
        elif quantity in ("strains", "global coordinates") and set_name == whole:
            level[quantity] = values
            if "strains" in level and "global coordinates" in level:
                level["state"] = through_the_height(level.pop("strains"), level.pop("global coordinates"), ne, thickness, f["length"])
    out = []
    for fraction in sorted(levels):
        level = levels[fraction]
        if "displacement" in level and "state" in level and level["held"] == supports:
            strain, curvature, shear, fit = level["state"]
            out.append(PlateLevel(float(fraction), level["displacement"], level["reaction"], strain, curvature, shear, float(fit)))
    return tuple(out)


# --- the plate as our composite layer reads it ------------------------------------------------------


def serendipity_derivatives(xi: float, eta: float) -> np.ndarray:
    """dN/dxi and dN/deta (2, 8) of the eight-node element at a point: the four corners, then the midside nodes of edges 1-2, 2-3, 3-4, 4-1."""
    d = np.zeros((2, 8))
    for i, (a, b) in enumerate(CORNERS):
        d[0, i] = 0.25 * a * (1.0 + eta * b) * (2.0 * xi * a + eta * b)
        d[1, i] = 0.25 * b * (1.0 + xi * a) * (xi * a + 2.0 * eta * b)
    for i, (a, b) in enumerate(((0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), start=4):
        if a == 0.0:
            d[0, i], d[1, i] = -xi * (1.0 + eta * b), 0.5 * b * (1.0 - xi * xi)
        else:
            d[0, i], d[1, i] = 0.5 * a * (1.0 - eta * eta), -eta * (1.0 + xi * a)
    return d


@dataclass(frozen=True)
class Frame:
    """What stays the same at every level of one plate: the spec's model on four-node elements with the deck our kernel reads of it and
    the kernel's mesh, the eight-node twin CalculiX solves, and how the twin's nodes and plies map onto the kernel's."""

    spec: CouponSpec  # in SI
    model: FEModel  # four-node, the kernel's
    twin: FEModel  # eight-node, CalculiX's
    deck: Deck
    mesh: Mesh
    corner: np.ndarray  # (n,) the twin's node at each node of the kernel's mesh
    between: np.ndarray  # (m, 3) each midside node of the twin and the two corner nodes it lies between, as kernel nodes
    ply_shear: np.ndarray  # (layers, 2, 2) N/m: each ply's thickness times its transverse shear stiffness
    direct: np.ndarray  # (n8, 3) N: what the whole load puts straight onto held directions of the twin's nodes

    @property
    def units(self) -> str:
        return self.spec.units


def frame_of(spec: CouponSpec) -> Frame:
    """The frame of a plate's spec (in SI). Refused: a spec that does not ask for its shape to be followed, a plate `why_not` names, and a
    mesh whose two models do not share their corner nodes."""
    if not follows_shape(spec):
        raise FollowedError("the spec does not ask for its shape to be followed ([analysis] large_displacement = true)")
    refused = why_not(spec)
    if refused is not None:
        raise FollowedError(refused)
    first = spec if spec.mesh.element_order == 1 else spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 1})})
    model = build_model(first)
    twin = build_model(eight_node_twin(spec))
    units = deck_units_of(spec.units)
    parsed = parse_deck(write_abaqus(model, units))  # the deck our kernel reads, as every run of ours reads it back
    deck = dataclasses.replace(deck_to_si(parsed, units), notes=validate_deck(parsed))
    mesh = mesh_from_deck(deck, shell=True)
    used = np.unique(twin.mesh.corners)
    if mesh.node_count != used.size or not np.allclose(mesh.xy, twin.mesh.xy[used]) or not np.array_equal(used[mesh.connectivity], twin.mesh.corners):
        raise FollowedError("the eight-node mesh does not share its corner nodes with the four-node one")
    if len(mesh.sections) != 1:
        raise FollowedError(f"the plate holds {len(mesh.sections)} laminates; a followed plate is one laminate")
    index = -np.ones(twin.mesh.node_count, dtype=int)
    index[used] = np.arange(used.size)
    edges = {int(m): (int(index[a]), int(index[b])) for nodes, mids in zip(twin.mesh.corners, twin.mesh.midside)
             for k, m in enumerate(mids) for a, b in [(nodes[k], nodes[(k + 1) % 4])]}
    between = np.array([(m, a, b) for m, (a, b) in sorted(edges.items())], dtype=int).reshape(-1, 3)
    [section] = [s for part in deck.parts.values() for s in part.sections]
    ply_shear = np.array([thickness * stiffness for thickness, stiffness in layer_shear_stiffness(section, deck.materials, mesh.sections[0].name)])
    return Frame(spec, model, twin, deck, mesh, used, between, ply_shear, loads_on_held_nodes(twin))


def loads_on_held_nodes(twin: FEModel) -> np.ndarray:
    """What the model's whole load puts straight onto a held direction of a node, (n, 3) N on the eight-node mesh: a force stated there, and
    a pressure's share by the element's own weights (-1/12 of its area at a corner, 1/3 at a midside node, `femodel.consistent_area_loads`).
    CalculiX prints as a held node's reaction the force the plate puts on it and leaves this share out (seen on 2.21, 2026-11-25: the
    supports of a clamped plate of 20 by 20 elements under a pressure print 96.6 % of it, the missing 3.4 % the share of its edge nodes),
    so the supports carry the printed reaction less this. The shape before the load is used: a held edge has not moved."""
    mesh = twin.mesh
    held = np.zeros((mesh.node_count, 3), dtype=bool)
    for boundary in twin.boundaries:
        if boundary.target in twin.node_sets:
            for dof in range(boundary.dof_first, min(boundary.dof_last, 3) + 1):
                held[twin.node_sets[boundary.target], dof - 1] = True
    external = np.zeros((mesh.node_count, 3))
    for load in twin.loads:
        if load.dof > 3:
            continue
        label = load.target.rsplit(".", 1)[-1]
        nodes = twin.node_sets[load.target] if load.target in twin.node_sets else np.array([int(label) - 1])
        external[nodes, load.dof - 1] += load.value
    for pressure in twin.pressures:
        for e in np.asarray(twin.element_sets[pressure.elset], dtype=int).tolist():
            p = mesh.xy[mesh.corners[e]]
            area = 0.5 * abs(sum(p[i, 0] * p[(i + 1) % 4, 1] - p[(i + 1) % 4, 0] * p[i, 1] for i in range(4)))
            external[mesh.corners[e], 2] -= pressure.value * -area / 12.0
            external[mesh.midside[e], 2] -= pressure.value * area / 3.0
    return np.where(held, external, 0.0)


def midplane_slopes(frame: Frame, w: np.ndarray) -> np.ndarray:
    """The slope of the deflected middle of the plate at every node of the kernel's mesh, as the two rotations our shell carries:
    theta_x = dw/dy and theta_y = -dw/dx, the mean over the elements that share the node. `w` is the deflection of every node of the
    eight-node mesh; a shell node of CalculiX carries no rotation of its own."""
    mesh = frame.twin.mesh
    nodes = np.hstack([mesh.corners, mesh.midside])
    xy = mesh.xy[mesh.corners].reshape(-1, 4, 2)
    J, _ = jacobians_all(xy, CORNERS)  # (4, ne, 2, 2): rows d/dxi and d/deta of x and y
    total = np.zeros((frame.mesh.node_count, 2))
    count = np.zeros(frame.mesh.node_count)
    for c, (xi, eta) in enumerate(CORNERS):
        natural = w[nodes] @ serendipity_derivatives(xi, eta).T  # (ne, 2): dw/dxi, dw/deta
        slope = np.linalg.solve(J[c], natural[:, :, None])[:, :, 0]  # dw/dx, dw/dy
        at = frame.mesh.connectivity[:, c]
        np.add.at(total, at, np.column_stack([slope[:, 1], -slope[:, 0]]))
        np.add.at(count, at, 1.0)
    return total / count[:, None]


def shell_solution(frame: Frame, level: PlateLevel) -> ShellSolution:
    """One level as a solution of our flat shell, so that everything that reads our kernel's solve reads CalculiX's: the displacements at
    the corner nodes with the middle's slopes for rotations; the reactions, with the load put straight onto held nodes, a midside node's
    shared between the two corners it lies between; the strain of the middle and the curvature of every element; the section forces and moments by the laminate's own A, B
    and D on them; each ply's shear force its shear stiffness times its own strain, summed, and the shear strain their mean by thickness."""
    mesh = frame.mesh
    displacement = np.zeros((mesh.node_count, 5))
    displacement[:, :3] = level.displacement[frame.corner]
    displacement[:, 3:] = midplane_slopes(frame, level.displacement[:, 2])
    carried = level.reaction - level.fraction * frame.direct  # with what the load puts straight onto the held nodes (`loads_on_held_nodes`)
    reaction = np.zeros((mesh.node_count, 5))
    reaction[:, :3] = carried[frame.corner]
    if frame.between.size:
        shared = 0.5 * carried[frame.between[:, 0]]
        np.add.at(reaction[:, :3], frame.between[:, 1], shared)
        np.add.at(reaction[:, :3], frame.between[:, 2], shared)
    A, B, D, _ = element_sections(mesh)
    on = lambda stiffness, values: (stiffness @ values[:, :, None])[:, :, 0]  # noqa: E731
    thickness = np.array([ply.thickness_m for ply in frame.twin.section.plies], dtype=float)
    return ShellSolution(mesh=mesh, displacement=displacement, reaction=reaction, strain=level.strain, curvature=level.curvature,
                         shear_strain=np.einsum("k,eki->ei", thickness / thickness.sum(), level.shear),
                         section_force=on(A, level.strain) + on(B, level.curvature), moment=on(B, level.strain) + on(D, level.curvature),
                         shear_force=np.einsum("kij,ekj->ei", frame.ply_shear, level.shear), free_residual=0.0,
                         notes=(f"solved by CalculiX with the shape followed, at {level.fraction:g} of the load; {SOLVER_WORDS}",))


# --- the solve --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Followed:
    """A plate followed to its whole load: the frame, the levels in the order the load rose, and the run."""

    frame: Frame
    levels: tuple[PlateLevel, ...]
    version: str | None
    elapsed_s: float
    deck_path: Path


def follow_plate(spec: CouponSpec, workdir: Path | str, ccx: str | Path | None = None, timeout_s: float = SOLVE_TIMEOUT_S) -> Followed:
    """Solve the plate in CalculiX with its shape followed and read the whole plate at every level. `spec` is in SI. A run that stops
    before the whole load raises `Stopped` with the last level it reached and the plate's largest displacement there."""
    frame = frame_of(spec)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    deck = workdir / f"{JOB}.inp"
    deck.write_text(write_calculix(frame.twin, large=LargeDisplacement(first=LEVELS[0], at=LEVELS, whole=True)), encoding="utf-8", newline="\n")
    dat = workdir / f"{JOB}.dat"
    failure = None
    version, elapsed = None, 0.0
    try:
        run = run_calculix(deck, ccx=ccx, timeout_s=timeout_s)
        version, elapsed = run.version, run.elapsed_s
    except CalculixError as exc:
        failure = str(exc)
    levels = read_plate(frame.twin, dat) if dat.is_file() else ()
    if failure is None and levels and abs(levels[-1].fraction - 1.0) <= 1e-6:
        return Followed(frame, levels, version, elapsed, deck)
    lab = UNIT_LABEL[frame.units]
    timed_out = failure is not None and "did not finish" in failure
    detail = failure or "CalculiX printed no level"
    if not levels:
        raise Stopped("the solve with nonlinear geometry stopped before its first level, a tenth of the load: "
                      + (f"it ran past {timeout_s:g} s; a coarser mesh is followed sooner" if timed_out else
                         "no balance of forces was found; a smaller load runs, and so does a plate held against every rigid motion"), 0.0, detail)
    last = levels[-1]
    moved = float(from_si(np.linalg.norm(last.displacement, axis=1).max(), "length", frame.units))
    raise Stopped(f"the solve with nonlinear geometry reached {last.fraction * 100:.0f} % of the load and stopped there, the largest displacement "
                  f"{moved:.4g} {lab['length']}: " + (f"it ran past {timeout_s:g} s; a coarser mesh follows the whole load" if timed_out else
                                                      "no balance of forces was found past it (a plate that buckles or snaps through stops so); "
                                                      "a smaller load runs to its end"), last.fraction, detail)


# --- the fields the page reads -----------------------------------------------------------------------


def crossing(fractions: list[float], index: list[float]) -> tuple[float, float, float] | None:
    """Where a failure index that rises with the load first reaches one: the fraction of the load, by the straight line between the two
    levels it lies between (from nothing at no load), and those two fractions. None when it stays below one."""
    before_f, before_i = 0.0, 0.0
    for fraction, value in zip(fractions, index):
        if value >= 1.0:
            share = (1.0 - before_i) / (value - before_i) if value > before_i else 1.0
            return before_f + share * (fraction - before_f), before_f, fraction
        before_f, before_i = fraction, value
    return None


def followed_fields(followed: Followed) -> dict[str, Any]:
    """The followed plate as the page reads a solve (`fields.field_data` on the last level), the summary's loading at first-ply failure
    set right for an answer that does not scale, and `summary["followed"]`: the levels, the load against the largest displacement beside
    the linear answer of our kernel on the same model, and the failure index at each level."""
    frame, spec, units = followed.frame, followed.frame.spec, followed.frame.units
    last = shell_solution(frame, followed.levels[-1])
    f12 = deck_f12_star(frame.deck)
    states = element_ply_states(last)
    criteria = []
    for criterion in spec.output.fpf_criteria:
        try:
            strength_ratios(last, criterion, f12, states)
            criteria.append(criterion)
        except KernelError:
            pass
    coupon = {"designation": spec.coupon.designation if spec.coupon else None, "title": spec.title, "kind": spec.kind, "test": TEST_CODES[spec.kind][1],
              "layup": layup_text(spec)}
    data = field_data(frame.deck, last, units, criteria=tuple(criteria), quality=element_quality(frame.model.mesh.xy, frame.model.mesh.corners),
                      coupon=coupon)
    summary = data["summary"]
    lab = UNIT_LABEL[units]
    fractions = [level.fraction for level in followed.levels]
    solutions = [shell_solution(frame, level) for level in followed.levels[:-1]] + [last]
    # the load against the largest displacement: the node that moves most under the whole load, along the axis it mostly moves
    node, axis = int(summary["max_displacement"]["node"]), "xyz".index(summary["max_displacement"]["axis"])
    linear = np.zeros((frame.mesh.node_count, 3))  # our kernel's linear answer on the same deck; a plate loaded in its plane alone has no w
    moved = solve_deck(frame.deck).displacement[:, :3]
    linear[:, :moved.shape[1]] = moved
    linear_value = float(from_si(linear[node, axis], "length", units))
    linear_largest = float(from_si(np.linalg.norm(linear, axis=1).max(), "length", units))
    dof = int(summary["reaction"]["dof"])
    held = applied_loading(frame.deck, last)["nodes"]  # where the summary reads its reaction

    def carried(solution: ShellSolution) -> float:
        rows = solution.reaction[held] if held else solution.reaction
        return float(from_si(rows[:, dof - 1].sum(), "force", units))

    reactions = [carried(solution) for solution in solutions]
    index: dict[str, list[float]] = {}
    for criterion in criteria:
        index[criterion] = []
        for solution in solutions:
            ratio = strength_ratios(solution, criterion, f12).factor
            index[criterion].append(0.0 if math.isinf(ratio) else 1.0 / ratio)
    for table in (summary["fpf"], summary["fpf_gauge"]):
        for criterion, entry in table.items():
            found = crossing(fractions, index[criterion]) if table is summary["fpf"] else None
            entry["at_failure"] = None
            if found is not None:  # reached on the way: the share of the load, and what was applied and carried there
                share, low, high = found
                entry["at_failure"] = {"applied": float(share * summary["applied"]["value"]), "unit": summary["applied"]["unit"],
                                       "reaction": float(np.interp(share, [0.0, *fractions], [0.0, *reactions])), "reaction_unit": lab["force"],
                                       "every_load": True, "fraction": float(share), "between": [float(low), float(high)]}
    for worked in (summary.get("working") or {}).get("criteria", {}).values():  # the step from R to a loading holds for a linear model alone
        worked["steps"] = [step for step in worked["steps"] if step.get("id") != "loading"]
    value = float(from_si(last.displacement[node, axis], "length", units))
    largest = float(summary["max_displacement"]["value"])
    # how far following the shape moves the largest displacement from the linear answer's, in percent of the linear one, and which way
    change = 100.0 * (largest / linear_largest - 1.0) if linear_largest > 0.0 else None
    summary["followed"] = {
        "solver": f"CalculiX {followed.version}" if followed.version else "CalculiX",
        "seconds": round(followed.elapsed_s, 1),
        "fractions": fractions,
        "curve": {"node": node, "label": summary["max_displacement"]["label"], "xy": summary["max_displacement"]["xy"], "axis": "xyz"[axis],
                  "unit": lab["length"],
                  "values": [float(from_si(solution.displacement[node, axis], "length", units)) for solution in solutions],
                  "linear": [float(fraction * linear_value) for fraction in fractions]},
        "reaction": reactions,
        "index": index,
        "linear": {"value": linear_value, "largest": linear_largest, "ratio": value / linear_value if linear_value else None,
                   "change_percent": None if change is None else abs(change), "change": None if change is None else "smaller" if change < 0 else "larger"},
        "fit": max(level.fit for level in followed.levels),
        "law": "the Lagrangian strain and the second Piola-Kirchhoff stress, by the constants of small strain; a pressure follows the surface it "
               "presses on, a force keeps its direction",
    }
    data["kernel"] = "shell"
    data["solver"] = "calculix-followed"
    return data


def write_followed(followed: Followed, out: Path | str, stem: str) -> dict[str, Path]:
    """The followed plate's fields and the sentences about them, as `examples/build_model.py` writes our kernel's: `<stem>-fields.json`
    and `<stem>-explanation.json` in `out`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    data = followed_fields(followed)
    fields = out / f"{stem}-fields.json"
    fields.write_text(json.dumps(data), encoding="utf-8")
    words = explanation(data["summary"], data["coupon"], followed.frame.units, data["labels"])
    told = out / f"{stem}-explanation.json"
    told.write_text(json.dumps(words, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"fields": fields, "explanation": told}
