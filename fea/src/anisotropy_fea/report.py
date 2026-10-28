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
from .model import Deck, all_boundaries, coupled_nodes, expanded_layers, node_name, reference_node, resolve_nodes
from .recovery import FailureField, element_ply_states
from .results import MembraneSolution
from .units import UNIT_LABEL, from_si

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
class GaugeElement:
    """The element a coupon's gauge state is read at, by one rule for every reader (the hand check, the results chapter and the
    audit's rows C4, D1 and D5): the spec's centre probe; when the coupon's centre lies in no element (an open hole), its far-field
    probe; failing both, the element whose centroid is nearest the centre."""

    index: int  # mesh element index
    name: str  # instance.label
    xy: tuple[float, float]  # centroid, m
    basis: str  # why this element: "the centre probe", "the far-field probe" or "nearest the centre"
    centre_in_hole: bool  # the coupon's centre lies in no element


def _probe_element(deck: Deck, solution: MembraneSolution, name: str) -> int | None:
    """The mesh index of a probe element set holding one element, or None."""
    keys = deck.elsets.get(name)
    if keys is None or len(keys) != 1:
        return None
    return solution.mesh.element_keys.index(tuple(keys[0]))


def gauge_element(deck: Deck, solution: MembraneSolution) -> GaugeElement:
    mesh = solution.mesh
    instance_rows = [k for k in range(mesh.node_count) if mesh.node_keys[k][0] is not None]
    middle = 0.5 * (mesh.xy[instance_rows].min(axis=0) + mesh.xy[instance_rows].max(axis=0))
    corners = mesh.xy[mesh.connectivity[:, :4]]
    centres = corners.mean(axis=1)
    edges = np.roll(corners, -1, axis=1) - corners
    cross = edges[..., 0] * (middle[1] - corners[..., 1]) - edges[..., 1] * (middle[0] - corners[..., 0])
    tolerance = 1e-9 * float(np.max(np.abs(edges))) ** 2
    inside = np.all(cross >= -tolerance, axis=1) | np.all(cross <= tolerance, axis=1)  # convex corners in either winding
    in_hole = not bool(inside.any())
    for probe, basis in (("Probe-centre", "the centre probe"), *((("Probe-far", "the far-field probe"),) if in_hole else ())):
        e = _probe_element(deck, solution, probe)
        if e is not None:
            return GaugeElement(e, element_name(mesh.element_keys[e]), (float(centres[e, 0]), float(centres[e, 1])), basis, in_hole)
    e = int(np.argmin(np.linalg.norm(centres - middle, axis=1)))
    return GaugeElement(e, element_name(mesh.element_keys[e]), (float(centres[e, 0]), float(centres[e, 1])), "nearest the centre", in_hole)


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
    gauge: GaugeElement  # where the kernel's values beside the theory are read
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


def fpf_place(deck: Deck, solution: MembraneSolution, field: FailureField, units: str) -> tuple[str, bool, list[int]]:
    """Where the first ply to fail sits, in words: at the edge of a gripped tab, beside the hole, or its distance from the nearer tab line;
    whether it touches a gripped tab; and the plies of that element that tie with the one named (the bottom-most is named). The coupon
    document's cover and the studio's summary say it with these words."""
    mesh = solution.mesh
    e = mesh.element_keys.index(field.element)
    ratios = np.asarray(field.ratio[e])
    tied = [k + 1 for k, r in enumerate(ratios) if r <= ratios.min() * (1 + 1e-9)]
    try:
        bottom, top = gripped_groups(deck, solution)
    except KernelError:
        return "in the coupon", False, tied
    gripped = {i for i in (*bottom, *top) if mesh.node_keys[i][0] is not None}
    if gripped & set(mesh.connectivity[e, :4].tolist()):
        return "at the edge of a gripped tab", True, tied
    unit = UNIT_LABEL[units]["length"]
    y = float(mesh.xy[mesh.connectivity[e, :4]].mean(axis=0)[1])
    lo = max(float(mesh.xy[i, 1]) for i in bottom if mesh.node_keys[i][0] is not None)
    hi = min(float(mesh.xy[i, 1]) for i in top if mesh.node_keys[i][0] is not None)
    gauge = gauge_element(deck, solution)
    if gauge.centre_in_hole and abs(y - 0.5 * (lo + hi)) < 0.1 * (hi - lo):
        return "beside the hole", False, tied
    return f"{from_si(min(y - lo, hi - y), 'length', units):.2g} {unit} from the nearer tab line", False, tied


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

    gauge = gauge_element(deck, solution)
    e = gauge.index
    field = element_ply_states(solution)
    reaction = float(solution.reaction[list(top)].sum(axis=0)[1])
    return LaminateCheck(plies=plies, A=A, thickness_m=thickness, constants=engineering_constants(plies), width_m=width,
                         free_length_m=free_length, control=control, applied=applied, strain=strain, section_force=section_force,
                         ply_stress_12=ply_stress, ply_strain_12=ply_strain, gauge=gauge,
                         kernel_strain=solution.strain[e], kernel_section_force=solution.section_force[e],
                         kernel_ply_stress_12=field.stress_12[e], kernel_reaction_N=reaction)


# --- the facts a rebuild guide is made of ------------------------------------------------------------


@dataclass(frozen=True)
class SetFacts:
    name: str
    count: int
    x_range: tuple[float, float]  # m
    y_range: tuple[float, float]  # m
    scope: str  # "assembly" or the part name


@dataclass(frozen=True)
class CouplingFacts:
    name: str
    reference: str  # node name
    reference_xy: tuple[float, float]  # m
    slaves: int
    y_range: tuple[float, float]  # m
    dofs: tuple[int, ...]


@dataclass(frozen=True)
class BoundaryFacts:
    target: str  # set name or node name
    nodes: int
    dof_first: int
    dof_last: int
    value: float  # m, or 0 for fixed
    line: int


@dataclass(frozen=True)
class LoadFacts:
    target: str
    nodes: int
    dof: int
    value: float  # N per node as written


@dataclass(frozen=True)
class PlyFacts:
    index: int  # 1 is the bottom ply of the expanded stack
    name: str | None
    material: str
    thickness_m: float
    angle_deg: float
    integration_points: int
    z_bottom_m: float
    z_top_m: float


@dataclass(frozen=True)
class SectionFacts:
    elset: str
    elements: int
    layup_name: str | None
    orientation: str | None
    orientation_axes: tuple[tuple[float, float, float], tuple[float, float, float]] | None
    orientation_rotation: tuple[int, float] | None
    section_integration: str | None
    symmetric: bool
    listed: tuple[PlyFacts, ...]  # as the deck lists them (the lower half when symmetric)
    expanded: tuple[PlyFacts, ...]  # bottom-first, `symmetric` applied
    total_thickness_m: float
    angle_fractions: tuple[tuple[float, int], ...]  # (angle, ply count), by first appearance


@dataclass(frozen=True)
class ModelFacts:
    """Everything a deck states about a model, read from the deck and the mesh, in SI: the input to a rebuild guide."""

    parts: tuple[tuple[str, int, int, str], ...]  # name, nodes, elements, element type
    instances: tuple[tuple[str, str], ...]  # instance, part
    extent_x: tuple[float, float]  # m, coupon nodes
    extent_y: tuple[float, float]
    grid: tuple[int, int] | None  # elements across x and along y when the coupon mesh is a rectangular grid
    node_rows_y: tuple[float, ...]  # distinct y of the coupon nodes
    partition_lines_y: tuple[float, ...]  # the coupon ends and the inner edges of the gripped groups
    grip_lines_y: tuple[float, ...]  # the coupon ends and the inner edges of the gripped groups only, without the mesh's spacing changes
    row_counts: tuple[int, ...]  # element rows between consecutive partition lines
    element_bands: tuple[tuple[float, float, int, int, int], ...]  # y0, y1, elements, first label, last label
    edge_length_range: tuple[float, float]  # m
    node_sets: tuple[SetFacts, ...]
    element_sets: tuple[tuple[str, int, str], ...]  # name, count, scope
    surfaces: tuple[tuple[str, str, str], ...]  # name, kind, what it names
    reference_nodes: tuple[tuple[str, tuple[float, float]], ...]
    couplings: tuple[CouplingFacts, ...]
    boundaries: tuple[BoundaryFacts, ...]
    loads: tuple[LoadFacts, ...]
    step: tuple[str, bool]  # name, nlgeom
    sections: tuple[SectionFacts, ...]
    ignored_keywords: tuple[str, ...]


def _range(values: np.ndarray) -> tuple[float, float]:
    return (float(values.min()), float(values.max())) if values.size else (math.nan, math.nan)


def model_facts(deck: Deck, solution: MembraneSolution) -> ModelFacts:
    mesh = solution.mesh
    coupon = np.array([k for k in range(mesh.node_count) if mesh.node_keys[k][0] is not None])
    xy = mesh.xy
    extent_x, extent_y = _range(xy[coupon, 0]), _range(xy[coupon, 1])
    size = max(extent_x[1] - extent_x[0], extent_y[1] - extent_y[0]) or 1.0
    tick = 1e-9 * size
    rows_y = np.unique(np.round(xy[coupon, 1] / tick).astype(np.int64)) * tick
    cols_x = np.unique(np.round(xy[coupon, 0] / tick).astype(np.int64)) * tick
    is_grid = (cols_x.size - 1) * (rows_y.size - 1) == mesh.element_count and coupon.size == cols_x.size * rows_y.size
    grid = (int(cols_x.size - 1), int(rows_y.size - 1)) if is_grid else None

    try:
        bottom, top = gripped_groups(deck, solution)
        on_coupon = lambda group: [i for i in group if mesh.node_keys[i][0] is not None]  # noqa: E731
        inner = [float(xy[on_coupon(bottom), 1].max()), float(xy[on_coupon(top), 1].min())]
    except KernelError:
        inner = []
    # a partition line is also wherever the node-row spacing changes: a CAE face partition leaves that trace in the mesh
    spacing = np.diff(rows_y)
    changes = [float(rows_y[k + 1]) for k in range(spacing.size - 1) if abs(spacing[k + 1] - spacing[k]) > 1e-6 * size]
    lines = sorted({round(v, 12) for v in (extent_y[0], extent_y[1], *inner, *changes)})
    row_counts = tuple(int(np.sum((rows_y > a + tick) & (rows_y <= b + tick))) for a, b in zip(lines, lines[1:]))

    centroids = xy[mesh.connectivity[:, :4]].mean(axis=1)
    labels = np.array([key[1] for key in mesh.element_keys])
    bands = []
    for a, b in zip(lines, lines[1:]):
        inside = np.flatnonzero((centroids[:, 1] > a) & (centroids[:, 1] < b))
        if inside.size:
            bands.append((a, b, int(inside.size), int(labels[inside].min()), int(labels[inside].max())))
    corners = mesh.connectivity[:, :4]
    edges = np.linalg.norm(xy[corners] - xy[np.roll(corners, -1, axis=1)], axis=2)

    def set_facts(name: str, indices: np.ndarray, scope: str) -> SetFacts:
        return SetFacts(name, int(indices.size), _range(xy[indices, 0]), _range(xy[indices, 1]), scope)

    node_sets = [set_facts(name, np.array([mesh.node(k) for k in keys]), "assembly") for name, keys in deck.nsets.items()]
    for part in deck.parts.values():
        instances = [name for name, inst in deck.instances.items() if inst.part == part.name]
        for name, part_labels in part.nsets.items():
            keys = [(instance, int(label)) for instance in instances for label in part_labels]
            node_sets.append(set_facts(name, np.array([mesh.node(k) for k in keys]), part.name))
    element_sets = [(name, len(keys), "assembly") for name, keys in deck.elsets.items()]
    element_sets += [(name, int(len(v)), part.name) for part in deck.parts.values() for name, v in part.elsets.items()]
    surfaces = [(name, "node", s.nset) if hasattr(s, "nset") else (name, "element", f"{s.elset} ({s.side})") for name, s in deck.surfaces.items()]
    reference_nodes = [(node_name((None, int(label))), (float(p[0]), float(p[1])))
                       for label, p in zip(deck.assembly_nodes.labels, deck.assembly_nodes.xyz)]
    couplings = []
    for c in deck.couplings:
        reference = reference_node(deck, c)
        slaves = np.array([mesh.node(k) for k in coupled_nodes(deck, c)])
        couplings.append(CouplingFacts(c.name, node_name(reference), (float(xy[mesh.node(reference), 0]), float(xy[mesh.node(reference), 1])),
                                       int(slaves.size), _range(xy[slaves, 1]), tuple(sorted(c.dofs))))
    boundaries = [BoundaryFacts(b.target if isinstance(b.target, str) else node_name(b.target), len(resolve_nodes(deck, b.target, b.line)),
                                b.dof_first, b.dof_last, b.value, b.line) for b in all_boundaries(deck)]
    loads = [LoadFacts(c.target if isinstance(c.target, str) else node_name(c.target), len(resolve_nodes(deck, c.target, c.line)), c.dof, c.value)
             for step in deck.steps for c in step.cloads]
    (step,) = deck.steps
    sections = []
    for part in deck.parts.values():
        for section in part.sections:
            layers = expanded_layers(section)
            total = sum(layer.thickness for layer in layers)
            z = -total / 2
            expanded = []
            for k, layer in enumerate(layers, start=1):
                expanded.append(PlyFacts(k, layer.ply_name, layer.material, layer.thickness, layer.angle_deg, layer.integration_points, z, z + layer.thickness))
                z += layer.thickness
            fractions: dict[float, int] = {}
            for layer in layers:
                fractions[layer.angle_deg] = fractions.get(layer.angle_deg, 0) + 1
            orientation = part.orientations.get(section.orientation) if section.orientation else None
            n_elements = len(part.elsets[section.elset]) if section.elset in part.elsets else (len(part.elements) if part.elements is not None else 0)
            sections.append(SectionFacts(section.elset, n_elements, section.layup_name, section.orientation,
                                         (orientation.a, orientation.b) if orientation else None,
                                         (orientation.rotation_axis, orientation.rotation_deg) if orientation else None,
                                         section.section_integration, section.symmetric, tuple(expanded[: len(section.layers)]), tuple(expanded),
                                         total, tuple(fractions.items())))
    return ModelFacts(
        parts=tuple((p.name, len(p.nodes), len(p.elements) if p.elements is not None else 0, p.elements.element_type if p.elements is not None else "none")
                    for p in deck.parts.values()),
        instances=tuple((name, inst.part) for name, inst in deck.instances.items()),
        extent_x=extent_x, extent_y=extent_y, grid=grid, node_rows_y=tuple(float(v) for v in rows_y), partition_lines_y=tuple(lines),
        grip_lines_y=tuple(sorted({round(v, 12) for v in (extent_y[0], extent_y[1], *inner)})),
        row_counts=row_counts, element_bands=tuple(bands), edge_length_range=_range(edges),
        node_sets=tuple(node_sets), element_sets=tuple(element_sets), surfaces=tuple(surfaces), reference_nodes=tuple(reference_nodes),
        couplings=tuple(couplings), boundaries=tuple(boundaries), loads=tuple(loads), step=(step.name, step.nlgeom), sections=tuple(sections),
        ignored_keywords=tuple(sorted({k.split(": ", 1)[1] for k in deck.ignored_keywords})))
