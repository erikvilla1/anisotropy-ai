"""A model brought in as an Abaqus input deck (ADR-0105): what the reader took from it, the model as the viewer draws it, and our
kernel's answer on it.

The deck is read by `abaqus_reader` and nothing else: the subset of `fea/README.md`, and anything outside it refused with its line
(ADR-0003). Nothing is repaired, guessed or filled in. The reading says what was taken and what was skipped; the preview is the deck's
own mesh, sets, supports and loads in the shape `preview.preview_data` gives a model of ours, so the page draws both the same way; the
fields and the answer are `fields.field_data` on the deck as it stands. A deck carries no units, so the caller states the system it is
written in, one of the four a coupon may be stated in, and the results come back in it.
"""

from __future__ import annotations

import dataclasses
import re
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from .abaqus_reader import HANDLERS, IGNORED_KEYWORDS, UNUSED_KEYWORDS, parse_deck, tokenize
from .explain import explanation
from .fields import field_data
from .kernel import solve_deck
from .mesh import KernelError, Mesh, mesh_from_deck
from .model import (
    SUPPORTED_ELEMENT_TYPES,
    Deck,
    DeckError,
    all_boundaries,
    coupled_nodes,
    expanded_layers,
    fibre_angles,
    reference_node,
    resolve_elements,
    resolve_nodes,
    to_si,
    validate_deck,
)
from .preview import DOF_WORDS
from .shell import needs_shell
from .units import UNIT_LABEL, from_si, unit_factors

KIND = "imported"  # the preview's `coupon.kind` for a model that came in as a deck
TEST = "imported model"
BY_ELEMENT = "Pressure by element"  # the preview's name for the elements a deck loads one by one
# A load along an edge, by its label, as the preview names it: per length of edge. A positive EDNOR pushes into the plate.
EDGE_WORDS = {"EDNOR": "edge load, normal to the edge,", "EDSHR": "edge load, along the edge,", "EDTRA": "edge load, across the plate,"}
MAX_BYTES = 20_000_000  # a deck above this is refused before it is read: the kernel's meshes are far below it
_LINE = re.compile(r"\bline (\d+)\b")


def plain(message: str) -> str:
    """A reader's or the kernel's message as the import shows it: without the pointer to this repository's own files and names."""
    return message.replace("; see fea/README.md for the supported subset", "").replace("anisotropy_fea 0.1", "this version")


class ImportRefused(ValueError):
    """The file cannot be taken as it stands; the message says why, and `line` where when the reader named one. `unread` lists every
    kind of thing the file holds that is not read, when the survey found any."""

    def __init__(self, message: str, line: int | None = None, unread: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.line = line
        self.unread = unread or []


# What a model may hold that is not read, by keyword, in the words an engineer has for it. Several keywords may be one thing ("contact").
# A keyword that is not here is named as the file writes it.
UNREAD_WORDS = {
    "contact": "contact", "contact pair": "contact", "contact inclusions": "contact", "contact exclusions": "contact",
    "contact property assignment": "contact", "surface interaction": "contact", "surface behavior": "contact", "friction": "contact",
    "contact controls": "contact", "contact initialization data": "contact", "contact initialization assignment": "contact",
    "contact formulation": "contact", "contact stabilization": "contact", "clearance": "contact",
    "tie": "a tie between surfaces", "mpc": "multi-point constraints", "equation": "constraint equations", "rigid body": "a rigid body",
    "distributing": "a distributing coupling", "distributing coupling": "a distributing coupling", "shell to solid coupling": "a shell-to-solid coupling",
    "embedded element": "embedded elements", "connector section": "connectors", "connector behavior": "connectors", "fastener": "fasteners",
    "spring": "springs", "dashpot": "dashpots", "mass": "point masses", "rotary inertia": "point masses",
    "solid section": "solid or plane-element sections", "beam section": "beams", "beam general section": "beams", "membrane section": "membranes",
    "shell general section": "a shell stated by its stiffness matrix", "cohesive section": "cohesive elements", "rigid surface": "a rigid surface",
    "transverse shear": "a stated transverse shear stiffness", "transverse shear stiffness": "a stated transverse shear stiffness",
    "section controls": "element controls (hourglass or distortion settings)", "hourglass stiffness": "element controls (hourglass or distortion settings)",
    "nodal thickness": "a thickness stated node by node", "distribution": "values that vary over the mesh (a distribution)",
    "distribution table": "values that vary over the mesh (a distribution)", "rebar layer": "rebar layers",
    "fail strain": "strain limits (failure is judged from the stress limits)", "plastic": "plasticity", "hyperelastic": "a hyperelastic material", "viscoelastic": "a viscoelastic material", "creep": "creep",
    "damage initiation": "damage (Hashin or another damage model)", "damage evolution": "damage (Hashin or another damage model)",
    "damage stabilization": "damage (Hashin or another damage model)", "user material": "a user material", "depvar": "a user material",
    "dflux": "heat loads", "dsflux": "heat loads", "cflux": "heat loads", "film": "heat loads", "sfilm": "heat loads",
    "temperature": "a temperature field", "initial conditions": "initial conditions", "field": "field variables",
    "amplitude": "a load that follows an amplitude curve", "buckle": "a buckling step", "frequency": "a frequency step", "dynamic": "a dynamic step",
    "heat transfer": "a heat transfer step", "coupled temperature-displacement": "a heat transfer step", "visco": "a time-dependent material step",
    "steady state dynamics": "a dynamic step", "modal dynamic": "a dynamic step", "complex frequency": "a frequency step",
    "include": "another file brought in by name", "parameter": "values computed by parameters", "system": "a local coordinate system for nodes",
    "transform": "a local coordinate system for nodes", "submodel": "a submodel", "import": "results imported from another analysis",
    "controls": "solution controls", "adaptive mesh": "adaptive meshing", "sradiate": "heat loads", "inertia relief": "inertia relief",
    "base motion": "a dynamic step", "periodic": "periodic constraints", "pre-tension section": "bolt pretension", "kinematic coupling": "a kinematic coupling of the older form",
}

# An element type that is not read, by how its name starts (longest first where two fit), in an engineer's words.
ELEMENT_WORDS = (
    ("SC", "continuum shell elements"), ("STRI", "triangular shell elements"), ("S3", "triangular shell elements"), ("S8", "second-order shell elements"),
    ("S9", "second-order shell elements"), ("SAX", "axisymmetric shell elements"), ("C3D", "solid elements"), ("CPS", "plane-stress elements"),
    ("CPE", "plane-strain elements"), ("CAX", "axisymmetric elements"), ("M3D", "membrane elements"), ("R3D", "rigid elements"), ("COH", "cohesive elements"),
    ("B2", "beam elements"), ("B3", "beam elements"), ("PIPE", "beam elements"), ("T2", "truss elements"), ("T3", "truss elements"),
    ("SPRING", "springs"), ("DASHPOT", "dashpots"), ("MASS", "point masses"), ("CONN", "connectors"), ("DC", "heat transfer elements"), ("DS", "heat transfer elements"),
)


def unread(text: str) -> list[dict[str, Any]]:
    """Every kind of thing a file holds that is not read, found before the reader stops at the first: keywords with no reading, element
    types the kernels do not solve, a second step and large displacements. One entry per kind, in the order the
    file meets them: `what` in an engineer's words, `keyword` as the file writes its first, and the `lines`. What a keyword's own
    parameters or data hold (an instance turned out of the plane, a load label) is still the reader's to refuse, one at a time."""
    try:
        blocks = tokenize(text)
    except DeckError:
        return []  # the reader says what is wrong with the file's form
    found: dict[str, dict[str, Any]] = {}

    def note(what: str, keyword: str, line: int) -> None:
        found.setdefault(what, {"what": what, "keyword": keyword, "lines": []})["lines"].append(line)

    steps = 0
    for block in blocks:
        written = "*" + block.name.title()
        if block.name == "element":
            kind = (block.params.get("type") or "").upper()
            if kind and kind not in SUPPORTED_ELEMENT_TYPES:
                note(next((words for start, words in ELEMENT_WORDS if kind.startswith(start)), "elements of another type"), kind, block.line)
        elif block.name == "step":
            steps += 1
            if steps > 1:
                note("more than one step", written, block.line)
            if (block.params.get("nlgeom") or "NO").upper() == "YES":
                note("large displacements", written + ", nlgeom=YES", block.line)
            if "perturbation" in block.params:
                note("a perturbation step", written + ", perturbation", block.line)
        elif block.name not in HANDLERS and block.name not in IGNORED_KEYWORDS and block.name not in UNUSED_KEYWORDS:
            note(UNREAD_WORDS.get(block.name, f"the keyword {written}"), written, block.line)
    return list(found.values())


def unread_message(found: list[dict[str, Any]]) -> str:
    """The survey in one sentence. One kind is said the way the reader says a refusal, its line first; several are listed, each once,
    with the keyword the file writes and where it first is. Element types add what is read in their place."""
    def keyword(entry: dict[str, Any]) -> str:
        return "" if entry["keyword"] in entry["what"] else f"{entry['keyword']}, "

    def times(entry: dict[str, Any]) -> str:
        return f", {len(entry['lines'])} times" if len(entry["lines"]) > 1 else ""

    shells = ". It reads flat four-node shells (" + ", ".join(SUPPORTED_ELEMENT_TYPES) + ")" if any(e["keyword"].isalnum() for e in found) else ""
    if len(found) == 1:
        entry = found[0]
        named = keyword(entry).rstrip(", ")
        return f"line {entry['lines'][0]}: this version does not read {entry['what']}" + (f" ({named}{times(entry)})" if named or times(entry) else "") + shells
    kinds = "; ".join(f"{entry['what']} ({keyword(entry)}line {entry['lines'][0]}{times(entry)})" for entry in found)
    return f"this file holds {len(found)} things that this version does not read: {kinds}" + shells


def decoded(content: bytes) -> str:
    """The file's text: UTF-8, or the single-byte page Abaqus/CAE writes a heading in on Windows. A file with a NUL byte is not text."""
    if len(content) > MAX_BYTES:
        raise ImportRefused(f"the file is {len(content)} bytes; a model of up to {MAX_BYTES} bytes is read")
    if b"\x00" in content:
        raise ImportRefused("the file is not text: an Abaqus input deck (.inp) is read, not a .cae or .odb file")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def read_text(text: str, units: str, name: str | None = None) -> tuple[Deck, list[str]]:
    """The deck in SI, with the reader's notes, and the warnings the unit statement raised (a modulus far from any material's usually
    means the wrong system). Refuses, with the line, what the reader refuses."""
    unit_factors(units)  # refuses a system no coupon is stated in, before anything is read
    outside = unread(text)
    if outside:  # everything at once: an engineer deciding whether a model can be brought in should not learn its limits one upload at a time
        raise ImportRefused(unread_message(outside), outside[0]["lines"][0], outside)
    try:
        deck = parse_deck(text, source_path=name)
        notes = validate_deck(deck)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            converted = to_si(deck, units, any_system=True)
    except DeckError as exc:
        found = _LINE.search(str(exc))
        raise ImportRefused(plain(str(exc)), int(found.group(1)) if found else None) from exc
    return dataclasses.replace(converted, notes=notes), [str(w.message) for w in caught]


def layup_words(deck: Deck) -> str:
    """The first section's stacking sequence as the deck states it, for example [45/0/-45/90]s; "isotropic" for one isotropic layer."""
    sections = [section for part in deck.parts.values() for section in part.sections]
    if not sections:
        return ""
    section = sections[0]
    material = deck.materials.get(section.layers[0].material)
    if len(section.layers) == 1 and material is not None and material.elastic is not None and material.elastic.kind == "ISOTROPIC":
        return "isotropic"
    return "[" + "/".join(f"{layer.angle_deg:g}" for layer in section.layers) + "]" + ("s" if section.symmetric else "")


def reading(deck: Deck, units: str, warned: list[str]) -> dict[str, Any]:
    """What the reader took from the deck, in counts and names, and what it skipped: the import's own report. Lengths in `units`."""
    length = lambda v: from_si(float(v), "length", units)  # noqa: E731
    types: dict[str, int] = {}
    for part in deck.parts.values():
        if part.elements is not None:
            types[part.elements.element_type] = types.get(part.elements.element_type, 0) + len(part.elements) * sum(i.part == part.name for i in deck.instances.values())
    sections = []
    for part in deck.parts.values():
        for section in part.sections:
            plies = expanded_layers(section)
            sections.append({"element_set": section.elset, "plies": len(plies), "symmetric": section.symmetric,
                             "thickness": length(sum(layer.thickness for layer in plies)), "materials": sorted({layer.material for layer in plies}),
                             "rotation_deg": float(section.rotation_deg)})
    materials = [{"name": m.name, "kind": None if m.elastic is None else m.elastic.kind.lower(), "strengths": m.fail_stress is not None}
                 for m in deck.materials.values()]
    steps = list(deck.steps)
    return {
        "heading": deck.heading.strip(), "sha256": deck.source_sha256, "units": units, "unit_labels": UNIT_LABEL[units],
        "parts": len(deck.parts), "instances": len(deck.instances),
        "moved": [{"instance": i.name, "by": [length(v) for v in i.translation[:2]], "turned_deg": float(i.rotation_deg), "about": [length(v) for v in i.rotation_about]}
                  for i in deck.instances.values() if any(i.translation) or i.rotation_deg],
        "nodes": sum(len(deck.parts[i.part].nodes) for i in deck.instances.values()), "reference_nodes": len(deck.assembly_nodes),
        "elements": sum(types.values()), "element_types": types,
        "node_sets": len(deck.nsets), "element_sets": len(deck.elsets), "couplings": len(deck.couplings),
        "sections": sections, "layup": layup_words(deck), "materials": materials,
        "step": steps[0].name if steps else None,
        "boundaries": len(all_boundaries(deck)),
        "concentrated_loads": sum(load.edge is None for step in steps for load in step.cloads), "pressures": sum(len(step.dloads) for step in steps),
        "edge_loads": sum(len(step.edge_loads) for step in steps),
        "skipped": list(deck.ignored_keywords), "notes": list(deck.notes), "warnings": warned,
    }


def _target_name(target: Any) -> str:
    """A boundary's or a load's target as the deck names it: a set, or one node or element as `Instance.label`."""
    if isinstance(target, str):
        return target
    instance, label = target
    return f"{instance}.{label}" if instance is not None else f"Assembly.{label}"


def _through(deck: Deck, mesh: Mesh, target: Any, line: int) -> tuple[str, str | None, list[int]]:
    """The nodes a boundary or a concentrated load acts on, by mesh index, under the name the page keys them by: the coupled surface's
    nodes when the target is a coupling's reference node (and the target's name as what it acts through), the target's own otherwise."""
    name = _target_name(target)
    keys = resolve_nodes(deck, target, line)
    for coupling in deck.couplings:
        if len(keys) == 1 and keys[0] == reference_node(deck, coupling):
            return coupling.surface, name, [mesh.node(key) for key in coupled_nodes(deck, coupling)]
    return name, None, [mesh.node(key) for key in keys]


def model_preview(deck: Deck, mesh: Mesh, units: str, name: str, criteria: list[str]) -> dict[str, Any]:
    """The deck as the viewer draws a model before its results (the shape of `preview.preview_data`): the mesh, every set by mesh index,
    what is held, what is loaded, the plies and the first section's material. Values in `units`."""
    length = lambda v: from_si(float(v), "length", units)  # noqa: E731
    stress = lambda v: None if v is None else from_si(float(v), "stress", units)  # noqa: E731
    lab = UNIT_LABEL[units]
    instance_rows = [k for k in range(mesh.node_count) if mesh.node_keys[k][0] is not None]
    node_sets: dict[str, list[int]] = {set_name: [mesh.node(key) for key in keys] for set_name, keys in deck.nsets.items()}
    element_sets: dict[str, list[int]] = {set_name: [mesh.element(key) for key in keys] for set_name, keys in deck.elsets.items()}
    held: list[dict[str, Any]] = []
    loads: list[dict[str, Any]] = []
    pressures: list[tuple[str, float, tuple[float, float] | None, list[int]]] = []
    for boundary in all_boundaries(deck):
        set_name, through, nodes = _through(deck, mesh, boundary.target, boundary.line)
        node_sets.setdefault(set_name, nodes)
        dofs = list(range(boundary.dof_first, boundary.dof_last + 1))
        if boundary.value == 0.0:
            same = next((h for h in held if h["set"] == set_name and h["through"] == through), None)
            if same is None:  # one entry per held set: a deck states one line per degree of freedom
                held.append({"set": set_name, "through": through, "dofs": dofs, "directions": [], "nodes": len(nodes)})
            else:
                same["dofs"] = sorted(set(same["dofs"]) | set(dofs))
            continue
        dof = boundary.dof_first
        value = length(boundary.value) if dof <= 3 else float(boundary.value)
        loads.append({"set": set_name, "through": through, "control": "displacement", "dof": dof, "direction": ("+" if value >= 0 else "-") + DOF_WORDS[dof],
                      "value": value, "unit": lab["length"] if dof <= 3 else lab["rotation"], "nodes": len(nodes)})
    for step in deck.steps:
        for edge in step.edge_loads:  # a load along an edge is one load: its nodal forces are not listed one by one
            forces = [load for load in step.cloads if load.edge == edge.tag]
            nodes = sorted({mesh.node(load.target) for load in forces})
            total = np.zeros(3)
            for load in forces:
                total[load.dof - 1] += load.value
            dof = int(np.argmax(np.abs(total))) + 1  # the axis the whole edge is pushed along, for the arrow
            set_name = edge.surface if node_sets.setdefault(edge.surface, nodes) == nodes else f"{edge.surface} (edge)"
            node_sets.setdefault(set_name, nodes)
            loads.append({"set": set_name, "through": None, "control": EDGE_WORDS[edge.label], "dof": dof, "direction": ("+" if total[dof - 1] >= 0 else "-") + DOF_WORDS[dof],
                          "value": from_si(edge.value, "force", units) * unit_factors(units)["length"], "unit": lab["force"] + "/" + lab["length"], "nodes": len(nodes),
                          "total_force": from_si(float(np.linalg.norm(total)), "force", units)})
        for load in step.cloads:
            if load.edge is not None:
                continue
            set_name, through, nodes = _through(deck, mesh, load.target, load.line)
            node_sets.setdefault(set_name, nodes)
            count = len(resolve_nodes(deck, load.target, load.line))  # the deck's value is per node of its target
            kind, unit = ("force", lab["force"]) if load.dof <= 3 else ("moment", lab["force"] + "·" + lab["length"])
            value = from_si(load.value * count, "force", units) * (1.0 if load.dof <= 3 else 1.0 / unit_factors(units)["length"])
            loads.append({"set": set_name, "through": through, "control": kind, "dof": load.dof, "direction": ("+" if value >= 0 else "-") + DOF_WORDS[load.dof],
                          "value": value, "unit": unit, "nodes": len(nodes)})
        single: list[tuple[float, int]] = []  # a deck may state a pressure element by element: those are one load, with its range
        for dload in step.dloads:
            elements = [mesh.element(key) for key in resolve_elements(deck, dload.target, dload.line)]
            if isinstance(dload.target, str):
                pressures.append((dload.target, dload.value, None, elements))
            else:
                single.extend((dload.value, e) for e in elements)
        if single:
            values = [value for value, _ in single]
            pressures.append((BY_ELEMENT, max(values, key=abs), None if min(values) == max(values) else (min(values), max(values)), [e for _, e in single]))
    for set_name, value, spread, elements in pressures:
        element_sets.setdefault(set_name, elements)
        nodes = np.unique(mesh.connectivity[elements, :4]).tolist()
        load = {"set": set_name, "through": None, "control": "pressure", "dof": 3, "direction": ("-" if value > 0 else "+") + "z",
                "value": from_si(value, "stress", units), "unit": lab["stress"], "nodes": len(nodes)}
        if spread is not None:  # `value` is then the largest in magnitude
            load["range"] = [from_si(spread[0], "stress", units), from_si(spread[1], "stress", units)]
        loads.append(load)
    for entry in held:
        entry["directions"] = [DOF_WORDS[d] for d in entry["dofs"]]
    sections = [section for part in deck.parts.values() for section in part.sections]
    plies: list[dict[str, Any]] = []
    thickness_m = 0.0
    material: dict[str, Any] | None = None
    if sections:
        section = sections[0]
        layers = expanded_layers(section)
        thickness_m = sum(layer.thickness for layer in layers)
        z = -thickness_m / 2
        for k, (layer, angle) in enumerate(zip(layers, fibre_angles(section), strict=True), start=1):
            plies.append({"index": k, "angle": float(angle), "thickness": length(layer.thickness), "z_bottom": length(z), "z_top": length(z + layer.thickness),
                          "material": layer.material})
            z += layer.thickness
        first = deck.materials.get(layers[0].material)
        if first is not None and first.elastic is not None:
            e, f = first.elastic, first.fail_stress
            strengths = None if f is None else {"F1t": stress(f.Xt), "F1c": stress(f.Xc), "F2t": stress(f.Yt), "F2c": stress(f.Yc), "F6": stress(f.S)}
            material = {"name": first.name, "source": f"as stated in {name}", "rights": "user-supplied", "E1": stress(e.E1), "E2": stress(e.E2),
                        "G12": stress(e.G12), "nu12": float(e.nu12), "G13": stress(e.G13 if e.G13 is not None else e.G12),
                        "G23": stress(e.G23 if e.G23 is not None else e.G12), "strengths": strengths, "f12_star": None if f is None else f.f_star,
                        "criteria": list(criteria), "citation_lines": [], "ply_thickness": length(layers[0].thickness), "plies": len(layers)}
    xy = mesh.xy[instance_rows] if instance_rows else mesh.xy
    span = xy.max(axis=0) - xy.min(axis=0)
    layup = layup_words(deck)
    card = [["Model", name], ["Layup", layup], ["Elements", str(mesh.element_count)], ["Units", f"{lab['length']}, {lab['stress']}, {lab['force']}"]]
    return {
        "units": units, "labels": lab,
        "coupon": {"designation": None, "title": deck.heading.strip() or name, "kind": KIND, "test": TEST, "card": card, "layup": layup},
        "geometry": {"length": length(span[1]), "width": length(span[0]), "tab_length": 0.0, "hole_diameter": None, "thickness": length(thickness_m)},
        "mesh": {"nodes": [[length(x), length(y)] for x, y in mesh.xy], "quads": mesh.connectivity[:, :4].tolist(), "node_sets": node_sets,
                 "element_sets": element_sets, "order": 1, "mesher": "imported", "node_count": mesh.node_count, "element_count": mesh.element_count},
        "held": held, "loaded": loads[0] if loads else None, "loads": loads, "regions": None,
        "plies": plies, "material": material,
        "probes": {"nodes": {}, "elements": {}},
    }


def import_model(content: bytes, name: str, units: str) -> dict[str, Any]:
    """One imported file, start to end: `state` is `refused` (the reader or the unit statement refused it; `problem` says why and on
    which line), `read` (taken, but our kernel could not solve it as it stands; `problem` says why) or `solved`. A taken model has its
    `reading` and `preview`; a solved one its `fields` (with the answer in its summary) and its `explanation` too."""
    name = Path(name).name or "model.inp"
    try:
        deck, warned = read_text(decoded(content), units, name)
    except ImportRefused as exc:
        return {"state": "refused", "name": name, "units": units, "problem": {"message": str(exc), "line": exc.line, "unread": exc.unread}}
    except ValueError as exc:  # the unit statement
        return {"state": "refused", "name": name, "units": units, "problem": {"message": str(exc), "line": None, "unread": []}}
    result: dict[str, Any] = {"state": "read", "name": name, "units": units, "problem": None, "reading": reading(deck, units, warned)}
    try:
        solution = solve_deck(deck)
        coupon = {"designation": Path(name).stem, "title": deck.heading.strip() or name, "kind": KIND, "test": TEST, "layup": layup_words(deck)}
        data = field_data(deck, solution, units, coupon=coupon)
    except (KernelError, DeckError) as exc:
        result["problem"] = {"message": plain(str(exc)), "line": int(found.group(1)) if (found := _LINE.search(str(exc))) else None, "unread": []}
        try:
            result["preview"] = model_preview(deck, mesh_from_deck(deck, shell=needs_shell(deck)), units, name, [])
        except (KernelError, DeckError):
            result["preview"] = None
        return result
    result["state"] = "solved"
    result["preview"] = model_preview(deck, solution.mesh, units, name, list(data["summary"]["fpf"]))
    result["fields"] = data
    result["explanation"] = explanation(data["summary"], coupon, units, data["labels"])
    return result
