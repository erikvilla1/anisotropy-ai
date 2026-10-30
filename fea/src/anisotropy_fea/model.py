"""The parsed Abaqus deck: what the reader produces and the kernel will consume (ADR-0029).

Everything here is data. Bulk mesh data are NumPy arrays; small records are frozen Pydantic models.
A `Deck` straight from `parse_deck` is unitless, exactly as the file; `to_si` converts it once the
caller has stated the unit system (ADR-0002, ADR-0003). `validate_deck` checks that every reference
resolves and that the model is one a flat laminate membrane kernel can represent, and returns the
notes a reader should see (for example a reference node listed inside its own coupled set).
"""

from __future__ import annotations

import dataclasses
import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply, abd_matrices

from .units import unit_factors

NodeKey = tuple[str | None, int]  # (instance name, label); None means an assembly-level node (a reference point)
ElementKey = tuple[str, int]  # (instance name, label)

SUPPORTED_ELEMENT_TYPES = ("S4", "S4R", "S4R5")
GLOBAL_AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
IN_PLANE_DOFS = (1, 2)
ROTATION_DOFS = (4, 5, 6)
PLAUSIBLE_MODULUS_PA = (1e9, 1e12)  # a modulus outside this range after conversion usually means the wrong unit system
SYMMETRY_TOLERANCE = 1e-9  # relative size of B that still counts as a symmetric layup (roundoff)


class DeckError(ValueError):
    """The deck is outside what anisotropy_fea reads, or a reference does not resolve. The message names the line."""


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Orientation(Record):
    name: str
    a: tuple[float, float, float]
    b: tuple[float, float, float]
    rotation_axis: int = 3
    rotation_deg: float = 0.0
    line: int


class Layer(Record):
    thickness: float
    integration_points: int
    material: str
    angle_deg: float
    ply_name: str | None = None


class ShellSection(Record):
    elset: str
    orientation: str | None
    layup_name: str | None
    symmetric: bool
    layers: tuple[Layer, ...]  # as listed in the deck; `expanded_layers` applies `symmetric`
    section_integration: str | None = None
    line: int


class Elastic(Record):
    kind: Literal["LAMINA", "ISOTROPIC"]
    E1: float
    E2: float
    nu12: float
    G12: float
    G13: float | None = None  # read and kept; a membrane has no transverse shear
    G23: float | None = None


class FailStress(Record):
    """`*Fail Stress` as written. Abaqus's sign convention for Xc and Yc is UNVERIFIED; consumers use magnitudes."""

    Xt: float
    Xc: float
    Yt: float
    Yc: float
    S: float
    f_star: float | None = None
    sigma_biax: float | None = None


class Material(Record):
    name: str
    elastic: Elastic | None
    fail_stress: FailStress | None
    line: int


@dataclass(frozen=True)
class Nodes:
    labels: np.ndarray  # int, shape (n,)
    xyz: np.ndarray  # float, shape (n, 3)

    def __len__(self) -> int:
        return int(self.labels.shape[0])

    def index_of(self, label: int) -> int:
        hits = np.flatnonzero(self.labels == label)
        if hits.size != 1:
            raise KeyError(label)
        return int(hits[0])


@dataclass(frozen=True)
class Elements:
    labels: np.ndarray  # int, shape (ne,)
    connectivity: np.ndarray  # int node labels, shape (ne, 4)
    element_type: str

    def __len__(self) -> int:
        return int(self.labels.shape[0])


@dataclass(frozen=True)
class Part:
    name: str
    nodes: Nodes
    elements: Elements | None
    nsets: dict[str, np.ndarray]
    elsets: dict[str, np.ndarray]
    orientations: dict[str, Orientation]
    sections: tuple[ShellSection, ...]


class Instance(Record):
    name: str
    part: str  # identity placement only; a translated or rotated instance is refused by the reader


class NodeSurface(Record):
    name: str
    nset: str
    internal: bool = False


class ElementSurface(Record):
    name: str
    elset: str
    side: str


class KinematicCoupling(Record):
    name: str
    ref_node_set: str
    surface: str
    dofs: frozenset[int]
    line: int


class Boundary(Record):
    target: str | NodeKey  # an assembly node set name, or one node
    dof_first: int
    dof_last: int
    value: float = 0.0
    line: int


class ConcentratedLoad(Record):
    target: str | NodeKey
    dof: int
    value: float
    line: int


class DistributedLoad(Record):
    """A `*Dload` line with the P label: a uniform pressure on an element set or one element (ADR-0053). A positive value pushes
    against the element normal, which is +z for counterclockwise nodes, so it loads the plate toward -z."""

    target: str | ElementKey  # an assembly element set name, or one element
    label: str  # "P" is the only label read
    value: float  # pressure; stress units
    line: int


class Step(Record):
    name: str
    nlgeom: bool
    boundaries: tuple[Boundary, ...]
    cloads: tuple[ConcentratedLoad, ...]
    line: int
    dloads: tuple[DistributedLoad, ...] = ()


@dataclass(frozen=True)
class Deck:
    heading: str
    parts: dict[str, Part]
    instances: dict[str, Instance]
    assembly_nodes: Nodes
    nsets: dict[str, tuple[NodeKey, ...]]
    elsets: dict[str, tuple[ElementKey, ...]]
    surfaces: dict[str, NodeSurface | ElementSurface]
    couplings: tuple[KinematicCoupling, ...]
    materials: dict[str, Material]
    model_boundaries: tuple[Boundary, ...]
    steps: tuple[Step, ...]
    ignored_keywords: tuple[str, ...]  # "line N: *Keyword" for every output request skipped
    source_sha256: str
    source_path: str | None = None
    units: str | None = None  # None until `to_si` has run; then the system the file was written in
    notes: tuple[str, ...] = ()


def node_name(key: NodeKey) -> str:
    """How this package names a node: `Instance.label`, or `Assembly.label` for a reference point."""
    instance, label = key
    return f"{instance}.{label}" if instance is not None else f"Assembly.{label}"


def expanded_layers(section: ShellSection) -> tuple[Layer, ...]:
    """The plies bottom-first: the listed layers, mirrored when the section is symmetric (ADR-0004 order)."""
    return section.layers + tuple(reversed(section.layers)) if section.symmetric else section.layers


def lamina_of(material: Material) -> Lamina:
    """The engine's lamina for a material that has already been converted to SI."""
    if material.elastic is None:
        raise DeckError(f"line {material.line}: material {material.name!r} has no *Elastic")
    e = material.elastic
    strengths = None
    if material.fail_stress is not None:
        f = material.fail_stress
        strengths = Strengths(F1t=abs(f.Xt), F1c=abs(f.Xc), F2t=abs(f.Yt), F2c=abs(f.Yc), F6=abs(f.S))
    return Lamina(E1=e.E1, E2=e.E2, G12=e.G12, nu12=e.nu12, strengths=strengths)


def section_plies(section: ShellSection, materials: dict[str, Material]) -> list[Ply]:
    """The engine plies of a section, bottom-first, for a deck already in SI."""
    plies = []
    for layer in expanded_layers(section):
        if layer.material not in materials:
            raise DeckError(f"line {section.line}: layer names material {layer.material!r}, which the deck does not define")
        plies.append(Ply(material=lamina_of(materials[layer.material]), angle_deg=layer.angle_deg, thickness_m=layer.thickness))
    return plies


def is_symmetric_layup(plies: list[Ply]) -> bool:
    """B vanishes relative to A times the thickness, so the membrane problem decouples from bending."""
    A, B, _ = abd_matrices(plies)
    thickness = sum(ply.thickness_m for ply in plies)
    return float(np.linalg.norm(B)) <= SYMMETRY_TOLERANCE * float(np.linalg.norm(A)) * thickness


# --- resolution helpers -------------------------------------------------------------------------


def part_of_instance(deck: Deck, instance: str, context: str) -> Part:
    if instance not in deck.instances:
        raise DeckError(f"{context}: instance {instance!r} is not defined")
    return deck.parts[deck.instances[instance].part]


def node_exists(deck: Deck, key: NodeKey) -> bool:
    instance, label = key
    nodes = deck.assembly_nodes if instance is None else part_of_instance(deck, instance, "node reference").nodes
    return bool(np.any(nodes.labels == label))


def node_xyz(deck: Deck, key: NodeKey) -> np.ndarray:
    instance, label = key
    nodes = deck.assembly_nodes if instance is None else part_of_instance(deck, instance, "node reference").nodes
    return nodes.xyz[nodes.index_of(label)]


def resolve_nodes(deck: Deck, target: str | NodeKey, line: int) -> tuple[NodeKey, ...]:
    """The nodes a boundary or load target names: an assembly node set, or one node."""
    if isinstance(target, str):
        if target not in deck.nsets:
            raise DeckError(f"line {line}: node set {target!r} is not defined in the assembly")
        return deck.nsets[target]
    if not node_exists(deck, target):
        raise DeckError(f"line {line}: node {node_name(target)} does not exist")
    return (target,)


def reference_node(deck: Deck, coupling: KinematicCoupling) -> NodeKey:
    keys = resolve_nodes(deck, coupling.ref_node_set, coupling.line)
    if len(keys) != 1:
        raise DeckError(f"line {coupling.line}: coupling {coupling.name!r} needs exactly one reference node; set "
                        f"{coupling.ref_node_set!r} has {len(keys)}")
    return keys[0]


def coupled_nodes(deck: Deck, coupling: KinematicCoupling) -> tuple[NodeKey, ...]:
    """The nodes the coupling drives: the surface's node set without the reference node itself."""
    surface = deck.surfaces.get(coupling.surface)
    if not isinstance(surface, NodeSurface):
        raise DeckError(f"line {coupling.line}: coupling {coupling.name!r} needs a node-based surface; "
                        f"{coupling.surface!r} is {'not defined' if surface is None else 'element-based'}")
    reference = reference_node(deck, coupling)
    return tuple(key for key in resolve_nodes(deck, surface.nset, coupling.line) if key != reference)


def all_boundaries(deck: Deck) -> tuple[Boundary, ...]:
    return deck.model_boundaries + tuple(b for step in deck.steps for b in step.boundaries)


def prescribed_dofs(deck: Deck, key: NodeKey) -> dict[int, float]:
    """Every dof held by a boundary condition at this node, with its value (0 for fixed)."""
    held: dict[int, float] = {}
    for boundary in all_boundaries(deck):
        if key in resolve_nodes(deck, boundary.target, boundary.line):
            for dof in range(boundary.dof_first, boundary.dof_last + 1):
                held[dof] = boundary.value
    return held


# --- validation ---------------------------------------------------------------------------------


def validate_deck(deck: Deck) -> tuple[str, ...]:
    """Every reference resolves and the model is a flat plate one of the kernels can represent; what each kernel refuses is checked
    when it is asked to solve (`membrane_limits` for the membrane). Returns notes."""
    notes: list[str] = []
    for part in deck.parts.values():
        _validate_part(deck, part)
    if deck.assembly_nodes.xyz.size and np.any(deck.assembly_nodes.xyz[:, 2] != 0):
        raise DeckError("assembly nodes have nonzero z coordinates; the membrane model is flat (z = 0)")
    for instance in deck.instances.values():
        if instance.part not in deck.parts:
            raise DeckError(f"instance {instance.name!r} names part {instance.part!r}, which is not defined")
    for name, keys in deck.nsets.items():
        for key in keys:
            if not node_exists(deck, key):
                raise DeckError(f"node set {name!r} names node {node_name(key)}, which does not exist")
    for name, keys in deck.elsets.items():
        for instance, label in keys:
            part = part_of_instance(deck, instance, f"element set {name!r}")
            if part.elements is None or not np.any(part.elements.labels == label):
                raise DeckError(f"element set {name!r} names element {instance}.{label}, which does not exist")
    for surface in deck.surfaces.values():
        if isinstance(surface, NodeSurface) and surface.nset not in deck.nsets:
            raise DeckError(f"surface {surface.name!r} names node set {surface.nset!r}, which is not defined")
        if isinstance(surface, ElementSurface) and surface.elset not in deck.elsets:
            raise DeckError(f"surface {surface.name!r} names element set {surface.elset!r}, which is not defined")
    if not deck.steps:
        raise DeckError("the deck has no *Step; there is nothing to solve")
    _validate_boundaries(deck)
    for step in deck.steps:
        for load in step.cloads:
            resolve_nodes(deck, load.target, load.line)
            if not 1 <= load.dof <= 6:
                raise DeckError(f"line {load.line}: concentrated load on dof {load.dof}; a shell node has dofs 1 to 6")
        for load in step.dloads:
            resolve_elements(deck, load.target, load.line)
    for coupling in deck.couplings:
        notes.extend(_validate_coupling(deck, coupling))
    return tuple(notes)


def resolve_elements(deck: Deck, target: str | ElementKey, line: int) -> tuple[ElementKey, ...]:
    """The elements an assembly element set name or one `Instance.label` stands for."""
    if isinstance(target, tuple):
        instance, label = target
        part = part_of_instance(deck, instance, f"line {line}")
        if part.elements is None or not np.any(part.elements.labels == label):
            raise DeckError(f"line {line}: element {instance}.{label} does not exist")
        return (target,)
    if target not in deck.elsets:
        raise DeckError(f"line {line}: element set {target!r} is not defined at the assembly level")
    return deck.elsets[target]


def membrane_limits(deck: Deck) -> None:
    """What the membrane kernel cannot represent, refused by name: an out-of-plane or rotational prescription with a value, a load on
    dofs 3 to 6, a distributed load, or a coupling whose reference node can rotate (ADR-0029; the flat shell of ADR-0053 takes them).
    Raises DeckError so the message names the deck line, as it did when validate_deck held these rules."""
    for boundary in all_boundaries(deck):
        for dof in range(boundary.dof_first, boundary.dof_last + 1):
            if boundary.value != 0 and dof == 3:
                raise DeckError(f"line {boundary.line}: a nonzero out-of-plane displacement (dof 3); the membrane model is in-plane only")
            if boundary.value != 0 and dof in ROTATION_DOFS:
                raise DeckError(f"line {boundary.line}: a nonzero prescribed rotation (dof {dof}); the membrane model has no rotations")
    for step in deck.steps:
        for load in step.cloads:
            if load.dof not in IN_PLANE_DOFS:
                raise DeckError(f"line {load.line}: concentrated load on dof {load.dof}; the membrane model takes dofs 1 and 2 only")
        for load in step.dloads:
            raise DeckError(f"line {load.line}: a distributed load; the membrane model takes concentrated loads on dofs 1 and 2 only")
    for coupling in deck.couplings:
        reference = reference_node(deck, coupling)
        held = prescribed_dofs(deck, reference)
        free_rotations = [dof for dof in ROTATION_DOFS if dof not in held]
        if free_rotations:
            raise DeckError(f"line {coupling.line}: reference node {node_name(reference)} of coupling {coupling.name!r} has rotation dofs "
                            f"{free_rotations} free; the membrane model represents the coupling as a rigid translation of the edge, "
                            f"so the reference node's rotations must be fixed")


def _validate_part(deck: Deck, part: Part) -> None:
    if part.nodes.xyz.size and np.any(part.nodes.xyz[:, 2] != 0):
        raise DeckError(f"part {part.name!r}: node z coordinates are not all zero; the membrane model is flat")
    for name, labels in part.nsets.items():
        missing = sorted(set(labels.tolist()) - set(part.nodes.labels.tolist()))
        if missing:
            raise DeckError(f"part {part.name!r}: node set {name!r} names nodes {missing[:5]} that the part does not define")
    if part.elements is None:
        if part.sections:
            raise DeckError(f"part {part.name!r}: has a shell section but no elements")
        return
    missing = sorted(set(part.elements.connectivity.ravel().tolist()) - set(part.nodes.labels.tolist()))
    if missing:
        raise DeckError(f"part {part.name!r}: elements name nodes {missing[:5]} that the part does not define")
    for name, labels in part.elsets.items():
        unknown = sorted(set(labels.tolist()) - set(part.elements.labels.tolist()))
        if unknown:
            raise DeckError(f"part {part.name!r}: element set {name!r} names elements {unknown[:5]} that the part does not define")
    covered: dict[int, ShellSection] = {}
    for section in part.sections:
        if section.elset not in part.elsets:
            raise DeckError(f"line {section.line}: shell section names element set {section.elset!r}, which part {part.name!r} does not define")
        if section.orientation is not None and section.orientation not in part.orientations:
            raise DeckError(f"line {section.line}: shell section names orientation {section.orientation!r}, which part {part.name!r} does not define")
        for label in part.elsets[section.elset].tolist():
            if label in covered:
                raise DeckError(f"line {section.line}: element {part.name}.{label} is in two shell sections")
            covered[label] = section
        for layer in expanded_layers(section):
            if layer.material not in deck.materials:
                raise DeckError(f"line {section.line}: layer names material {layer.material!r}, which the deck does not define")
            if deck.materials[layer.material].elastic is None:
                raise DeckError(f"line {section.line}: material {layer.material!r} has no *Elastic")
    uncovered = sorted(set(part.elements.labels.tolist()) - set(covered))
    if uncovered:
        raise DeckError(f"part {part.name!r}: elements {uncovered[:5]}{'...' if len(uncovered) > 5 else ''} have no shell section")


def _validate_boundaries(deck: Deck) -> None:
    seen: dict[tuple[NodeKey, int], tuple[float, int]] = {}
    for boundary in all_boundaries(deck):
        if not 1 <= boundary.dof_first <= boundary.dof_last <= 6:
            raise DeckError(f"line {boundary.line}: boundary dofs {boundary.dof_first}..{boundary.dof_last} are outside 1..6")
        keys = resolve_nodes(deck, boundary.target, boundary.line)
        if boundary.value != 0 and boundary.dof_first <= 3 < boundary.dof_last:
            raise DeckError(f"line {boundary.line}: one nonzero value for dofs {boundary.dof_first} to {boundary.dof_last} would be a length and an "
                            "angle at once; write translations and rotations on separate lines")
        for dof in range(boundary.dof_first, boundary.dof_last + 1):
            for key in keys:
                earlier = seen.get((key, dof))
                if earlier is not None and earlier[0] != boundary.value:
                    raise DeckError(f"line {boundary.line}: node {node_name(key)} dof {dof} is prescribed {boundary.value} here "
                                    f"and {earlier[0]} at line {earlier[1]}")
                seen[(key, dof)] = (boundary.value, boundary.line)


def _validate_coupling(deck: Deck, coupling: KinematicCoupling) -> list[str]:
    reference = reference_node(deck, coupling)
    if not set(IN_PLANE_DOFS) <= coupling.dofs:
        raise DeckError(f"line {coupling.line}: coupling {coupling.name!r} leaves an in-plane dof free; the kernels need dofs 1 and 2 coupled")
    surface = deck.surfaces.get(coupling.surface)
    if not isinstance(surface, NodeSurface):
        raise DeckError(f"line {coupling.line}: coupling {coupling.name!r} needs a node-based surface; "
                        f"{coupling.surface!r} is {'not defined' if surface is None else 'element-based'}")
    members = resolve_nodes(deck, surface.nset, coupling.line)
    notes = []
    if reference in members:
        notes.append(f"line {coupling.line}: reference node {node_name(reference)} is listed inside its own coupled set "
                     f"{surface.nset!r}; it is dropped from the coupled nodes (Abaqus runs the deck as written)")
    if len(coupled_nodes(deck, coupling)) == 0:
        raise DeckError(f"line {coupling.line}: coupling {coupling.name!r} drives no nodes")
    return notes


# --- units --------------------------------------------------------------------------------------


def to_si(deck: Deck, units: str) -> Deck:
    """The same deck with every dimensioned number in SI base units, and `units` recorded."""
    factors = unit_factors(units)
    length, stress, force = factors["length"], factors["stress"], factors["force"]

    def scale_nodes(nodes: Nodes) -> Nodes:
        return Nodes(labels=nodes.labels, xyz=nodes.xyz * length)

    def scale_section(section: ShellSection) -> ShellSection:
        layers = tuple(layer.model_copy(update={"thickness": layer.thickness * length}) for layer in section.layers)
        return section.model_copy(update={"layers": layers})

    def scale_material(material: Material) -> Material:
        update: dict = {}
        if material.elastic is not None:
            e = material.elastic
            update["elastic"] = e.model_copy(update={
                "E1": e.E1 * stress, "E2": e.E2 * stress, "G12": e.G12 * stress,
                "G13": None if e.G13 is None else e.G13 * stress, "G23": None if e.G23 is None else e.G23 * stress,
            })
        if material.fail_stress is not None:
            f = material.fail_stress
            update["fail_stress"] = f.model_copy(update={
                "Xt": f.Xt * stress, "Xc": f.Xc * stress, "Yt": f.Yt * stress, "Yc": f.Yc * stress, "S": f.S * stress,
                "sigma_biax": None if f.sigma_biax is None else f.sigma_biax * stress,
            })
        return material.model_copy(update=update)

    def scale_boundary(boundary: Boundary) -> Boundary:
        # Translations (dofs 1 to 3) are lengths; rotations (dofs 4 to 6) are angles in radians, the same in every system. A nonzero
        # value that spans both is refused by validate_deck.
        return boundary.model_copy(update={"value": boundary.value * length}) if boundary.dof_last <= 3 else boundary

    def scale_step(step: Step) -> Step:
        return step.model_copy(update={
            "boundaries": tuple(scale_boundary(b) for b in step.boundaries),
            "cloads": tuple(load.model_copy(update={"value": load.value * (force if load.dof <= 3 else force * length)}) for load in step.cloads),
            "dloads": tuple(load.model_copy(update={"value": load.value * stress}) for load in step.dloads),
        })

    parts = {
        name: dataclasses.replace(part, nodes=scale_nodes(part.nodes), sections=tuple(scale_section(s) for s in part.sections))
        for name, part in deck.parts.items()
    }
    materials = {name: scale_material(material) for name, material in deck.materials.items()}
    for material in materials.values():
        if material.elastic is not None:
            for modulus in (material.elastic.E1, material.elastic.E2, material.elastic.G12):
                if not PLAUSIBLE_MODULUS_PA[0] <= modulus <= PLAUSIBLE_MODULUS_PA[1]:
                    warnings.warn(f"material {material.name!r}: a modulus of {modulus:.3g} Pa after converting from {units!r} is outside "
                                  f"1 GPa to 1000 GPa; check that the deck is really written in {units!r}", stacklevel=2)
    return dataclasses.replace(
        deck,
        parts=parts,
        assembly_nodes=scale_nodes(deck.assembly_nodes),
        materials=materials,
        model_boundaries=tuple(scale_boundary(b) for b in deck.model_boundaries),
        steps=tuple(scale_step(step) for step in deck.steps),
        units=units,
    )
