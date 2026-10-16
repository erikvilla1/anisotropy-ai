"""Flat arrays for the kernel, built from a validated deck in SI (ADR-0029).

The mesh numbers every node of every instance and then the assembly's reference nodes, so a
reference node has degrees of freedom like any other node and a kinematic coupling can alias the
coupled nodes to it. Each element carries the index of its section; a section holds the engine
plies and the laminate membrane stiffness `A` they give.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from anisotropy_engine.laminate import Ply, abd_matrices

from .model import Deck, ElementKey, Material, NodeKey, ShellSection, is_symmetric_layup, section_plies


class KernelError(ValueError):
    """The deck is valid but outside what the membrane kernel can solve, or the system cannot be solved."""


@dataclass(frozen=True)
class Section:
    name: str
    plies: list[Ply]
    A: np.ndarray  # (3, 3), N/m: N = A eps with engineering shear strain (ADR-0004)


@dataclass(frozen=True)
class Mesh:
    node_keys: tuple[NodeKey, ...]
    xy: np.ndarray  # (n, 2), m
    connectivity: np.ndarray  # (ne, 4) node indices, counterclockwise as the deck lists them
    element_keys: tuple[ElementKey, ...]
    element_section: np.ndarray  # (ne,) index into `sections`
    sections: tuple[Section, ...]
    index: dict[NodeKey, int]

    def node(self, key: NodeKey) -> int:
        try:
            return self.index[key]
        except KeyError:
            raise KernelError(f"node {key[0] or 'Assembly'}.{key[1]} is not in the mesh") from None

    def element(self, key: ElementKey) -> int:
        try:
            return self.element_keys.index(key)
        except ValueError:
            raise KernelError(f"element {key[0]}.{key[1]} is not in the mesh") from None

    @property
    def node_count(self) -> int:
        return len(self.node_keys)

    @property
    def element_count(self) -> int:
        return len(self.element_keys)


def section_stiffness(section: ShellSection, materials: dict[str, Material], name: str) -> Section:
    """The engine plies of a section and their membrane stiffness; refuses a layup whose B does not vanish."""
    plies = section_plies(section, materials)
    if not is_symmetric_layup(plies):
        A, B, _ = abd_matrices(plies)
        thickness = sum(ply.thickness_m for ply in plies)
        ratio = float(np.linalg.norm(B) / (np.linalg.norm(A) * thickness))
        raise KernelError(f"section {name!r}: layup is not symmetric (||B|| / (||A|| h) = {ratio:.2g}); the membrane model needs "
                          "B = 0. Add `symmetric` to the shell section or mirror the layers.")
    A, _, _ = abd_matrices(plies)
    return Section(name=name, plies=plies, A=A)


def mesh_from_deck(deck: Deck) -> Mesh:
    """Instances' nodes and elements, then the assembly's reference nodes, as flat arrays."""
    if deck.units is None:
        raise KernelError("the deck has not been converted to SI; read it with read_deck(path, units)")
    keys: list[NodeKey] = []
    xy: list[tuple[float, float]] = []
    connectivity: list[list[int]] = []
    element_keys: list[ElementKey] = []
    element_section: list[int] = []
    sections: list[Section] = []
    index: dict[NodeKey, int] = {}

    for instance_name, instance in deck.instances.items():
        part = deck.parts[instance.part]
        for label, point in zip(part.nodes.labels.tolist(), part.nodes.xyz):
            key: NodeKey = (instance_name, label)
            index[key] = len(keys)
            keys.append(key)
            xy.append((float(point[0]), float(point[1])))
        if part.elements is None:
            continue
        section_of_label: dict[int, int] = {}
        for section in part.sections:
            sections.append(section_stiffness(section, deck.materials, f"{instance_name}.{section.elset}"))
            for label in part.elsets[section.elset].tolist():
                section_of_label[label] = len(sections) - 1
        for label, nodes in zip(part.elements.labels.tolist(), part.elements.connectivity):
            connectivity.append([index[(instance_name, int(node))] for node in nodes])
            element_keys.append((instance_name, label))
            element_section.append(section_of_label[label])
    for label, point in zip(deck.assembly_nodes.labels.tolist(), deck.assembly_nodes.xyz):
        key = (None, label)
        index[key] = len(keys)
        keys.append(key)
        xy.append((float(point[0]), float(point[1])))
    if not connectivity:
        raise KernelError("the deck has no elements to solve")
    return Mesh(
        node_keys=tuple(keys),
        xy=np.asarray(xy, dtype=float),
        connectivity=np.asarray(connectivity, dtype=int),
        element_keys=tuple(element_keys),
        element_section=np.asarray(element_section, dtype=int),
        sections=tuple(sections),
        index=index,
    )
