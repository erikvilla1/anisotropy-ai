"""The numbers a model comparison document is made of (ADR-0031).

A comparison record (`compare.py`) holds the reference solver's numbers for one model. A document about that model
needs, beside the record itself: every compared value next to the kernel's with its error in several forms, the
statistics per result group, where each element sits so the errors can be drawn on the mesh, and a hand check from
classical laminate theory computed by the engine. All of that is assembled here, in the record's units, with no
typesetting; `docs/models/build.py` turns it into LaTeX. Nothing in this module invents a number: every value is the
reference solver's, the kernel's, or the engine's.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from anisotropy_engine.cases import Comparison
from anisotropy_engine.engineering import EngineeringConstants, engineering_constants
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.mixed import mixed_response
from anisotropy_engine.response import ply_surfaces

from .abaqus_reader import read_deck
from .cases import GROUPS, PLY_GROUPS, element_name
from .compare import compare_record, record_as_case
from .membrane import solve_membrane
from .mesh import KernelError, mesh_from_deck
from .model import Deck, all_boundaries, coupled_nodes, reference_node, resolve_nodes
from .recovery import element_ply_states
from .results import MembraneSolution
from .units import from_si

# Component names per result group, in the order the record lists them.
COMPONENTS: dict[str, tuple[str, ...]] = {
    "rf": ("RF_x", "RF_y"),
    "u": ("u", "v"),
    "strain": ("eps_x", "eps_y", "gamma_xy"),
    "section_force": ("N_x", "N_y", "N_xy"),
    "ply_stress_local": ("sigma_1", "sigma_2", "tau_12"),
    "ply_strain_local": ("eps_1", "eps_2", "gamma_12"),
    "ply_mises": ("sigma_M",),
    "fpf": ("ratio",),
}
# Unit kind (units.py) of each group; None for dimensionless groups.
GROUP_KIND: dict[str, str | None] = {**{g: GROUPS[g][0] for g in GROUPS}, **{g: PLY_GROUPS[g][0] for g in PLY_GROUPS}, "fpf": None}
KEY = re.compile(r"^(?P<group>\w+)\[(?P<name>[^\]]+)\](?:\[(?P<ply>[^\]]+)\])?\[(?P<component>\d+)\]$")


@dataclass(frozen=True)
class ComparisonRow:
    """One compared number with its error, in the record's units."""

    key: str
    group: str
    name: str  # node, node set, element or criterion
    ply: int | None  # bottom ply is 1; None outside the ply groups
    component: int
    reference: float
    kernel: float
    allowed: float  # the largest accepted absolute difference, tolerance and floor applied

    @property
    def difference(self) -> float:
        """Kernel minus reference."""
        return self.kernel - self.reference

    @property
    def agrees(self) -> bool:
        return abs(self.difference) <= self.allowed

    @property
    def relative(self) -> float:
        """|difference| / |reference|; nan when the reference is zero."""
        return abs(self.difference) / abs(self.reference) if self.reference != 0 else math.nan

    @property
    def of_allowed(self) -> float:
        """|difference| / allowed: below 1 agrees."""
        return abs(self.difference) / self.allowed

    @property
    def component_name(self) -> str:
        return COMPONENTS[self.group][self.component]


@dataclass(frozen=True)
class GroupSummary:
    group: str
    count: int
    agreeing: int
    scale: float  # the largest |reference| in the group, in the record's units
    worst: ComparisonRow  # the row with the largest |difference| / allowed
    mean_relative_to_scale: float  # the mean of |difference| / scale: small components are judged against the group, not themselves
    max_relative_to_scale: float  # the largest |difference| / scale


def parse_key(key: str) -> tuple[str, str, int | None, int]:
    """`group[name][component]` or `group[name][ply][component]` into its parts."""
    match = KEY.match(key)
    if match is None:
        raise ValueError(f"{key!r} is not a comparison label")
    ply = match["ply"]
    return match["group"], match["name"], (int(ply) if ply is not None and ply.isdigit() else None), int(match["component"])


def comparison_rows(record: dict) -> tuple[list[ComparisonRow], list[str]]:
    """Every compared number of a record as a row, plus the comparison's problems (names the kernel cannot produce)."""
    comparisons, problems = compare_record(record)
    return [rows_from(c) for c in comparisons], problems


def rows_from(comparison: Comparison) -> ComparisonRow:
    group, name, ply, component = parse_key(comparison.key)
    return ComparisonRow(comparison.key, group, name, ply, component, comparison.expected, comparison.engine, comparison.allowed)


def summarize(rows: list[ComparisonRow]) -> list[GroupSummary]:
    """One summary per result group, in the order the groups first appear."""
    out = []
    for group in dict.fromkeys(row.group for row in rows):
        members = [row for row in rows if row.group == group]
        scale = max(abs(row.reference) for row in members)
        differences = np.array([abs(row.difference) for row in members])
        out.append(GroupSummary(
            group=group, count=len(members), agreeing=sum(row.agrees for row in members), scale=scale,
            worst=max(members, key=lambda row: row.of_allowed),
            mean_relative_to_scale=float(differences.mean() / scale) if scale else math.nan,
            max_relative_to_scale=float(differences.max() / scale) if scale else math.nan))
    return out


def not_reported(record: dict) -> int:
    """How many components the reference solver did not report (`nan` in the record), which the comparison skips."""
    count = 0
    for group, rows in record["expected"].items():
        if group in ("tolerance", "floor"):
            continue
        if group in PLY_GROUPS:
            count += sum(1 for plies in rows.values() for vector in plies.values() for v in vector if isinstance(v, float) and math.isnan(v))
        elif group in GROUPS:
            count += sum(1 for vector in rows.values() for v in vector if isinstance(v, float) and math.isnan(v))
    return count


def solve_record(record: dict) -> tuple[Deck, MembraneSolution]:
    """The kernel's solution of the record's kernel deck."""
    case = record_as_case(record)
    deck = read_deck(f"{case['_dir']}/{case['mesh']['deck']}", record["units"])
    return deck, solve_membrane(deck)


def element_centroids(solution: MembraneSolution, units: str) -> dict[str, tuple[float, float]]:
    """Element name -> centroid in the record's length unit."""
    mesh = solution.mesh
    centres = mesh.xy[mesh.connectivity[:, :4]].mean(axis=1)
    return {element_name(key): (from_si(float(c[0]), "length", units), from_si(float(c[1]), "length", units))
            for key, c in zip(mesh.element_keys, centres)}


# --- the hand check from classical laminate theory ---------------------------------------------------


@dataclass(frozen=True)
class LaminateCheck:
    """Classical laminate theory for the coupon as a uniaxial test with free lateral edges, computed by the engine.

    The coupon's gripped node groups are read from the deck: the nodes whose dof 2 is prescribed directly or through a
    coupling (and the coupling's reference node, which carries the group's reaction), split into the bottom and top
    group by position. The free length is the gap between the groups' coupon nodes, the
    applied value is the difference of the prescribed dof-2 values (displacement control) or the summed dof-2 load
    (force control). The laminate is the mesh's one section. Values in SI.
    """

    plies: list[Ply]
    A: np.ndarray  # (3, 3) N/m
    thickness_m: float
    constants: EngineeringConstants
    width_m: float
    free_length_m: float
    control: str  # "displacement" or "force"
    applied: float  # m or N
    strain: np.ndarray  # [eps_x, eps_y, gamma_xy] with N_x = N_xy = 0
    section_force: np.ndarray  # [N_x, N_y, N_xy] N/m
    ply_stress_12: np.ndarray  # (plies, 3) Pa, material axes, bottom ply first
    ply_strain_12: np.ndarray  # (plies, 3)
    centre_element: str  # the element whose centroid is nearest the coupon's centre
    kernel_strain: np.ndarray
    kernel_section_force: np.ndarray
    kernel_ply_stress_12: np.ndarray
    kernel_reaction_N: float  # the reaction of the top group along y

    @property
    def reaction_N(self) -> float:
        return float(self.section_force[1] * self.width_m)


def gripped_groups(deck: Deck, solution: MembraneSolution) -> tuple[dict[int, float], dict[int, float]]:
    """Mesh node index -> prescribed dof-2 value, for the bottom and the top gripped group."""
    held: dict[int, float] = {}
    mesh = solution.mesh
    for boundary in all_boundaries(deck):
        if not boundary.dof_first <= 2 <= boundary.dof_last:
            continue
        for key in resolve_nodes(deck, boundary.target, boundary.line):
            held[mesh.node(key)] = boundary.value
    for coupling in deck.couplings:
        reference = mesh.node(reference_node(deck, coupling))
        if reference in held:
            for key in coupled_nodes(deck, coupling):
                held[mesh.node(key)] = held[reference]
    if not any(mesh.node_keys[i][0] is not None for i in held):
        raise KernelError("no instance node has its dof 2 prescribed, so there are no gripped groups")
    y = mesh.xy[:, 1]
    instance_rows = [k for k in range(mesh.node_count) if mesh.node_keys[k][0] is not None]
    middle = 0.5 * (y[instance_rows].min() + y[instance_rows].max())
    # a coupling's reference node joins its group by its own position: the reaction of a coupled grip is carried there
    bottom = {i: v for i, v in held.items() if y[i] < middle}
    top = {i: v for i, v in held.items() if y[i] >= middle}
    if not any(mesh.node_keys[i][0] is not None for i in bottom) or not any(mesh.node_keys[i][0] is not None for i in top):
        raise KernelError("the gripped nodes are all on one side of the coupon")
    return bottom, top


def laminate_check(deck: Deck, solution: MembraneSolution) -> LaminateCheck:
    """The engine's classical laminate theory prediction for the coupon beside the kernel's centre-element values.

    Raises KernelError, with the reason, for a deck this check does not describe: several sections, no gripped groups,
    or neither a prescribed pull nor an applied load along y.
    """
    mesh = solution.mesh
    if len(mesh.sections) != 1:
        raise KernelError(f"the hand check needs one section; the deck has {len(mesh.sections)}")
    plies = mesh.sections[0].plies
    A, _, _ = abd_matrices(plies)
    thickness = sum(ply.thickness_m for ply in plies)
    bottom, top = gripped_groups(deck, solution)
    y = mesh.xy[:, 1]
    instance_rows = [k for k in range(mesh.node_count) if mesh.node_keys[k][0] is not None]
    on_coupon = lambda group: [i for i in group if mesh.node_keys[i][0] is not None]  # noqa: E731  reference nodes may sit anywhere
    free_length = float(y[on_coupon(top)].min() - y[on_coupon(bottom)].max())
    width = float(np.ptp(mesh.xy[instance_rows, 0]))
    pull = float(np.mean(list(top.values())) - np.mean(list(bottom.values())))
    if free_length <= 0 or width <= 0:
        raise KernelError("the gripped groups leave no free length between them")
    if pull != 0.0:
        control, applied = "displacement", pull
        known = {"Nx": 0.0, "eps_y": pull / free_length, "Nxy": 0.0, "Mx": 0.0, "My": 0.0, "Mxy": 0.0}
    else:
        total = sum(load.value for step in deck.steps for load in step.cloads if load.dof == 2)
        if total == 0.0:
            raise KernelError("neither a prescribed pull nor a load along y: nothing for the hand check to predict")
        control, applied = "force", float(total)
        known = {"Nx": 0.0, "Ny": total / width, "Nxy": 0.0, "Mx": 0.0, "My": 0.0, "Mxy": 0.0}
    result = mixed_response(plies, known, None)
    strain = result.midplane_strain
    section_force = np.array([result.loads.Nx, result.loads.Ny, result.loads.Nxy])
    surfaces = ply_surfaces(plies, strain, np.zeros(3))
    ply_stress = np.array([surfaces[2 * k].stress_12 for k in range(len(plies))])
    ply_strain = np.array([surfaces[2 * k].strain_12 for k in range(len(plies))])

    centres = mesh.xy[mesh.connectivity[:, :4]].mean(axis=1)
    middle = 0.5 * (mesh.xy[instance_rows].min(axis=0) + mesh.xy[instance_rows].max(axis=0))
    e = int(np.argmin(np.linalg.norm(centres - middle, axis=1)))
    field = element_ply_states(solution)
    reaction = float(solution.reaction[list(top)].sum(axis=0)[1])
    return LaminateCheck(plies=plies, A=A, thickness_m=thickness, constants=engineering_constants(plies), width_m=width,
                         free_length_m=free_length, control=control, applied=applied, strain=strain, section_force=section_force,
                         ply_stress_12=ply_stress, ply_strain_12=ply_strain, centre_element=element_name(mesh.element_keys[e]),
                         kernel_strain=solution.strain[e], kernel_section_force=solution.section_force[e],
                         kernel_ply_stress_12=field.stress_12[e], kernel_reaction_N=reaction)
