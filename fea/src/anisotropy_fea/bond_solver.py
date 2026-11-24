"""A plane of elastic solids joined by a bond that softens and lets go, followed along its load path (ADR-0137).

The solids are eight-node plane elements with four integration points, the element CalculiX solves a repair's slice with
(CPE8R, ADR-0132). The bond is a set of node pairs, one node on each side of it: each pair is one integration point of the
bond, with the length of bond it stands for as its weight (Simpson's rule along an element's edge: a sixth, four sixths and a
sixth of the edge for its two corners and its middle). SI units throughout: m, Pa, N per metre of width, J/m^2.

The law (`BondLaw`) is two straight lines in peel and in shear, six numbers: a stiffness, a strength and a fracture energy
for each. With the opening dn (positive when the two sides part) and the slip ds of a pair:

    onset     (Kn <dn> / peel strength)^2 + (Ks ds / shear strength)^2 = 1
    failure   G_I / peel energy + G_II / shear energy = 1

Between the two the stresses fall in a straight line along the direction the pair is moving in, so that the energy spent is
the failure line's. One number, the damage d from 0 to 1, lowers both stiffnesses: tn = (1 - d) Kn dn, ts = (1 - d) Ks ds.
Damage only grows. A pair pressed together (dn < 0) carries the pressure with its whole stiffness, and its shear follows the
shear law alone.

The path (`follow`): every load and every prescribed strain is one unit load times a load factor. The answer is elastic up to
the first pair at onset, found by scaling one linear solve. From there the factor rises in small steps while the bond spends
little energy, and then every step spends a set amount of energy in the bond and the load factor is one of the step's
unknowns (Gutierrez 2004; Verhoosel, Remmers and Gutierrez 2009). For a bond that unloads to the origin, as this one does,
the energy spent in a step from (u0, f0) to (u, f) is (f0 F.(u - u0) - (f - f0) F.u0) / 2, with F the unit load. A step that
must spend energy cannot stall where the load peaks or where load and displacement both fall back, and nothing artificial is
added to get through.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


class BondError(ValueError):
    """The bond's numbers or the model cannot be solved as stated, or the path could not be followed."""


@dataclass(frozen=True)
class BondLaw:
    """The six numbers of a bond: stiffness (Pa/m), strength (Pa) and fracture energy (J/m^2), in peel and in shear."""

    peel_stiffness: float
    shear_stiffness: float
    peel_strength: float
    shear_strength: float
    peel_energy: float
    shear_energy: float

    def __post_init__(self) -> None:
        for name in ("peel_stiffness", "shear_stiffness", "peel_strength", "shear_strength", "peel_energy", "shear_energy"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise BondError(f"The bond's {name.replace('_', ' ')} must be a positive number")
        # a law whose energy is under the elastic energy at onset would have the bond gone before it reached its strength
        if not self.peel_energy > self.peel_strength**2 / (2 * self.peel_stiffness):
            raise BondError("The bond's peel energy is under the energy it holds when it reaches its peel strength: "
                            f"it must be above {self.peel_strength**2 / (2 * self.peel_stiffness):.4g} J/m^2")
        if not self.shear_energy > self.shear_strength**2 / (2 * self.shear_stiffness):
            raise BondError("The bond's shear energy is under the energy it holds when it reaches its shear strength: "
                            f"it must be above {self.shear_strength**2 / (2 * self.shear_stiffness):.4g} J/m^2")

    @property
    def onset_opening(self) -> float:
        return self.peel_strength / self.peel_stiffness

    @property
    def onset_slip(self) -> float:
        return self.shear_strength / self.shear_stiffness

    @property
    def final_opening(self) -> float:
        return 2 * self.peel_energy / self.peel_strength

    @property
    def final_slip(self) -> float:
        return 2 * self.shear_energy / self.shear_strength

    def index(self, opening: np.ndarray, slip: np.ndarray) -> np.ndarray:
        """How near an undamaged pair is to onset: 1 at onset, in proportion to the opening and the slip below it."""
        return np.sqrt((self.peel_stiffness * np.maximum(opening, 0.0) / self.peel_strength) ** 2
                       + (self.shear_stiffness * slip / self.shear_strength) ** 2)

    def traction(self, opening: np.ndarray, slip: np.ndarray, damage: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """The peel and the shear stress of each pair (Pa) and its damage after this state, from its opening and slip (m)
        and the damage it had."""
        opening, slip = np.asarray(opening, dtype=float), np.asarray(slip, dtype=float)
        kn, ks = self.peel_stiffness, self.shear_stiffness
        parted = np.maximum(opening, 0.0)
        size = np.sqrt(parted**2 + slip**2)
        safe = np.where(size > 0, size, 1.0)
        cn = np.where(size > 0, parted / safe, 0.0)
        cs = np.where(size > 0, np.abs(slip) / safe, 1.0)
        onset = 1.0 / np.sqrt((kn * cn / self.peel_strength) ** 2 + (ks * cs / self.shear_strength) ** 2)
        final = 2.0 / (onset * (kn * cn**2 / self.peel_energy + ks * cs**2 / self.shear_energy))
        now = np.where(size > onset, final * (size - onset) / (safe * (final - onset)), 0.0)
        d = np.clip(np.maximum(now, damage), 0.0, 1.0)
        return np.where(opening > 0, (1 - d) * kn * opening, kn * opening), (1 - d) * ks * slip, d


Q8_SIGNS = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1], [0, -1], [1, 0], [0, 1], [-1, 0]], dtype=float)
GAUSS = 1 / math.sqrt(3)


def rectangle(first_lines, second_lines, start: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A rectangle of eight-node elements between the given lines along each axis. Returns the nodes (n, 2), the elements
    (m, 8) and the node at every corner and middle, `ids[i, j]` with i and j counting half elements (-1 at an element's
    centre, which has no node). Node numbers begin at `start`, so that several rectangles make one model."""
    first_lines, second_lines = np.asarray(first_lines, dtype=float), np.asarray(second_lines, dtype=float)
    if len(first_lines) < 2 or len(second_lines) < 2 or np.any(np.diff(first_lines) <= 0) or np.any(np.diff(second_lines) <= 0):
        raise BondError("A rectangle's lines must rise, two or more along each axis")
    n1, n2 = len(first_lines) - 1, len(second_lines) - 1
    fine1, fine2 = np.empty(2 * n1 + 1), np.empty(2 * n2 + 1)
    fine1[0::2], fine1[1::2] = first_lines, 0.5 * (first_lines[:-1] + first_lines[1:])
    fine2[0::2], fine2[1::2] = second_lines, 0.5 * (second_lines[:-1] + second_lines[1:])
    keep = ~((np.arange(2 * n1 + 1)[:, None] % 2 == 1) & (np.arange(2 * n2 + 1)[None, :] % 2 == 1))
    ids = -np.ones(keep.shape, dtype=int)
    ids[keep] = start + np.arange(keep.sum())
    grid1, grid2 = np.meshgrid(fine1, fine2, indexing="ij")
    nodes = np.column_stack([grid1[keep], grid2[keep]])
    e1, e2 = np.meshgrid(np.arange(n1), np.arange(n2), indexing="ij")
    i, j = 2 * e1.ravel(), 2 * e2.ravel()
    elements = np.column_stack([ids[i, j], ids[i + 2, j], ids[i + 2, j + 2], ids[i, j + 2],
                                ids[i + 1, j], ids[i + 2, j + 1], ids[i + 1, j + 2], ids[i, j + 1]])
    return nodes, elements, ids


def _shape_derivatives(xi: float, eta: float) -> tuple[np.ndarray, np.ndarray]:
    """The eight shape functions' derivatives along the element's own two axes at one point: corners first, counterclockwise,
    then the middle of each edge from the first corner's."""
    dxi, deta = np.empty(8), np.empty(8)
    for a in range(4):
        sx, sy = Q8_SIGNS[a]
        dxi[a] = 0.25 * sx * (1 + sy * eta) * (2 * sx * xi + sy * eta)
        deta[a] = 0.25 * sy * (1 + sx * xi) * (sx * xi + 2 * sy * eta)
    for a in (4, 6):
        sy = Q8_SIGNS[a, 1]
        dxi[a], deta[a] = -xi * (1 + sy * eta), 0.5 * sy * (1 - xi * xi)
    for a in (5, 7):
        sx = Q8_SIGNS[a, 0]
        dxi[a], deta[a] = 0.5 * sx * (1 - eta * eta), -eta * (1 + sx * xi)
    return dxi, deta


def _strain_matrices(nodes: np.ndarray, elements: np.ndarray):
    """For each of the four integration points: every element's strain matrix (m, 3, 16) and its area weight (m,). The
    strains are along the first axis, along the second, and the engineering shear between them."""
    corners = nodes[elements]
    for xi in (-GAUSS, GAUSS):
        for eta in (-GAUSS, GAUSS):
            dxi, deta = _shape_derivatives(xi, eta)
            jx, jy = np.einsum("a,eak->ek", dxi, corners), np.einsum("a,eak->ek", deta, corners)
            det = jx[:, 0] * jy[:, 1] - jx[:, 1] * jy[:, 0]
            if np.any(det <= 0):
                raise BondError("An element is turned inside out: its corners must run counterclockwise")
            d1 = (jy[:, 1, None] * dxi - jx[:, 1, None] * deta) / det[:, None]
            d2 = (-jy[:, 0, None] * dxi + jx[:, 0, None] * deta) / det[:, None]
            b = np.zeros((len(elements), 3, 16))
            b[:, 0, 0::2], b[:, 1, 1::2] = d1, d2
            b[:, 2, 0::2], b[:, 2, 1::2] = d2, d1
            yield b, det


def _element_dofs(elements: np.ndarray) -> np.ndarray:
    dofs = np.empty((len(elements), 16), dtype=int)
    dofs[:, 0::2], dofs[:, 1::2] = 2 * elements, 2 * elements + 1
    return dofs


def solid_stiffness(nodes: np.ndarray, elements: np.ndarray, stiffness: np.ndarray) -> sp.csr_matrix:
    """The solids' stiffness matrix. `stiffness` is (m, 3, 3): each element's, between the three plane stresses and strains."""
    ke = np.zeros((len(elements), 16, 16))
    for b, weight in _strain_matrices(nodes, elements):
        ke += np.einsum("eki,ekl,elj,e->eij", b, stiffness, b, weight)
    dofs = _element_dofs(elements)
    size = 2 * len(nodes)
    return sp.coo_matrix((ke.ravel(), (np.repeat(dofs, 16, axis=1).ravel(), np.tile(dofs, (1, 16)).ravel())), shape=(size, size)).tocsr()


def stress_load(nodes: np.ndarray, elements: np.ndarray, stress: np.ndarray) -> np.ndarray:
    """The nodal forces that balance a stress already in each element, (m, 3): the forces the element puts on its nodes."""
    fe = np.zeros((len(elements), 16))
    for b, weight in _strain_matrices(nodes, elements):
        fe += np.einsum("eki,ek,e->ei", b, stress, weight)
    force = np.zeros(2 * len(nodes))
    np.add.at(force, _element_dofs(elements).ravel(), fe.ravel())
    return force


def element_strains(nodes: np.ndarray, elements: np.ndarray, displacement: np.ndarray) -> np.ndarray:
    """Each element's strains, (m, 3): the mean of its four integration points."""
    ue = displacement[_element_dofs(elements)]
    total = np.zeros((len(elements), 3))
    for b, _ in _strain_matrices(nodes, elements):
        total += np.einsum("eki,ei->ek", b, ue)
    return total / 4


def simpson_weights(lengths: np.ndarray) -> np.ndarray:
    """The weights of the pairs along a line of element edges of the given lengths, one pair at each corner and each middle:
    2 n + 1 of them."""
    lengths = np.asarray(lengths, dtype=float)
    weights = np.zeros(2 * len(lengths) + 1)
    weights[0:-2:2] += lengths / 6
    weights[1::2] += 4 * lengths / 6
    weights[2::2] += lengths / 6
    return weights


@dataclass
class BondModel:
    """Solids and a bond. `under` and `over` are the two nodes of each pair and `weight` the length of bond it stands for
    (m); the bond's normal is the second axis, from `under` to `over`. `fixed` are the degrees of freedom held at zero (2 n
    for node n along the first axis, 2 n + 1 along the second) and `unit_load` the nodal forces at a load factor of 1.
    `damage` is each pair's at the start (1 where the bond is already gone, as along a crack)."""

    nodes: np.ndarray
    elements: np.ndarray
    stiffness: np.ndarray
    under: np.ndarray
    over: np.ndarray
    weight: np.ndarray
    law: BondLaw
    fixed: np.ndarray
    unit_load: np.ndarray
    damage: np.ndarray | None = None
    matrix: sp.csr_matrix = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.nodes, self.elements = np.asarray(self.nodes, dtype=float), np.asarray(self.elements, dtype=int)
        self.under, self.over, self.weight = np.asarray(self.under, dtype=int), np.asarray(self.over, dtype=int), np.asarray(self.weight, dtype=float)
        if not (len(self.under) == len(self.over) == len(self.weight)) or len(self.under) == 0:
            raise BondError("A bond needs pairs of nodes, each with its weight")
        if np.any(self.weight <= 0):
            raise BondError("Every pair of a bond must stand for some length of it")
        self.fixed = np.unique(np.asarray(self.fixed, dtype=int))
        self.damage = np.zeros(len(self.weight)) if self.damage is None else np.asarray(self.damage, dtype=float).copy()
        self.matrix = solid_stiffness(self.nodes, self.elements, np.asarray(self.stiffness, dtype=float))

    @property
    def size(self) -> int:
        return 2 * len(self.nodes)

    def jumps(self, displacement: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Each pair's opening and slip, m."""
        return (displacement[2 * self.over + 1] - displacement[2 * self.under + 1],
                displacement[2 * self.over] - displacement[2 * self.under])

    def bond_forces(self, displacement: np.ndarray, damage: np.ndarray, tangent: bool = True):
        """The bond's forces on the nodes, its tangent stiffness (None unless asked) and the damage after this state."""
        opening, slip = self.jumps(displacement)
        tn, ts, after = self.law.traction(opening, slip, damage)
        ux, uy, ox, oy = 2 * self.under, 2 * self.under + 1, 2 * self.over, 2 * self.over + 1
        force = np.zeros(self.size)
        np.add.at(force, ox, self.weight * ts)
        np.add.at(force, oy, self.weight * tn)
        np.add.at(force, ux, -self.weight * ts)
        np.add.at(force, uy, -self.weight * tn)
        if not tangent:
            return force, None, after
        # the law's slopes by a small step in the slip and in the opening, from the damage the step began with
        h = 1e-7 * min(self.law.onset_opening, self.law.onset_slip)
        tn_s, ts_s, _ = self.law.traction(opening, slip + h, damage)
        tn_n, ts_n, _ = self.law.traction(opening + h, slip, damage)
        slopes = {(0, 0): (ts_s - ts) / h, (0, 1): (ts_n - ts) / h, (1, 0): (tn_s - tn) / h, (1, 1): (tn_n - tn) / h}
        side = {"u": (ux, uy), "o": (ox, oy)}
        rows, cols, values = [], [], []
        for a in "uo":
            for c in "uo":
                for i in (0, 1):
                    for j in (0, 1):
                        rows.append(side[a][i])
                        cols.append(side[c][j])
                        values.append((1.0 if a == c else -1.0) * self.weight * slopes[(i, j)])
        matrix = sp.coo_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))), shape=(self.size, self.size)).tocsr()
        return force, matrix, after


@dataclass(frozen=True)
class PathPoint:
    """One state on the path: the load factor, the work-conjugate movement (unit load . displacement), the energy the bond
    has spent so far per metre of width (J/m), each pair's damage, and the displacements."""

    load: float
    movement: float
    spent: float
    damage: np.ndarray
    displacement: np.ndarray


@dataclass(frozen=True)
class Path:
    """A followed path. `onset_load` is the load factor at which the first pair reaches onset; `points` begin there.
    `ended` says why the path stopped: "stopped" (the caller's test), "gone" (no bond left), "steps" (the step limit) or
    "stalled" (no further step could be found: the path is not complete, and whoever reads it must say so)."""

    onset_load: float
    points: tuple[PathPoint, ...]
    ended: str
    solves: int
    cuts: int

    @property
    def loads(self) -> np.ndarray:
        return np.array([point.load for point in self.points])

    @property
    def movements(self) -> np.ndarray:
        return np.array([point.movement for point in self.points])

    @property
    def peak(self) -> PathPoint:
        """The state of the largest load on the path."""
        return max(self.points, key=lambda point: point.load)

    def first_peak(self, drop: float = 0.01) -> PathPoint | None:
        """The first state after which the load falls by more than `drop` of it before rising above it again: the first
        load the model cannot hold. None when the load never falls that far."""
        loads = self.loads
        best = 0
        for k in range(1, len(loads)):
            if loads[k] > loads[best]:
                best = k
            elif loads[k] < (1 - drop) * loads[best]:
                return self.points[best]
        return None


def follow(model: BondModel, *, first_energy: float | None = None, largest_energy: float | None = None, steps: int = 4000,
           tolerance: float = 1e-7, iterations: int = 10, target_iterations: int = 4, stop=None, keep_every: int = 1) -> Path:
    """Follow the model's path from no load. `largest_energy` caps the energy a step may spend (J per metre of width);
    `stop(point, path_so_far)` ends the path when it returns True. `keep_every` thins the points kept (the peak load's and
    the last are always kept)."""
    fixed = model.fixed
    free = np.setdiff1d(np.arange(model.size), fixed)
    unit, unit_free = model.unit_load, model.unit_load[free]
    if not np.any(unit_free):
        raise BondError("The model has no load")
    solid_free = model.matrix[free][:, free].tocsr()
    counters = {"solves": 0, "cuts": 0}

    def state(displacement: np.ndarray, damage: np.ndarray):
        force, bond, after = model.bond_forces(displacement, damage)
        return (model.matrix @ displacement + force)[free], (solid_free + bond[free][:, free]).tocsc(), after

    damage = model.damage.copy()
    u = np.zeros(model.size)
    for _ in range(25):  # the unit load's elastic answer; which pairs are pressed may change on the way
        internal, tangent, _ = state(u, damage)
        step = spla.splu(tangent).solve(unit_free - internal)
        counters["solves"] += 1
        u[free] += step
        if np.linalg.norm(step) <= 1e-10 * np.linalg.norm(u[free]):
            break
    else:
        raise BondError("The elastic answer did not settle: the pairs pressed together keep changing")
    opening, slip = model.jumps(u)
    index = np.where(damage > 0, 0.0, model.law.index(opening, slip))
    if not index.max() > 0:
        raise BondError("The load does not stress the bond at all")
    onset_load = 1.0 / float(index.max())
    load = 0.98 * onset_load
    u = load * u
    stored = 0.5 * load * float(unit @ u)
    if first_energy is None:
        first_energy = 1e-4 * abs(stored)
    energy = first_energy
    spent = 0.0
    points = [PathPoint(load, float(unit @ u), 0.0, damage.copy(), u.copy())]
    by_energy = False
    load_step = 0.02 * load
    last = None  # the last step taken: displacement change, load change, energy spent
    ended = "steps"
    taken = 0
    for _ in range(steps * 4):
        if taken >= steps:
            break
        u0, load0 = u, load
        if by_energy and last is not None and last[2] > 0:
            scale = min(4.0, max(0.1, energy / last[2]))
            trial, trial_load = u0 + scale * last[0], load0 + scale * last[1]
        elif by_energy:
            trial, trial_load = u0.copy(), load0
        elif last is not None and last[1] != 0:
            trial, trial_load = u0 + (load_step / last[1]) * last[0], load0 + load_step
        else:
            trial, trial_load = u0 * (1 + load_step / load0), load0 + load_step
        converged, used = False, 0
        for iteration in range(iterations):
            internal, tangent, after = state(trial, damage)
            residual = trial_load * unit_free - internal
            gap = 0.0 if not by_energy else 0.5 * (load0 * float(unit @ (trial - u0)) - (trial_load - load0) * float(unit @ u0)) - energy
            if np.linalg.norm(residual) <= tolerance * np.linalg.norm(model.matrix @ trial) and abs(gap) <= 1e-4 * energy:
                converged, used = True, iteration
                break
            if abs(trial_load) > 5 * abs(load0):
                break
            factor = spla.splu(tangent)
            counters["solves"] += 1
            correction = factor.solve(residual)
            if by_energy:
                unit_answer = factor.solve(unit_free)
                slope = 0.5 * load0 * unit_free
                change = -(gap + slope @ correction) / (slope @ unit_answer - 0.5 * float(unit @ u0))
                trial[free] += correction + change * unit_answer
                trial_load += change
            else:
                trial[free] += correction
        if not converged:
            counters["cuts"] += 1
            if by_energy:
                energy *= 0.25
                if energy < 1e-12 * abs(stored):
                    ended = "stalled"  # the steps shrank to nothing: the path so far is returned, and says so
                    break
            elif load_step > 1e-4 * abs(load0):
                load_step *= 0.5
            else:
                by_energy = True  # the load will not rise further in steps of load: let the energy lead
                energy = max(last[2] if last else 0.0, 1e-9 * abs(stored))
            continue
        step_spent = 0.5 * (load0 * float(unit @ (trial - u0)) - (trial_load - load0) * float(unit @ u0))
        work = 0.5 * (load0 + trial_load) * float(unit @ (trial - u0))
        last = (trial - u0, trial_load - load0, step_spent)
        u, load, damage = trial, trial_load, after
        spent += step_spent
        taken += 1
        if not by_energy and step_spent > 0.02 * abs(work):
            by_energy = True
            energy = min(step_spent, energy) if largest_energy is None else min(step_spent, largest_energy)
        elif by_energy:
            energy *= min(2.0, max(0.5, (target_iterations / max(used, 1)) ** 0.5))
            if largest_energy is not None:
                energy = min(energy, largest_energy)
        points.append(PathPoint(load, float(unit @ u), spent, damage.copy(), u.copy()))
        if np.all(damage >= 1.0):
            ended = "gone"
            break
        if stop is not None and stop(points[-1], points):
            ended = "stopped"
            break
    if keep_every > 1:
        peak = max(range(len(points)), key=lambda k: points[k].load)
        points = [point for k, point in enumerate(points) if k % keep_every == 0 or k in (peak, len(points) - 1)]
    return Path(onset_load, tuple(points), ended, counters["solves"], counters["cuts"])
