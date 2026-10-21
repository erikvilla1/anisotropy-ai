"""Is our generated model the same model as another deck, the team's? Item by item, from the two parsed decks (ADR-0035).

Both decks are read by our reader and converted to SI. The decks number their nodes and elements differently, so nodes
are matched by position (within a tolerance the caller states) and elements by the matched nodes of their corners. Every
physical item is then compared through that map: element type, the layup with each ply's material constants, the shell
orientation, the grips (each coupling's reference point, the nodes it drives and its dofs), every prescribed dof node by
node, the concentrated loads, and the steps. Names (part, instance, material, sets) are listed but not judged, because they
do not change the solution; strengths are listed but not judged, because a linear solve does not read them. The node and
element maps are returned so the two decks' results can be put side by side.

Our reader accepts only linear static steps (nlgeom=NO, *Static), so two decks that both read have the same procedure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .model import Deck, ElementKey, NodeKey, all_boundaries, coupled_nodes, expanded_layers, reference_node, resolve_nodes
from .units import from_si, unit_factors

RELATIVE = 1e-9  # material constants, thicknesses and prescribed values count as equal within this relative difference
UNIT_NAMES = {"mm-MPa": ("mm", "MPa"), "m-Pa": ("m", "Pa")}


class EquivalenceError(ValueError):
    """The decks cannot be compared item by item (more than one part or instance, nodes that do not match one to one)."""


@dataclass(frozen=True)
class EquivalenceItem:
    item: str
    team: str  # the reference deck, as it states the item
    ours: str
    same: bool | None  # None: listed, not judged (names; values a linear solve does not read)


@dataclass(frozen=True)
class DeckEquivalence:
    items: tuple[EquivalenceItem, ...]
    node_map: dict[NodeKey, NodeKey]  # reference node -> our node, instance and assembly nodes
    element_map: dict[ElementKey, ElementKey]  # reference element -> our element
    largest_node_offset: float  # m, over all matched nodes
    tolerance: float  # m, as the caller stated it
    units: str  # the unit system the item texts are written in

    @property
    def same_model(self) -> bool:
        """Every judged item agrees."""
        return all(item.same is not False for item in self.items)

    @property
    def differences(self) -> tuple[EquivalenceItem, ...]:
        return tuple(item for item in self.items if item.same is False)


def _only(mapping: dict, what: str, deck: Deck):
    if len(mapping) != 1:
        raise EquivalenceError(f"{deck.source_path or 'deck'}: equivalence compares decks with one {what}; this one has {len(mapping)}")
    return next(iter(mapping.values()))


def _close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= RELATIVE * max(abs(a), abs(b), 1e-300)


def _match_points(reference: np.ndarray, ours: np.ndarray, tolerance: float, what: str) -> tuple[np.ndarray, float]:
    """Index into `ours` of the point at each reference position; one to one and within the tolerance, or refused."""
    if len(reference) != len(ours):
        raise EquivalenceError(f"{what}: the reference deck has {len(reference)}, ours {len(ours)}")
    if len(reference) == 0:
        return np.zeros(0, dtype=int), 0.0
    distance, index = cKDTree(ours).query(reference)
    largest = float(distance.max())
    if largest > tolerance:
        worst = int(distance.argmax())
        raise EquivalenceError(f"{what}: the reference point at {reference[worst].tolist()} m has no point of ours within {tolerance:g} m "
                               f"(nearest {largest:g} m away)")
    if len(set(index.tolist())) != len(index):
        raise EquivalenceError(f"{what}: two reference points match the same point of ours; the tolerance {tolerance:g} m is too coarse")
    return index, largest


def _held(deck: Deck) -> dict[NodeKey, dict[int, float]]:
    held: dict[NodeKey, dict[int, float]] = {}
    for boundary in all_boundaries(deck):
        for key in resolve_nodes(deck, boundary.target, boundary.line):
            for dof in range(boundary.dof_first, boundary.dof_last + 1):
                held.setdefault(key, {})[dof] = boundary.value
    return held


def _layer_text(layers) -> str:
    return "/".join(f"{layer.angle_deg:g}" for layer in layers)


def deck_equivalence(reference: Deck, ours: Deck, tolerance: float, units: str) -> DeckEquivalence:
    """Compare two SI decks of one part and one instance each; `tolerance` (m) is the largest node offset that counts as the same position.

    The comparison is made in SI; `units` ("mm-MPa" or "m-Pa") is only how the item texts state lengths and stresses.
    """
    if reference.units is None or ours.units is None:
        raise EquivalenceError("deck_equivalence needs both decks in SI (read_deck with units, or to_si)")
    if not tolerance > 0:
        raise EquivalenceError("tolerance must be a positive length in metres")
    unit_factors(units)
    length_unit, stress_unit = UNIT_NAMES[units]
    length = lambda v: f"{from_si(v, 'length', units):.6g} {length_unit}"  # noqa: E731
    stress = lambda v: f"{from_si(v, 'stress', units):.6g}"  # noqa: E731
    ref_part, our_part = _only(reference.parts, "part", reference), _only(ours.parts, "part", ours)
    ref_inst, our_inst = _only(reference.instances, "instance", reference), _only(ours.instances, "instance", ours)
    if ref_part.elements is None or our_part.elements is None:
        raise EquivalenceError("both decks need elements")
    items: list[EquivalenceItem] = []

    def add(item: str, team: str, mine: str, same: bool | None) -> None:
        items.append(EquivalenceItem(item, team, mine, same))

    # names: listed, not judged
    # names: "same" when they match, listed (never a difference) when they do not
    add("Part / instance names", f"{ref_part.name} / {ref_inst.name}", f"{our_part.name} / {our_inst.name}",
        True if (ref_part.name, ref_inst.name) == (our_part.name, our_inst.name) else None)

    # nodes by position
    instance_index, offset_instance = _match_points(ref_part.nodes.xyz, our_part.nodes.xyz, tolerance, "instance nodes")
    assembly_index, offset_assembly = _match_points(reference.assembly_nodes.xyz, ours.assembly_nodes.xyz, tolerance, "reference points")
    node_map: dict[NodeKey, NodeKey] = {}
    for k, label in enumerate(ref_part.nodes.labels.tolist()):
        node_map[(ref_inst.name, label)] = (our_inst.name, int(our_part.nodes.labels[instance_index[k]]))
    for k, label in enumerate(reference.assembly_nodes.labels.tolist()):
        node_map[(None, label)] = (None, int(ours.assembly_nodes.labels[assembly_index[k]]))
    largest = max(offset_instance, offset_assembly)
    add("Nodes", f"{len(ref_part.nodes.labels)} on the part, {len(reference.assembly_nodes.labels)} reference points",
        f"{len(our_part.nodes.labels)} on the part, {len(ours.assembly_nodes.labels)} reference points", True)
    add("Node positions", "as written", f"every node at a reference node's position; largest offset {from_si(largest, 'length', units):.3g} {length_unit}", largest <= tolerance)

    # elements by their matched corner nodes
    our_by_nodes = {frozenset(row.tolist()): int(label) for label, row in zip(our_part.elements.labels, our_part.elements.connectivity)}
    element_map: dict[ElementKey, ElementKey] = {}
    unmatched = 0
    for label, row in zip(ref_part.elements.labels.tolist(), ref_part.elements.connectivity):
        mapped = frozenset(node_map[(ref_inst.name, int(n))][1] for n in row)
        if mapped in our_by_nodes:
            element_map[(ref_inst.name, label)] = (our_inst.name, our_by_nodes[mapped])
        else:
            unmatched += 1
    add("Elements", f"{len(ref_part.elements.labels)} {ref_part.elements.element_type}", f"{len(our_part.elements.labels)} {our_part.elements.element_type}",
        ref_part.elements.element_type == our_part.elements.element_type and len(ref_part.elements.labels) == len(our_part.elements.labels))
    add("Element connectivity", "as written", "every element on the same corner nodes" if not unmatched else f"{unmatched} elements have no counterpart",
        unmatched == 0)

    # section, layup, orientation, material constants per ply
    if len(ref_part.sections) != 1 or len(our_part.sections) != 1:
        raise EquivalenceError("equivalence compares decks with one shell section")
    ref_section, our_section = ref_part.sections[0], our_part.sections[0]
    covers = lambda part, section: set(part.elsets[section.elset].tolist()) == set(part.elements.labels.tolist())  # noqa: E731
    ref_layers, our_layers = expanded_layers(ref_section), expanded_layers(our_section)
    add("Section", f"composite shell on {'all' if covers(ref_part, ref_section) else 'some'} elements"
        + (", listed as the symmetric half" if ref_section.symmetric else ""),
        f"composite shell on {'all' if covers(our_part, our_section) else 'some'} elements" + (", listed as the symmetric half" if our_section.symmetric else ""),
        covers(ref_part, ref_section) and covers(our_part, our_section))
    same_angles = len(ref_layers) == len(our_layers) and all(_close(a.angle_deg, b.angle_deg) for a, b in zip(ref_layers, our_layers))
    add("Layup, bottom first", f"[{_layer_text(ref_layers)}], {len(ref_layers)} plies", f"[{_layer_text(our_layers)}], {len(our_layers)} plies", same_angles)
    same_thickness = len(ref_layers) == len(our_layers) and all(_close(a.thickness, b.thickness) for a, b in zip(ref_layers, our_layers))
    add("Ply thickness", ", ".join(sorted({length(layer.thickness) for layer in ref_layers})),
        ", ".join(sorted({length(layer.thickness) for layer in our_layers})), same_thickness)
    same_points = len(ref_layers) == len(our_layers) and all(a.integration_points == b.integration_points for a, b in zip(ref_layers, our_layers))
    add("Integration points per ply", ", ".join(sorted({str(layer.integration_points) for layer in ref_layers})),
        ", ".join(sorted({str(layer.integration_points) for layer in our_layers})), same_points)
    ref_ori = ref_part.orientations.get(ref_section.orientation) if ref_section.orientation else None
    our_ori = our_part.orientations.get(our_section.orientation) if our_section.orientation else None
    ori_text = lambda o: "global axes (none)" if o is None else f"a = {list(o.a)}, b = {list(o.b)}, {o.rotation_deg:g} deg about {o.rotation_axis}"  # noqa: E731
    same_ori = (ref_ori is None and our_ori is None) or (ref_ori is not None and our_ori is not None and ref_ori.a == our_ori.a and ref_ori.b == our_ori.b
                                                         and ref_ori.rotation_axis == our_ori.rotation_axis and _close(ref_ori.rotation_deg, our_ori.rotation_deg))
    add("Shell orientation", ori_text(ref_ori), ori_text(our_ori), same_ori)

    ref_materials = {layer.material for layer in ref_layers}
    our_materials = {layer.material for layer in our_layers}
    add("Material names", ", ".join(sorted(ref_materials)), ", ".join(sorted(our_materials)), True if ref_materials == our_materials else None)
    add("Section set / layup names", f"{ref_section.elset} / {ref_section.layup_name}", f"{our_section.elset} / {our_section.layup_name}",
        True if (ref_section.elset, ref_section.layup_name) == (our_section.elset, our_section.layup_name) else None)
    for name, label in (("E1", "E1"), ("E2", "E2"), ("nu12", "nu12"), ("G12", "G12"), ("G13", "G13"), ("G23", "G23")):
        ref_values = [getattr(reference.materials[layer.material].elastic, name) for layer in ref_layers]
        our_values = [getattr(ours.materials[layer.material].elastic, name) for layer in our_layers]
        shown = (lambda v: f"{v:g}") if name == "nu12" else stress
        text = lambda values, shown=shown: ", ".join(sorted({"none" if v is None else shown(v) for v in values}))  # noqa: E731
        add(f"Material {label}" + ("" if name == "nu12" else f" ({stress_unit})"), text(ref_values), text(our_values),
            len(ref_values) == len(our_values) and all(_close(a, b) for a, b in zip(ref_values, our_values)))
    strength_text = lambda deck, names: "; ".join(  # noqa: E731
        f"{n}: none" if deck.materials[n].fail_stress is None else
        f"{n}: F1t {stress(deck.materials[n].fail_stress.Xt)}, F1c {stress(abs(deck.materials[n].fail_stress.Xc))}, F2t {stress(deck.materials[n].fail_stress.Yt)}, "
        f"F2c {stress(abs(deck.materials[n].fail_stress.Yc))}, F6 {stress(deck.materials[n].fail_stress.S)} {stress_unit}" for n in sorted(names))
    add("Strengths (*Fail Stress)", strength_text(reference, ref_materials), strength_text(ours, our_materials), None)

    # grips: couplings by their reference point
    our_couplings = {reference_node(ours, c): c for c in ours.couplings}
    if len(reference.couplings) != len(ours.couplings):
        add("Couplings", f"{len(reference.couplings)}", f"{len(ours.couplings)}", False)
    for coupling in reference.couplings:
        ref_point = reference_node(reference, coupling)
        mine = our_couplings.get(node_map[ref_point])
        driven = {node_map[key] for key in coupled_nodes(reference, coupling)}
        where = reference.assembly_nodes.xyz[reference.assembly_nodes.index_of(ref_point[1])] if ref_point[0] is None else None
        if where is not None:
            x, y = (from_si(float(v), "length", units) for v in where[:2])
            at = f"reference point at ({x:g}, {y:g}) {length_unit}"
        else:
            at = f"reference node {ref_point}"
        if mine is None:
            add(f"Coupling at {at}", f"{coupling.name}: drives {len(driven)} nodes, dofs {sorted(coupling.dofs)}", "no coupling at that point", False)
            continue
        our_driven = set(coupled_nodes(ours, mine))
        add(f"Coupling, {at}", f"{coupling.name}: kinematic, dofs {sorted(coupling.dofs)}, drives {len(driven)} nodes",
            f"{mine.name}: kinematic, dofs {sorted(mine.dofs)}, drives {len(our_driven)} nodes" + ("" if our_driven == driven else
                                                                                                  f"; {len(driven ^ our_driven)} nodes differ"),
            our_driven == driven and coupling.dofs == mine.dofs)

    # every prescribed dof, node by node
    ref_held = {node_map[key]: dofs for key, dofs in _held(reference).items()}
    our_held = _held(ours)
    scale = max([abs(v) for dofs in list(ref_held.values()) + list(our_held.values()) for v in dofs.values()] + [1.0])
    disagree = [key for key in set(ref_held) | set(our_held)
                if set(ref_held.get(key, {})) != set(our_held.get(key, {}))
                or any(abs(ref_held[key][d] - our_held[key][d]) > RELATIVE * scale for d in ref_held.get(key, {}) if d in our_held.get(key, {}))]
    value_text = lambda d, v: f"{from_si(v, 'length', units):g}" if d <= 3 else f"{v:g}"  # noqa: E731  dofs 1 to 3 are lengths, rotations are zero
    describe = lambda held: "; ".join(sorted({f"{len([k for k in held if held[k] == dofs])} node(s): " + ", ".join(  # noqa: E731
        f"{d}={value_text(d, v)}" for d, v in sorted(dofs.items())) for dofs in held.values()}))
    add("Boundary conditions, node by node", describe(ref_held), describe(our_held) + ("" if not disagree else f"; {len(disagree)} nodes differ"), not disagree)

    # concentrated loads
    load_list = lambda deck, mapping: sorted((mapping(key), load.dof, load.value)  # noqa: E731
                                             for step in deck.steps for load in step.cloads for key in resolve_nodes(deck, load.target, load.line))
    ref_loads = load_list(reference, lambda key: node_map[key])
    our_loads = load_list(ours, lambda key: key)
    same_loads = len(ref_loads) == len(our_loads) and all(a[:2] == b[:2] and _close(a[2], b[2]) for a, b in zip(ref_loads, our_loads))
    add("Concentrated loads", f"{len(ref_loads)}", f"{len(our_loads)}", same_loads)

    # steps
    add("Steps", ", ".join(f"{s.name} (linear static)" for s in reference.steps), ", ".join(f"{s.name} (linear static)" for s in ours.steps),
        len(reference.steps) == len(ours.steps))
    return DeckEquivalence(items=tuple(items), node_map=node_map, element_map=element_map, largest_node_offset=largest, tolerance=tolerance, units=units)
