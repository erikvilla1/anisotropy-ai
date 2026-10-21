"""Convert a deck our reader has read (the team's Abaqus coupon decks) into a CalculiX deck (ADR-0030).

What changes, and why, each from the CalculiX manual: composite shells must be S8R, so the four-node mesh gains a
midside node on every edge; a kinematic coupling's reference node cannot have its reaction printed, so every
coupled node receives the reference node's own prescribed values directly (the same model when the reference
rotations are fixed, which the reader already requires); there is no LAMINA material, so the engineering
constants need E3, nu13 and nu23, which an Abaqus deck does not carry and the caller must state; a composite
layer line has four fields and the symmetric half is written out in full with one *ORIENTATION per ply angle.
Nothing is assumed silently: the out-of-plane constants and every rewrite are listed in the deck's header.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .mesh import Mesh, mesh_from_deck
from .model import Deck, ElementKey, NodeKey, coupled_nodes, expanded_layers, node_name, prescribed_dofs, reference_node, resolve_nodes
from .units import from_si
from .write_abaqus import _rows, number
from .write_calculix import REFERENCE_TEMPERATURE, CalculixWriterError, orientation_name


@dataclass(frozen=True)
class TransverseChoice:
    """The out-of-plane constants CalculiX's three-dimensional law needs and an Abaqus LAMINA material lacks."""

    nu23: float | None = None  # required unless plane_stress
    transverse_isotropy: bool = True  # E3 = E2, nu13 = nu12
    E3: float | None = None  # Pa, when transverse_isotropy is False
    nu13: float | None = None
    plane_stress: bool = False  # nu13 = nu23 = 0: the three-dimensional law reduces to the plane stress that Abaqus LAMINA and our kernel assume

    def resolve(self, E2: float, nu12: float) -> tuple[float, float, float]:
        """E3, nu13 and nu23 for the ENGINEERING CONSTANTS line."""
        if self.plane_stress:
            if self.nu23 is not None or self.nu13 is not None:
                raise CalculixWriterError("with plane_stress, nu13 = nu23 = 0 are written; do not give them")
        elif self.nu23 is None:
            raise CalculixWriterError("nu23 must be given unless plane_stress")
        if self.transverse_isotropy:
            if self.E3 is not None or self.nu13 is not None:
                raise CalculixWriterError("with transverse_isotropy, E3 and nu13 are derived (E3 = E2, nu13 = nu12); do not give them")
            E3, nu13 = E2, nu12
        else:
            if self.E3 is None or (self.nu13 is None and not self.plane_stress):
                raise CalculixWriterError("without transverse_isotropy, E3 and nu13 must be given")
            E3, nu13 = self.E3, self.nu13
        return (E3, 0.0, 0.0) if self.plane_stress else (E3, nu13, self.nu23)


@dataclass(frozen=True)
class PromotedMesh:
    xy: np.ndarray  # (n2, 2): the corner nodes first (same indices as the order-1 mesh), then the midside nodes
    connectivity: np.ndarray  # (ne, 8)
    node_sets: dict[str, np.ndarray]  # order-2 sets: a midside node joins a set when both its corners are in it


def promote_to_order2(mesh: Mesh, corner_sets: dict[str, np.ndarray]) -> PromotedMesh:
    """Add one midside node per unique element edge; the S8R node order is the four corners then the four edge midpoints."""
    xy = [tuple(p) for p in mesh.xy]
    edge_node: dict[tuple[int, int], int] = {}
    mids = np.zeros_like(mesh.connectivity)
    for e, nodes in enumerate(mesh.connectivity):
        for k in range(4):
            a, b = int(nodes[k]), int(nodes[(k + 1) % 4])
            key = (min(a, b), max(a, b))
            if key not in edge_node:
                edge_node[key] = len(xy)
                xy.append(((xy[a][0] + xy[b][0]) / 2, (xy[a][1] + xy[b][1]) / 2))
            mids[e, k] = edge_node[key]
    node_sets = {}
    for name, corners in corner_sets.items():
        members = set(corners.tolist())
        extra = [mid for (a, b), mid in edge_node.items() if a in members and b in members]
        node_sets[name] = np.array(sorted(members | set(extra)), dtype=int)
    return PromotedMesh(xy=np.asarray(xy, dtype=float), connectivity=np.hstack([mesh.connectivity, mids]), node_sets=node_sets)


def calculix_from_deck(deck: Deck, transverse: TransverseChoice, probe_elements: list[ElementKey] | None = None,
                       units: str | None = None) -> str:
    """The CalculiX deck for a deck read with `read_deck` (SI inside); numbers written in the deck's unit system."""
    units = units or deck.units
    if units is None:
        raise CalculixWriterError("the deck has no unit system: read it with read_deck(path, units)")
    mesh = mesh_from_deck(deck)
    if any(part.elements is not None and part.elements.element_type not in ("S4", "S4R", "S4R5") for part in deck.parts.values()):
        raise CalculixWriterError("only four-node shell decks are converted (the mesh is promoted to S8R)")
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    stress = lambda v: from_si(v, "stress", units)  # noqa: E731

    # node sets as corner-node indices: the assembly's sets plus one set per coupling for its coupled nodes
    corner_sets: dict[str, np.ndarray] = {}
    for name, keys in deck.nsets.items():
        indices = [mesh.node(key) for key in keys if key[0] is not None]  # reference nodes are not carried over
        if indices:
            corner_sets[name] = np.array(sorted(indices), dtype=int)
    grips: list[tuple[str, NodeKey]] = []
    for coupling in deck.couplings:
        name = f"Coupled-{coupling.name}"
        corner_sets[name] = np.array(sorted(mesh.node(key) for key in coupled_nodes(deck, coupling)), dtype=int)
        grips.append((name, reference_node(deck, coupling)))
    promoted = promote_to_order2(mesh, corner_sets)
    corner_count = mesh.node_count
    # reference nodes also appear in ordinary boundary conditions: those move to the coupled set; other targets stay
    reference_keys = {ref for _, ref in grips}

    out: list[str] = ["*HEADING", f"CalculiX deck converted by anisotropy_fea from {deck.source_path or 'a read deck'} (sha256 {deck.source_sha256[:16]})"]
    out.append(f"** Source deck: {mesh.node_count} corner nodes, {mesh.element_count} four-node shell elements, promoted to S8R with "
               f"{promoted.xy.shape[0] - corner_count} midside nodes (CalculiX composite shells are S8R only).")
    out.append(f"** Units of this deck: {units}. Numbers are the source deck's, converted from SI.")
    if transverse.plane_stress:
        E3_note = "E3 = E2 (transverse isotropy, stated by the caller)" if transverse.transverse_isotropy else "E3 given by the caller"
        out.append(f"** Out-of-plane constants, absent from the Abaqus LAMINA material: {E3_note}; nu13 = nu23 = 0 written for plane stress, "
                   "as the LAMINA law and our kernel assume (chosen by the caller).")
    else:
        if transverse.nu23 is None:
            raise CalculixWriterError("nu23 must be given unless plane_stress")
        E3_note = "E3 = E2 and nu13 = nu12 (transverse isotropy, stated by the caller)" if transverse.transverse_isotropy else "E3 and nu13 given by the caller"
        out.append(f"** Out-of-plane constants, absent from the Abaqus LAMINA material: {E3_note}; nu23 = {transverse.nu23:g} given by the caller.")
    for name, ref in grips:
        held = prescribed_dofs(deck, ref)
        out.append(f"** Coupling {name[8:]}: reference node {node_name(ref)} replaced by direct constraints on its {promoted.node_sets[name].size} coupled nodes "
                   f"({', '.join(f'dof {d} = {length(v) if d <= 3 else v:g}' for d, v in sorted(held.items()))}); CalculiX cannot print a reference node's reaction.")
    for note in deck.notes:
        out.append(f"** Reader note: {note}")
    out.append("*NODE, NSET=Nall")
    for index, (x, y) in enumerate(promoted.xy, start=1):
        out.append(f"{index}, {number(length(x))}, {number(length(y))}, 0.")
    section_elsets: dict[str, list[int]] = {}
    out.append("*ELEMENT, TYPE=S8R, ELSET=All")
    for e, nodes in enumerate(promoted.connectivity, start=1):
        out.append(f"{e}, " + ", ".join(str(int(n) + 1) for n in nodes))
        section_elsets.setdefault(mesh.sections[mesh.element_section[e - 1]].name, []).append(e)
    for name, indices in promoted.node_sets.items():
        out.append(f"*NSET, NSET={name}")
        out += _rows([int(i) + 1 for i in indices])
    for name, keys in deck.elsets.items():
        labels = [mesh.element(key) + 1 for key in keys]
        out.append(f"*ELSET, ELSET={name}")
        out += _rows(labels)
    if probe_elements:
        out.append("*ELSET, ELSET=Probe")
        out += _rows([mesh.element(key) + 1 for key in probe_elements])
    for name, labels in section_elsets.items():
        out.append(f"*ELSET, ELSET=Section-{name.replace('.', '-')}")
        out += _rows(labels)

    angles: set[float] = set()
    for material in deck.materials.values():
        e = material.elastic
        if e is None:
            raise CalculixWriterError(f"material {material.name!r} has no elastic definition")
        E3, nu13, nu23 = transverse.resolve(e.E2, e.nu12)
        if e.G13 is None or e.G23 is None:
            raise CalculixWriterError(f"material {material.name!r}: LAMINA needs G13 and G23 for the three-dimensional law")
        out.append(f"*MATERIAL, NAME={material.name}")
        out.append("*ELASTIC, TYPE=ENGINEERING CONSTANTS")
        out.append(", ".join(number(stress(v)) for v in (e.E1, e.E2, E3)) + f", {number(e.nu12)}, {number(nu13)}, {number(nu23)}, "
                   + ", ".join(number(stress(v)) for v in (e.G12, e.G13)))
        out.append(f"{number(stress(e.G23))}, {number(REFERENCE_TEMPERATURE)}")
    for part in deck.parts.values():
        for section in part.sections:
            angles.update(layer.angle_deg for layer in expanded_layers(section))
    for angle in sorted(angles):
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        out.append(f"*ORIENTATION, NAME={orientation_name(angle)}")
        out.append(f"{number(c)}, {number(s)}, 0., {number(-s)}, {number(c)}, 0.")
    for instance_name, instance in deck.instances.items():
        for section in deck.parts[instance.part].sections:
            name = f"{instance_name}.{section.elset}"
            out.append(f"*SHELL SECTION, ELSET=Section-{name.replace('.', '-')}, COMPOSITE")
            for layer in expanded_layers(section):
                out.append(f"{number(length(layer.thickness))}, , {layer.material}, {orientation_name(layer.angle_deg)}")

    fixed: list[str] = []
    moving: list[str] = []
    for boundary in deck.model_boundaries + tuple(b for step in deck.steps for b in step.boundaries):
        keys = resolve_nodes(deck, boundary.target, boundary.line)
        targets: list[str] = []
        if any(key in reference_keys for key in keys):
            targets += [name for name, ref in grips if ref in keys]
        if any(key not in reference_keys for key in keys):
            if isinstance(boundary.target, str):
                targets.append(boundary.target)
            else:
                targets.append(str(mesh.node(boundary.target) + 1))
        for target in targets:
            line = f"{target}, {boundary.dof_first}, {boundary.dof_last}"
            if boundary.value != 0.0:
                moving.append(line + f", {number(length(boundary.value))}")
            else:
                fixed.append(line)
    if fixed:
        out.append("*BOUNDARY")
        out += fixed
    out.append("*STEP")
    out.append("*STATIC")
    if moving:
        out.append("*BOUNDARY")
        out += moving
    for step in deck.steps:
        if step.cloads:
            out.append("*CLOAD")
            for load in step.cloads:
                for key in resolve_nodes(deck, load.target, load.line):
                    out.append(f"{mesh.node(key) + 1}, {load.dof}, {number(from_si(load.value, 'force', units))}")
    for name, _ in grips:
        out.append(f"*NODE PRINT, NSET={name}, TOTALS=YES")
        out.append("RF")
    out.append("*NODE PRINT, NSET=Nall")
    out.append("U")
    if probe_elements:
        out.append("*EL PRINT, ELSET=Probe, GLOBAL=YES")
        out.append("S, E, COORD")
    out.append("*NODE FILE")
    out.append("U")
    out.append("*EL FILE")
    out.append("S, E")
    out.append("*END STEP")
    return "\n".join(out) + "\n"
