"""A stepped lap bond worked by hand: how a bonded repair patch takes up the load of the laminate it covers (ADR-0130).

Two adherends are bonded along a lap made of steps. The outer adherend (the patch) starts at its tip carrying nothing, and the
inner adherend (the parent laminate) ends at the last step, at the cut or the hole, where the outer adherend carries everything.
Within a step each adherend has one thickness and one modulus. The adherends only stretch and the adhesive only shears (a
shear-lag model, Volkersen 1938, as Hart-Smith extended it to stepped laps in NASA CR-112237, 1973): the adhesive's shear
strain is the difference of the adherends' displacements over the bondline's thickness, uniform through it.

With N the outer adherend's force per unit width and T the applied one, within a step

    d2N/dx2 = lambda^2 (N - P),   lambda^2 = (G / eta) (1 / So + 1 / Si),   P = T So / (So + Si),   tau = dN/dx

where So and Si are the adherends' stiffnesses E t, G and eta the adhesive's shear modulus and thickness, and P the force the
outer adherend would carry if both strained alike. The solution in a step is fixed by N at its two ends, and the shear stress
is continuous from one step to the next because both displacements are, which gives one linear equation per boundary between
steps: a tridiagonal system for the boundary forces.

The model is elastic. Its strength is the load at which the largest shear stress reaches the adhesive's shear strength, which
for a ductile adhesive is the start of yielding, well below failure; `long_overlap_strength` is the closed-form strength of
a bond between two uniform adherends with an elastic-plastic adhesive (Hart-Smith, NASA CR-112235, 1973).

Not covered: peel stresses and bending from the eccentric load path, the stress concentration through the adhesive's
thickness, residual stresses from cure, a yielding adhesive in a stepped lap, adherends that fail between the plies, and
any change across the width. SI throughout: m, Pa, N/m.
"""

import math
from dataclasses import dataclass

import numpy as np


def _positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive, finite number, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class Adhesive:
    """The bondline: shear modulus (Pa) and thickness (m); the shear strength (Pa) and the plastic shear strain it can take
    beyond its elastic limit, when a strength is asked for; and, for a solve of the repair's slice (ADR-0132), which a lap
    does not use, Poisson's ratio and the peel stress the bond can take (Pa), when the peel stress is to be judged. To
    follow the bond until it lets go (ADR-0137), its two fracture energies as well, in peel and in shear (J/m^2): the
    energy it takes to part a unit area of the bond."""

    shear_modulus_pa: float
    thickness_m: float
    shear_strength_pa: float | None = None
    plastic_strain: float = 0.0
    poisson_ratio: float | None = None
    peel_strength_pa: float | None = None
    peel_energy_j_m2: float | None = None
    shear_energy_j_m2: float | None = None

    def __post_init__(self):
        _positive(self.shear_modulus_pa, "The adhesive's shear modulus")
        _positive(self.thickness_m, "The adhesive's thickness")
        if self.shear_strength_pa is not None:
            _positive(self.shear_strength_pa, "The adhesive's shear strength")
        if isinstance(self.plastic_strain, bool) or not math.isfinite(self.plastic_strain) or self.plastic_strain < 0:
            raise ValueError(f"The adhesive's plastic shear strain must be finite and not negative, got {self.plastic_strain!r}")
        if self.peel_strength_pa is not None:
            _positive(self.peel_strength_pa, "The bond's peel strength")
        if self.peel_energy_j_m2 is not None:
            _positive(self.peel_energy_j_m2, "The bond's peel energy")
        if self.shear_energy_j_m2 is not None:
            _positive(self.shear_energy_j_m2, "The bond's shear energy")
        if self.poisson_ratio is not None:
            nu = self.poisson_ratio
            if isinstance(nu, bool) or not isinstance(nu, (int, float)) or not math.isfinite(nu) or not -1 < nu < 0.5:
                raise ValueError(f"The adhesive's Poisson's ratio must be above -1 and below 0.5, got {nu!r}")

    @property
    def strength(self) -> float:
        if self.shear_strength_pa is None:
            raise ValueError("The adhesive has no shear strength, so no strength can be worked out")
        return self.shear_strength_pa

    @property
    def elastic_strain(self) -> float:
        """The shear strain at which the adhesive reaches its strength."""
        return self.strength / self.shear_modulus_pa

    @property
    def strain_energy(self) -> float:
        """The area under the elastic-perfectly plastic shear stress-strain curve up to failure, in Pa."""
        return self.strength * (self.elastic_strain / 2 + self.plastic_strain)


@dataclass(frozen=True)
class Step:
    """One step of the lap, with each adherend's thickness (m) and modulus along the load (Pa) in it."""

    length_m: float
    outer_thickness_m: float
    outer_modulus_pa: float
    inner_thickness_m: float
    inner_modulus_pa: float

    def __post_init__(self):
        for value, name in ((self.length_m, "length"), (self.outer_thickness_m, "outer thickness"), (self.outer_modulus_pa, "outer modulus"),
                            (self.inner_thickness_m, "inner thickness"), (self.inner_modulus_pa, "inner modulus")):
            _positive(value, f"A step's {name}")

    @property
    def outer_stiffness(self) -> float:
        return self.outer_modulus_pa * self.outer_thickness_m

    @property
    def inner_stiffness(self) -> float:
        return self.inner_modulus_pa * self.inner_thickness_m


def step_constants(step: Step, adhesive: Adhesive, load_n_per_m: float) -> tuple[float, float]:
    """lambda (1/m) of a step, and P (N/m): the force the outer adherend carries where the two adherends strain alike."""
    so, si = step.outer_stiffness, step.inner_stiffness
    lam = math.sqrt(adhesive.shear_modulus_pa / adhesive.thickness_m * (1 / so + 1 / si))
    return lam, load_n_per_m * so / (so + si)


def boundary_forces(steps: list[Step], adhesive: Adhesive, load_n_per_m: float, inner_continues: bool = False) -> np.ndarray:
    """The outer adherend's force per unit width (N/m) at every step boundary, from its tip (zero) to the lap's end: the shear
    stress at the end of each step equals the one at the start of the next.

    The lap ends where the inner adherend does, and the outer adherend carries the whole load there. With `inner_continues`
    it ends instead at a plane of symmetry that both adherends cross, the middle of a patch over a laminate that is not cut
    through: the shear stress is zero there, and the force the outer adherend has reached is part of the answer."""
    m = len(steps)
    forces = np.zeros(m + 1)
    forces[m] = load_n_per_m
    if m == 1 and not inner_continues:
        return forces
    lam, shared = np.array([step_constants(step, adhesive, load_n_per_m) for step in steps]).T
    t = np.tanh(lam * np.array([step.length_m for step in steps]) / 2)
    a, b = lam * t / 2, lam / (2 * t)  # tau at a step's end = (a - b) N_start + (a + b) N_end - 2 a P; at its start, mirrored
    size = m if inner_continues else m - 1  # the unknowns are forces[1:size + 1]
    matrix, right = np.zeros((size, size)), np.zeros(size)
    for row in range(m - 1):  # the boundary between step `row` and step `row + 1`; its unknown is forces[row + 1]
        k, n = row, row + 1
        matrix[row, row] = a[k] + b[k] + a[n] + b[n]
        if row > 0:
            matrix[row, row - 1] = a[k] - b[k]
        if row < size - 1:
            matrix[row, row + 1] = a[n] - b[n]
        right[row] = 2 * a[k] * shared[k] + 2 * a[n] * shared[n]
    if inner_continues:  # no shear stress at the end of the last step
        if m > 1:
            matrix[-1, -2] = a[-1] - b[-1]
        matrix[-1, -1] = a[-1] + b[-1]
        right[-1] = 2 * a[-1] * shared[-1]
    else:
        right[-1] -= (a[-1] - b[-1]) * load_n_per_m
    forces[1:size + 1] = np.linalg.solve(matrix, right)
    return forces


def _ratios(lam: float, half: float, x: float) -> tuple[float, float, float, float]:
    """cosh(lam x)/cosh(lam c), sinh(lam x)/sinh(lam c), sinh(lam x)/cosh(lam c) and cosh(lam x)/sinh(lam c) for |x| <= c,
    written with decaying exponentials so that a long step does not overflow."""
    u, c = lam * abs(x), lam * half
    grow = math.exp(u - c)
    ex, ec = math.exp(-2 * u), math.exp(-2 * c)
    sign = 1.0 if x >= 0 else -1.0
    return grow * (1 + ex) / (1 + ec), sign * grow * (1 - ex) / (1 - ec), sign * grow * (1 - ex) / (1 + ec), grow * (1 + ex) / (1 - ec)


@dataclass(frozen=True)
class StepLap:
    """A stepped lap under a load, solved: the outer adherend's force at every step boundary, and from it the force and
    the adhesive's shear stress anywhere along the lap."""

    steps: tuple[Step, ...]
    adhesive: Adhesive
    load_n_per_m: float
    forces: np.ndarray  # the outer adherend's force at the step boundaries, N/m
    inner_continues: bool = False  # the lap ends at a plane of symmetry both adherends cross, not at the inner adherend's end

    @property
    def starts(self) -> np.ndarray:
        """Where each step starts, in m from the outer adherend's tip, with the lap's length last."""
        return np.concatenate([[0.0], np.cumsum([step.length_m for step in self.steps])])

    def _parts(self, k: int) -> tuple[float, float, float, float]:
        """lambda, the half length, and the two amplitudes of step k: (mean boundary force - P) and half the force's rise."""
        lam, shared = step_constants(self.steps[k], self.adhesive, self.load_n_per_m)
        return lam, self.steps[k].length_m / 2, (self.forces[k] + self.forces[k + 1]) / 2 - shared, (self.forces[k + 1] - self.forces[k]) / 2

    def outer_force(self, k: int, x: float) -> float:
        """The outer adherend's force per unit width (N/m) in step k, at x from the step's middle (-length/2 to length/2)."""
        lam, half, even, odd = self._parts(k)
        cc, ss, _, _ = _ratios(lam, half, x)
        return (self.forces[k] + self.forces[k + 1]) / 2 + even * (cc - 1) + odd * ss  # P + even cc + odd ss, exact at the ends

    def shear(self, k: int, x: float) -> float:
        """The adhesive's shear stress (Pa) in step k, at x from the step's middle: the slope of the outer adherend's force."""
        lam, half, even, odd = self._parts(k)
        _, _, sc, cs = _ratios(lam, half, x)
        return lam * (even * sc + odd * cs)

    @property
    def shear_at_ends(self) -> np.ndarray:
        """The shear stress (Pa) at the start and at the end of every step, one row per step."""
        return np.array([[self.shear(k, -step.length_m / 2), self.shear(k, step.length_m / 2)] for k, step in enumerate(self.steps)])

    @property
    def peak_shear(self) -> tuple[float, int, str]:
        """The largest shear stress in size (Pa, signed), the step it is in (from 0) and the end of that step ("start" or
        "end"). Within a step the shear stress is a sum of cosh and sinh, so its size is largest at an end. The shear stress is
        continuous along the lap, so the end of one step and the start of the next are one place with one value, alike to the
        last bits: the place is named by the first of the ends that reach the largest value within one part in 10^9, so that
        two repairs alike but for a small change name it the same way."""
        ends = self.shear_at_ends
        sizes = np.abs(ends)
        k, e = np.argwhere(sizes >= sizes.max() * (1 - 1e-9))[0]
        return float(ends[k, e]), int(k), ("start", "end")[e]

    def adherend_stresses(self) -> np.ndarray:
        """The largest stress in size (Pa, signed) in the outer and in the inner adherend of every step, one row per step:
        the force is largest at an end of the step, or where the shear stress passes through zero inside it."""
        rows = []
        for k, step in enumerate(self.steps):
            lam, half, even, odd = self._parts(k)
            places = [-half, half]
            reach = math.tanh(lam * half)
            if abs(odd) < abs(even) * reach**2:  # tau = 0 inside the step, where tanh(lam x) = -odd / (even tanh(lam c))
                places.append(math.atanh(-odd / (even * reach)) / lam)
            outer = [self.outer_force(k, x) for x in places]
            inner = [self.load_n_per_m - force for force in outer]
            rows.append([max(outer, key=abs) / step.outer_thickness_m, max(inner, key=abs) / step.inner_thickness_m])
        return np.array(rows)

    def distribution(self, points_per_step: int = 41) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """x from the outer adherend's tip (m), the shear stress (Pa) and the outer adherend's force (N/m) along the lap,
        `points_per_step` points in every step with both ends of each."""
        if points_per_step < 2:
            raise ValueError("A step is drawn with at least its two ends")
        xs, taus, forces = [], [], []
        for k, step in enumerate(self.steps):
            for x in np.linspace(-step.length_m / 2, step.length_m / 2, points_per_step):
                xs.append(self.starts[k] + step.length_m / 2 + x)
                taus.append(self.shear(k, x))
                forces.append(self.outer_force(k, x))
        return np.array(xs), np.array(taus), np.array(forces)


def step_lap(steps: list[Step], adhesive: Adhesive, load_n_per_m: float, inner_continues: bool = False) -> StepLap:
    """Solve a stepped lap under a load per unit width (N/m, tension positive). The steps are listed from the outer
    adherend's tip to the end of the inner adherend, or, with `inner_continues`, to the plane of symmetry in the middle of
    a patch whose laminate is not cut through (`boundary_forces`)."""
    if not steps:
        raise ValueError("A lap needs at least one step")
    if isinstance(load_n_per_m, bool) or not math.isfinite(load_n_per_m):
        raise ValueError(f"The load must be a finite number, got {load_n_per_m!r}")
    forces = boundary_forces(list(steps), adhesive, float(load_n_per_m), bool(inner_continues))
    return StepLap(tuple(steps), adhesive, float(load_n_per_m), forces, bool(inner_continues))


def elastic_limit_load(lap: StepLap) -> float:
    """The load per unit width (N/m, in size) at which the largest shear stress reaches the adhesive's shear strength. The
    model is linear, so it is the applied load times the strength over the largest shear stress under it."""
    peak = abs(lap.peak_shear[0])
    if peak == 0:
        raise ValueError("No load is applied, so there is no shear stress to scale")
    return abs(lap.load_n_per_m) * lap.adhesive.strength / peak


def long_overlap_strength(stiffness_a: float, stiffness_b: float, adhesive: Adhesive) -> float:
    """The most one bondline between two uniform adherends carries per unit width (N/m), however long the overlap, with an
    elastic-perfectly plastic adhesive (Hart-Smith, NASA CR-112235): at each end of the overlap the adhesive's shear
    strain energy to failure, times its thickness, sets the load, and the weaker end governs. `stiffness_a` and
    `stiffness_b` are E t of the two adherends (N/m). With no plastic strain it is the load at the elastic limit."""
    sa, sb = _positive(stiffness_a, "An adherend's stiffness"), _positive(stiffness_b, "An adherend's stiffness")
    energy = 2 * adhesive.thickness_m * adhesive.strain_energy
    return math.sqrt(energy * min(sa * (1 + sa / sb), sb * (1 + sb / sa)))


def double_lap_strength(inner_stiffness: float, outer_stiffness: float, adhesive: Adhesive) -> float:
    """The most a long double lap carries per unit width of the inner adherend (N/m): two bondlines, each between half the
    inner adherend and one outer adherend. `outer_stiffness` is E t of one outer adherend."""
    return 2 * long_overlap_strength(_positive(inner_stiffness, "The inner adherend's stiffness") / 2, outer_stiffness, adhesive)
