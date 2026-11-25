"""Plies that damage: a fibre break and a matrix crack as bands of softening elements (ADR-0141).

A ply's solid elements (`bond_solver`, eight nodes, four integration points) lose stiffness in two ways, each a crack the ply
can hold. In the ply's own axes, 1 along the fibres, 2 across them in the ply, 3 through the thickness:

    fibre     a crack across the fibres (its normal is 1). It begins when E1 e1 reaches the tensile strength, or -E1 e1 the
              compressive one, and lowers the ply's stiffness along 1 and in the shears 12 and 13.
    matrix    a crack along the fibres, through the ply (its normal is 2). It begins on the line
              (E2 <e2> / F2t)^2 + (G12 g12 / F6)^2 = 1 and lowers the stiffness along 2 (only while the crack is pulled open)
              and in the shears 12 and 23.

After onset the stress falls in a straight line with the strain, as a bond's does with its opening (`bond_solver.softening`:
the matrix crack is that law, with the strain times the band's width as the opening and the slip). A crack spends its
fracture energy per unit of its own area, whatever the mesh: the strain at which the stress reaches zero is set from the
width of the band of elements the crack forms in (the crack band of Bazant and Oh), so that a wider band softens over less
strain. The band is one column of integration points wide along the load, `BAND` of an element's length, and the crack's
plane cuts it at the ply's angle: the width across a fibre break is that length times |cos angle|, across a matrix crack
times |sin angle|. A crack whose plane holds the load's direction (a matrix crack in a 0 degree ply, a fibre break in a 90
degree ply) cannot form in a slice along the load and is not followed.

The damage enters the ply's compliance, the strains for its stresses: each damaged term is divided by (1 - d). So a ply
pulled along one axis alone carries (1 - d) times its elastic stress, the two-line law exactly, and the ply's stiffness
stays one an elastic solid may have. A matrix crack pressed shut carries the pressure with the whole stiffness. Damage only
grows. Nothing is done about a ply parting from its neighbour (delamination) or crushing across its fibres.

SI units throughout. A slice's width strain is the load factor times `width_strain`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

import scipy.sparse.linalg as spla

from .bond_solver import FACTOR, BondError, BondModel, _element_dofs, _strain_matrices, softening, stress_load

BAND = 1.0  # of an element's length along the load: the width of the band a crack forms in (the element: it damages as one)
RESIDUAL = 1e-6  # of its stiffness: what a wholly damaged term keeps, so that a broken ply does not leave the equations without an answer
ACROSS = 0.1  # a crack is followed only when its normal has at least this much of the load's direction in it
PLANE = (0, 2, 4, 1)  # of a slice's six stresses (xx, yy, zz, yz, xz, xy): the three in the plane, then the one across the width
SIX = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))  # a symmetric three by three's own terms


def strain_turn(angle_deg) -> np.ndarray:
    """The matrices (m, 6, 6) that give a ply's six strains in its own axes (11, 22, 33, 23, 13, 12, engineering shears) from
    those in the slice's axes (xx, yy, zz, yz, xz, xy), the ply turned by `angle_deg` about the thickness. Its transpose
    gives the slice's stresses from the ply's."""
    angle = np.radians(np.atleast_1d(np.asarray(angle_deg, dtype=float)))
    c, s = np.cos(angle), np.sin(angle)
    turn = np.zeros((len(angle), 6, 6))
    turn[:, 0, 0], turn[:, 0, 1], turn[:, 0, 5] = c * c, s * s, s * c
    turn[:, 1, 0], turn[:, 1, 1], turn[:, 1, 5] = s * s, c * c, -s * c
    turn[:, 2, 2] = 1.0
    turn[:, 3, 3], turn[:, 3, 4] = c, -s
    turn[:, 4, 3], turn[:, 4, 4] = s, c
    turn[:, 5, 0], turn[:, 5, 1], turn[:, 5, 5] = -2 * s * c, 2 * s * c, c * c - s * s
    return turn


@dataclass
class PlyDamage:
    """What the solids of a `BondModel` need to damage, one value for each element. `compliance` is the ply's elastic
    compliance in its own axes (m, 6, 6); the four strengths (Pa) and the four fracture energies (J/m^2) are the fibre's in
    tension and compression and the matrix crack's in tension and shear. `damages` says which elements may damage at all
    (an adhesive's or a part left elastic do not); `width_strain` is the strain across the width per unit of load factor."""

    compliance: np.ndarray
    angle_deg: np.ndarray
    fibre_tension: np.ndarray
    fibre_compression: np.ndarray
    matrix_tension: np.ndarray
    matrix_shear: np.ndarray
    fibre_tension_energy: np.ndarray
    fibre_compression_energy: np.ndarray
    matrix_tension_energy: np.ndarray
    matrix_shear_energy: np.ndarray
    damages: np.ndarray
    width_strain: float = 0.0
    band: float = BAND
    _b: list = field(init=False, repr=False, default_factory=list)

    def setup(self, nodes: np.ndarray, elements: np.ndarray) -> None:
        """Take the model's nodes and elements: the strain matrices, each element's length along the load, and from it the
        width of the band each crack forms in. Refused when a band is too wide for its ply to soften in."""
        m = len(elements)
        self.compliance = np.asarray(self.compliance, dtype=float)
        if self.compliance.shape != (m, 6, 6):
            raise BondError("The plies' compliance must be six by six for every element")
        names = ("angle_deg", "fibre_tension", "fibre_compression", "matrix_tension", "matrix_shear", "fibre_tension_energy",
                 "fibre_compression_energy", "matrix_tension_energy", "matrix_shear_energy")
        for name in names:
            setattr(self, name, np.broadcast_to(np.asarray(getattr(self, name), dtype=float), (m,)).copy())
        self.damages = np.broadcast_to(np.asarray(self.damages, dtype=bool), (m,)).copy()
        for name in names[1:]:
            if np.any(~(getattr(self, name)[self.damages] > 0)):
                raise BondError(f"A ply's {name.replace('_', ' ')} must be a positive number")
        self._b = [(b, weight) for b, weight in _strain_matrices(nodes, elements)]
        area = sum(weight for _, weight in self._b)
        self._mean = sum(b * (weight / area)[:, None, None] for b, weight in self._b)  # the mean strains of an element from its movements
        self._dofs = _element_dofs(elements)
        self._size = 2 * len(nodes)
        self._turn = strain_turn(self.angle_deg)
        self._e1, self._e2 = 1 / self.compliance[:, 0, 0], 1 / self.compliance[:, 1, 1]
        self._g23, self._g13, self._g12 = 1 / self.compliance[:, 3, 3], 1 / self.compliance[:, 4, 4], 1 / self.compliance[:, 5, 5]
        along = nodes[elements][:, :, 0]
        length = self.band * (along.max(axis=1) - along.min(axis=1))
        c, s = np.abs(np.cos(np.radians(self.angle_deg))), np.abs(np.sin(np.radians(self.angle_deg)))
        self.fibre_follows, self.matrix_follows = self.damages & (c >= ACROSS), self.damages & (s >= ACROSS)
        self.fibre_band, self.matrix_band = np.where(self.fibre_follows, length * c, 1.0), np.where(self.matrix_follows, length * s, 1.0)
        # the strain at which a crack's stress reaches zero, over the strain at onset: above 1 or the band cannot soften
        self._more_ft = 2 * self.fibre_tension_energy * self._e1 / (self.fibre_tension**2 * self.fibre_band)
        self._more_fc = 2 * self.fibre_compression_energy * self._e1 / (self.fibre_compression**2 * self.fibre_band)
        limits = [(self.fibre_follows, self._more_ft, "fibre break in tension"), (self.fibre_follows, self._more_fc, "fibre break in compression"),
                  (self.matrix_follows, 2 * self.matrix_tension_energy * self._e2 / (self.matrix_tension**2 * self.matrix_band), "matrix crack in tension"),
                  (self.matrix_follows, 2 * self.matrix_shear_energy * self._g12 / (self.matrix_shear**2 * self.matrix_band), "matrix crack in shear")]
        for follows, more, words in limits:
            if np.any(more[follows] <= 1.0):
                worst = float(np.min(more[follows]))
                raise BondError(f"An element is too long for a {words} to soften in it: its length along the load must be under "
                                f"{worst:.3g} of what it is (the fracture energy is spent before the strength is reached)")

    def begin(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """No damage: the fibre's in tension and in compression and the matrix crack's, one value for each element."""
        m = len(self.angle_deg)
        return np.zeros(m), np.zeros(m), np.zeros(m)

    def own_strain(self, displacement: np.ndarray, factor: float) -> np.ndarray:
        """Every element's six mean strains in its ply's axes (m, 6) for the model's displacements at a load factor."""
        strain = np.einsum("eki,ei->ek", self._mean, displacement[self._dofs])
        full = np.zeros((len(strain), 6))
        full[:, 0], full[:, 1], full[:, 2], full[:, 4] = strain[:, 0], factor * self.width_strain, strain[:, 1], strain[:, 2]
        return np.einsum("eij,ej->ei", self._turn, full)

    def _matrix_law(self, own: np.ndarray):
        """The matrix crack's two-line law at each element's strains: the size of its opening and slip, and the sizes at
        which the law begins to soften and ends, in those proportions."""
        band = self.matrix_band
        kn, ks, opening, slip = self._e2 / band, self._g12 / band, np.maximum(band * own[:, 1], 0.0), band * own[:, 5]
        size = np.sqrt(opening**2 + slip**2)
        safe = np.where(size > 0, size, 1.0)
        cn, cs = np.where(size > 0, opening / safe, 0.0), np.where(size > 0, np.abs(slip) / safe, 1.0)
        onset = 1.0 / np.sqrt((kn * cn / self.matrix_tension) ** 2 + (ks * cs / self.matrix_shear) ** 2)
        final = 2.0 / (onset * (kn * cn**2 / self.matrix_tension_energy + ks * cs**2 / self.matrix_shear_energy))
        return size, onset, final

    def damage(self, own: np.ndarray, before: tuple[np.ndarray, np.ndarray, np.ndarray]):
        """Every element's damage after its strains in the ply's axes (m, 6), from the damage it had."""
        e1, e2, g12 = own[:, 0], own[:, 1], own[:, 5]
        ft, fc, mx = before

        def line(ratio, more):
            now = np.where(ratio > 1, more * (ratio - 1) / (np.maximum(ratio, 1.0) * (more - 1)), 0.0)
            return np.clip(now, 0.0, 1.0)

        ft = np.where(self.fibre_follows, np.maximum(ft, line(self._e1 * e1 / self.fibre_tension, self._more_ft)), ft)
        fc = np.where(self.fibre_follows, np.maximum(fc, line(-self._e1 * e1 / self.fibre_compression, self._more_fc)), fc)
        band = self.matrix_band
        cracked = softening(self._e2 / band, self._g12 / band, self.matrix_tension, self.matrix_shear, self.matrix_tension_energy,
                            self.matrix_shear_energy, band * e2, band * g12, mx)
        return ft, fc, np.where(self.matrix_follows, cracked, mx)

    def nearness(self, own: np.ndarray, damage: tuple[np.ndarray, np.ndarray, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        """How near each element is to damaging further, whatever damage it has: its strains over the strains, in the same
        proportions, at which its damage would grow (1 or more where it grows already; 0 where the crack is not followed or
        has nothing left to lose). The fibre's, then the matrix crack's."""
        ft, fc, mx = damage

        def held(amount, more):  # the strain, over the onset's, up to which a damage of this amount has been
            return more / (more - np.minimum(amount, 1 - 1e-12) * (more - 1))

        fibre = np.maximum(np.where(ft < 1, self._e1 * own[:, 0] / (self.fibre_tension * held(ft, self._more_ft)), 0.0),
                           np.where(fc < 1, -self._e1 * own[:, 0] / (self.fibre_compression * held(fc, self._more_fc)), 0.0))
        size, onset, final = self._matrix_law(own)
        matrix = np.where(mx < 1, size / (onset * held(mx, final / onset)), 0.0)
        return np.where(self.fibre_follows, fibre, 0.0), np.where(self.matrix_follows, matrix, 0.0)

    def _own_stiffness(self, damage, pulled) -> np.ndarray:
        """Each element's stiffness in its ply's axes (m, 6, 6) with its damage: the damaged terms of the compliance divided
        by what is left. `pulled` says of each crack whether it is pulled open (the fibre's, the matrix's)."""
        ft, fc, mx = damage
        fibre = np.minimum(np.where(pulled[0], ft, fc), 1 - RESIDUAL)
        matrix = np.minimum(mx, 1 - RESIDUAL)
        normal = self.compliance[:, :3, :3].copy()
        normal[:, 0, 0] /= 1 - fibre
        normal[:, 1, 1] /= np.where(pulled[1], 1 - matrix, 1.0)
        own = np.zeros((len(mx), 6, 6))
        own[:, :3, :3] = np.linalg.inv(normal)
        own[:, 3, 3] = self._g23 * (1 - matrix)
        own[:, 4, 4] = self._g13 * (1 - fibre)
        own[:, 5, 5] = self._g12 * (1 - fibre) * (1 - matrix)
        return own

    def pulled(self, own: np.ndarray, damage, pulled) -> tuple[np.ndarray, np.ndarray]:
        """Whether each element's cracks are pulled open at these strains: the sign of the stress on each."""
        stress = np.einsum("eij,ej->ei", self._own_stiffness(damage, pulled)[:, :3, :3], own[:, :3])
        return stress[:, 0] > 0, stress[:, 1] > 0

    def stiffness(self, damage, pulled) -> np.ndarray:
        """Each element's stiffness in the slice's axes (m, 6, 6) with its damage."""
        return np.einsum("eji,ejk,ekl->eil", self._turn, self._own_stiffness(damage, pulled), self._turn)

    def stress(self, own: np.ndarray, damage, pulled) -> np.ndarray:
        """Each element's six mean stresses in its ply's axes (m, 6) at these strains, with its damage."""
        return np.einsum("eij,ej->ei", self._own_stiffness(damage, pulled), own)

    def in_slice_axes(self, stress: np.ndarray) -> np.ndarray:
        """Stresses given in each element's ply axes (m, 6) in the slice's axes (xx, yy, zz, yz, xz, xy)."""
        return np.einsum("eji,ej->ei", self._turn, stress)


@dataclass(frozen=True)
class Damage:
    """The damage of a whole model: each pair's of the bond, and each element's three of the plies (None when the solids do
    not damage)."""

    bond: np.ndarray
    plies: tuple[np.ndarray, np.ndarray, np.ndarray] | None


@dataclass(frozen=True)
class Held:
    """What became of a model under one load. `held` says whether the damage stopped growing with the model still
    carrying the load; `damage` and `displacement` are the state it stopped in (or the last one reached)."""

    load: float
    held: bool
    damage: Damage
    displacement: np.ndarray
    movement: float
    solves: int
    why: str  # "stopped" (the damage stopped growing), "parted" (the model came apart) or "solves" (it was still growing at the limit)


class Holder:
    """Holds a model under a load and lets its damage grow until it stops. At each turn the model is solved as an elastic
    one with the stiffness its damage leaves (every element's and every pair's, straight to its present state), and each
    element and pair then takes the damage of the strains found; the damage never falls. Where the damage stops, the state
    is one the model can rest in under that load; where it never stops, the model cannot carry the load."""

    def __init__(self, model: BondModel, *, tolerance: float = 1e-3, parted: float = 50.0) -> None:
        if model.plies is None:
            raise BondError("Holding a load is for a model whose solids damage")
        self.model, self.plies, self.tolerance, self.parted = model, model.plies, tolerance, parted
        self.free = np.setdiff1d(np.arange(model.size), model.fixed)
        self.solves = 0
        # What the turns share. An element's stiffness matrix is its nine stiffnesses, each times a matrix of the element's
        # shape alone (kept, six of them: the stiffness is symmetric); and every entry's place in the model's matrix is
        # found once, the solids' and the bond's.
        pieces = np.zeros((len(model.elements), 6, 16, 16))
        for b, weight in _strain_matrices(model.nodes, model.elements):
            for index, (k, m) in enumerate(SIX):
                piece = np.einsum("ei,ej,e->eij", b[:, k], b[:, m], weight)
                pieces[:, index] += piece if k == m else piece + piece.transpose(0, 2, 1)
        self._pieces = pieces
        position = np.full(model.size, -1)
        position[self.free] = np.arange(len(self.free))
        dofs = _element_dofs(model.elements)
        rows, cols = position[np.repeat(dofs, 16, axis=1).ravel()], position[np.tile(dofs, (1, 16)).ravel()]
        ux, uy, ox, oy = 2 * model.under, 2 * model.under + 1, 2 * model.over, 2 * model.over + 1
        bond_rows, bond_cols = position[np.concatenate([ux, ox, ux, ox, uy, oy, uy, oy])], position[np.concatenate([ux, ox, ox, ux, uy, oy, oy, uy])]
        self._solid_in, self._bond_in = (rows >= 0) & (cols >= 0), (bond_rows >= 0) & (bond_cols >= 0)
        size = len(self.free)
        keys = np.concatenate([cols[self._solid_in] * size + rows[self._solid_in], bond_cols[self._bond_in] * size + bond_rows[self._bond_in]])
        places, self._slot = np.unique(keys, return_inverse=True)
        self._indices = (places % size).astype(np.int32)
        self._indptr = np.searchsorted(places // size, np.arange(size + 1)).astype(np.int32)
        self._size, self._entries = size, len(places)
        self._open = np.zeros(len(model.weight), dtype=bool)
        whole = self.begin()
        self._pulled = (np.ones(len(model.elements), dtype=bool), np.ones(len(model.elements), dtype=bool))
        for _ in range(8):  # which cracks would be pulled open and which pairs pressed is found from the whole model's answer
            unit = self._answer(whole)
            now_open, now_pulled = self._ways(unit, 1.0, whole)
            same = np.array_equal(now_open, self._open) and all(np.array_equal(a, b) for a, b in zip(now_pulled, self._pulled))
            self._open, self._pulled = now_open, now_pulled
            if same:
                break
        self.elastic_movement = float(model.unit_load @ unit)
        near = self._near(unit, 1.0, whole)
        if not near > 0:
            raise BondError("The load stresses neither the bond nor a ply")
        self.onset_load = 1.0 / near
        self.unit = unit

    def begin(self) -> Damage:
        return Damage(self.model.damage.copy(), self.plies.begin())

    def _ways(self, displacement: np.ndarray, factor: float, damage: Damage):
        opening = self.model.jumps(displacement)[0] if len(self.model.weight) else np.zeros(0)
        return opening > 0, self.plies.pulled(self.plies.own_strain(displacement, factor), damage.plies, self._pulled)

    def _answer(self, damage: Damage) -> np.ndarray:
        """The displacements under the unit load of the model with this damage, each crack and pair the way it was last
        found (open or pressed)."""
        model, plies = self.model, self.plies
        full = plies.stiffness(damage.plies, self._pulled)
        plane = [0, 2, 4]
        six = np.stack([full[:, plane[k], plane[m]] for k, m in SIX], axis=1)
        values = [np.einsum("ep,epij->eij", six, self._pieces).ravel()[self._solid_in]]
        load = model.unit_load - stress_load(model.nodes, model.elements, full[:, plane, 1] * plies.width_strain)
        if len(model.weight):
            law = model.law
            shear = model.weight * (1 - damage.bond) * law.shear_stiffness
            peel = model.weight * np.where(self._open, 1 - damage.bond, 1.0) * law.peel_stiffness
            values.append(np.concatenate([shear, shear, -shear, -shear, peel, peel, -peel, -peel])[self._bond_in])
        data = np.bincount(self._slot, weights=np.concatenate(values), minlength=self._entries)
        matrix = sp.csc_matrix((data, self._indices, self._indptr), shape=(self._size, self._size))
        free = self.free
        answer = np.zeros(model.size)
        answer[free] = spla.splu(matrix, **FACTOR).solve(load[free])
        self.solves += 1
        return answer

    def _near(self, displacement: np.ndarray, factor: float, damage: Damage) -> float:
        """How near the nearest pair or element is to damaging further (above 1: it must)."""
        model = self.model
        fibre, matrix = self.plies.nearness(self.plies.own_strain(displacement, factor), damage.plies)
        largest = max(float(fibre.max()), float(matrix.max()))
        if len(model.weight):
            law = model.law
            opening, slip = model.jumps(displacement)
            after = softening(law.peel_stiffness, law.shear_stiffness, law.peel_strength, law.shear_strength, law.peel_energy,
                              law.shear_energy, opening, slip, damage.bond)
            grows = after > damage.bond
            if grows.any():  # a pair's nearness: 1 and as much more as its damage would grow
                largest = max(largest, 1.0 + float((after - damage.bond)[grows].max()))
            elif not (damage.bond > 0).any():
                largest = max(largest, float(law.index(opening, slip).max()))
        return largest

    def hold(self, load: float, damage: Damage, solves: int = 200) -> Held:
        """Hold the model under `load` from the given damage until the damage stops growing."""
        model, plies = self.model, self.plies
        unit = model.unit_load
        for turn in range(solves):
            answer = load * self._answer(damage)
            movement = float(unit @ answer)
            if abs(movement) > self.parted * abs(load * self.elastic_movement):
                return Held(load, False, damage, answer, movement, turn + 1, "parted")
            now_open, now_pulled = self._ways(answer, load, damage)
            same = np.array_equal(now_open, self._open) and all(np.array_equal(a, b) for a, b in zip(now_pulled, self._pulled))
            self._open, self._pulled = now_open, now_pulled
            near = self._near(answer, load, damage)
            if same and near <= 1 + self.tolerance:
                return Held(load, True, damage, answer, movement, turn + 1, "stopped")
            bond = damage.bond
            if len(model.weight):
                law = model.law
                opening, slip = model.jumps(answer)
                bond = softening(law.peel_stiffness, law.shear_stiffness, law.peel_strength, law.shear_strength, law.peel_energy,
                                 law.shear_energy, opening, slip, bond)
            damage = Damage(bond, plies.damage(plies.own_strain(answer, load), damage.plies))
        return Held(load, False, damage, answer, movement, solves, "solves")


def largest_load(model: BondModel, *, rise: float = 1.15, within: float = 0.005, solves: int = 200, tolerance: float = 1e-3,
                 most: int = 60) -> tuple[list[Held], Held, Holder]:
    """The largest load the model holds. The load is raised from first softening by `rise` at a time for as long as the model
    holds it, and the largest is then closed in on until the load held and the load not held are `within` of each other.
    Returns every load held, in order, the smallest load found that the model does not hold, and the holder."""
    holder = Holder(model, tolerance=tolerance)
    damage = holder.begin()
    first = holder.hold(holder.onset_load / (1 + tolerance), damage, solves)
    if not first.held:
        raise BondError("The model does not hold the load at which it first softens")
    held, failed = [first], None
    for _ in range(most):
        last = held[-1]
        if failed is not None and failed.load <= last.load * (1 + within):
            break
        aim = last.load * rise if failed is None else 0.5 * (last.load + failed.load)
        now = holder.hold(aim, last.damage, solves)
        if now.held:
            held.append(now)
        else:
            failed = now
    if failed is None:
        raise BondError("The model held every load tried")
    return held, failed, holder
