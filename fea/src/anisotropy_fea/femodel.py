"""The complete, solver-neutral finite element model built from a spec and a mesh (ADR-0030).

Everything a deck needs is decided here once, in SI: the material definition, the section with its plies,
the orientation angles, reference points and couplings for coupled grips, every boundary condition, every
load, the probe sets, and the header lines that say where the numbers came from. The writers only format it.

A bending coupon (ADR-0053) rests on two support lines where w is held, is pushed by the loading nose line(s) with a
prescribed w, and is pinned in its plane at the centre node of each support line (both in-plane directions at the left
support, the across direction at the right), which removes the in-plane rigid motions without restraining the coupon's
Poisson contraction or its length change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import __version__ as package_version
from .mesher import Mesh2D, gmsh_open_hole_plate, structured_rectangle
from .spec import (BENDING_KINDS, DEFAULT_NAMES, PLATE_KINDS, CouponSpec, MaterialDefinition, SpecError, coupon_card, edge_regions, full_angles,
                   mesh_counts, node_lines, row_coordinates, spec_material, spec_ply_thickness)

STEP_NAME = "Step-1"
CARD_IN_HEADING = ("Coupon", "Test", "Standard", "Size from", "Team's model", "Test data")  # the rest of the card is in the heading already


@dataclass(frozen=True)
class PlyDefinition:
    thickness_m: float
    angle_deg: float
    material: str
    name: str


@dataclass(frozen=True)
class SectionDefinition:
    elset: str
    layup: str  # the composite layup's name in an Abaqus deck
    plies: tuple[PlyDefinition, ...]  # the full stack, bottom-first
    symmetric: bool
    listed: tuple[PlyDefinition, ...]  # what a deck lists: the lower half when symmetric, else the full stack


@dataclass(frozen=True)
class ReferencePoint:
    set_name: str  # the single-node set that names it in boundary conditions
    label: int  # assembly-level node label
    xy: tuple[float, float]


@dataclass(frozen=True)
class CouplingDefinition:
    name: str
    reference_set: str
    node_set: str  # the coupled nodes


@dataclass(frozen=True)
class BoundaryDefinition:
    target: str  # a node set name
    dof_first: int
    dof_last: int
    value: float = 0.0  # metres for dofs 1 to 3


@dataclass(frozen=True)
class LoadDefinition:
    target: str  # a node set name or Instance.label
    dof: int
    value: float  # newtons


@dataclass(frozen=True)
class PressureDefinition:
    elset: str  # an element set name
    value: float  # Pa, positive against the plate's normal (the Abaqus P label; ADR-0053)


@dataclass(frozen=True)
class FEModel:
    spec: CouponSpec
    mesh: Mesh2D
    material: MaterialDefinition
    section: SectionDefinition
    orientation_angles: tuple[float, ...]  # distinct ply angles, for solvers that orient per ply
    reference_points: tuple[ReferencePoint, ...]
    couplings: tuple[CouplingDefinition, ...]
    boundaries: tuple[BoundaryDefinition, ...]
    loads: tuple[LoadDefinition, ...]
    probe_nodes: dict[str, int]  # probe name -> mesh node index
    probe_elements: dict[str, int]  # probe name -> mesh element index
    heading: tuple[str, ...]
    instance: str  # from the spec's [names], or DEFAULT_NAMES
    part: str
    pins: dict[str, int] = field(default_factory=dict)  # single-node sets that pin a bending coupon in its plane: set name -> mesh node index
    pressures: tuple[PressureDefinition, ...] = ()  # a plate's pressures (ADR-0054)

    @property
    def node_sets(self) -> dict[str, np.ndarray]:
        sets = dict(self.mesh.node_sets)
        if self.plate:
            sets["Face"] = np.arange(self.mesh.node_count)  # the whole face as a node set too, so a support may hold every node
        for name, index in self.pins.items():
            sets[name] = np.array([index])
        for name, index in self.probe_nodes.items():
            sets[f"Probe-{name}"] = np.array([index])
        return sets

    @property
    def plate(self) -> bool:
        return self.spec.kind in PLATE_KINDS

    @property
    def bending(self) -> bool:
        """Whether the model exercises the flat shell: a bending kind, or a plate that is loaded, pushed or held with a value out of its plane."""
        if self.spec.kind in BENDING_KINDS:
            return True
        if self.plate:
            return bool(self.pressures) or any(ld.dof >= 3 for ld in self.loads) or any(b.value != 0.0 and b.dof_first >= 3 for b in self.boundaries)
        return False

    @property
    def support_sets(self) -> tuple[str, ...]:
        """The node sets whose reaction a deck prints and a record compares: the two grips of an in-plane coupon (reference points when
        coupled), the supports and the loading nose(s) of a bending coupon, the supports of a plate in the order the spec lists them."""
        if self.spec.kind in BENDING_KINDS:
            return tuple(name for name in node_lines(self.spec))
        if self.plate:
            return tuple(dict.fromkeys(s.region for s in self.spec.supports))
        return ("RF-Top", "RF-Bottom") if self.couplings else ("Grip-Top", "Grip-Bottom")

    @property
    def nose_sets(self) -> tuple[str, ...]:
        return tuple(name for name in node_lines(self.spec) if name.startswith("Nose")) if self.bending else ()

    @property
    def element_sets(self) -> dict[str, np.ndarray]:
        sets = dict(self.mesh.element_sets)
        if self.plate:
            sets["Face"] = np.arange(self.mesh.element_count)
        for name, index in self.probe_elements.items():
            sets[f"Probe-{name}"] = np.array([index])
        return sets


def mesh_for_spec(spec: CouponSpec) -> Mesh2D:
    """The mesh the spec asks for: a structured rectangle, or Gmsh's O-grid for the open-hole coupon. A bending coupon is a structured
    rectangle with a node row on each support and nose line (`spec.node_lines`)."""
    if not spec.si:
        raise SpecError("mesh_for_spec needs the spec in SI (load_spec)")
    g = spec.geometry
    if spec.kind in BENDING_KINDS:
        nx, ny = mesh_counts(spec)
        return structured_rectangle(g.width, g.length, nx, ny, spec.mesh.element_order, node_rows=node_lines(spec), ys=row_coordinates(spec))
    bands = {}
    node_bands = {}
    boxes = {r.name: (r.x0, r.x1, r.y0, r.y1) for r in spec.regions} or None
    if g.tab_length:
        bands = {"Tab-Bottom": (0.0, g.tab_length), "Gauge": (g.tab_length, g.length - g.tab_length), "Tab-Top": (g.length - g.tab_length, g.length)}
        if spec.grips is not None and spec.grips.region == "tabs":
            # the whole tab is gripped: every node within tab_length of an end belongs to that grip set (as the team's decks do)
            node_bands = {"Grip-Bottom": (0.0, g.tab_length), "Grip-Top": (g.length - g.tab_length, g.length)}
        if spec.kind in PLATE_KINDS:  # a plate's tabs are regions: their nodes and their elements
            node_bands = {"Tab-Bottom": (0.0, g.tab_length), "Tab-Top": (g.length - g.tab_length, g.length)}
    if spec.mesh.mesher == "gmsh":
        hole = spec.mesh.hole
        return plate_sets(gmsh_open_hole_plate(g.width, g.length, g.hole_diameter, spec.mesh.element_size, hole.circumferential, hole.radial_layers,
                                               hole.ring_ratio, hole.growth, order=spec.mesh.element_order, tab_length=g.tab_length or 0.0,
                                               node_rows=node_lines(spec), element_bands=bands, node_bands=node_bands, boxes=boxes), spec)
    nx, ny = mesh_counts(spec)
    return plate_sets(structured_rectangle(g.width, g.length, nx, ny, spec.mesh.element_order, node_rows=node_lines(spec), element_bands=bands,
                                           node_bands=node_bands, ys=row_coordinates(spec), boxes=boxes), spec)


def plate_sets(mesh: Mesh2D, spec: CouponSpec) -> Mesh2D:
    """A plate names its end rows Edge-Bottom and Edge-Top (ADR-0054), beside the mesher's Grip-Bottom and Grip-Top; a coupon's mesh is unchanged."""
    if spec.kind in PLATE_KINDS:
        mesh.node_sets["Edge-Bottom"] = mesh.node_sets["Grip-Bottom"]
        mesh.node_sets["Edge-Top"] = mesh.node_sets["Grip-Top"]
    return mesh


def build_model(spec: CouponSpec, mesh: Mesh2D | None = None) -> FEModel:
    if not spec.si:
        raise SpecError("build_model needs the spec in SI (load_spec)")
    mesh = mesh if mesh is not None else mesh_for_spec(spec)
    material = spec_material(spec)
    thickness = spec_ply_thickness(spec)
    angles = full_angles(spec)
    names = spec.names.model_dump() if spec.names is not None else DEFAULT_NAMES
    plies = tuple(PlyDefinition(thickness, angle, material.name, f"Ply-{k}") for k, angle in enumerate(angles, start=1))
    listed = plies[: len(spec.layup.angles)] if spec.layup.symmetric else plies
    section = SectionDefinition(elset=names["section_set"], layup=names["layup"], plies=plies, symmetric=spec.layup.symmetric, listed=listed)
    orientation_angles = tuple(sorted(set(angles)))
    probe_nodes = {name: mesh.nearest_node(point) for name, point in spec.probes.nodes.items()}
    probe_elements = {name: mesh.nearest_element(point) for name, point in spec.probes.elements.items()}

    g, loading = spec.geometry, spec.loading
    reference_points: tuple[ReferencePoint, ...] = ()
    couplings: tuple[CouplingDefinition, ...] = ()
    boundaries: list[BoundaryDefinition] = []
    loads: list[LoadDefinition] = []
    pressures: list[PressureDefinition] = []
    pins: dict[str, int] = {}
    if spec.kind in PLATE_KINDS:
        edges = edge_regions(spec)
        available = set(mesh.node_sets) | {"Face"}
        for support in spec.supports:
            if support.region not in available or (support.region != "Face" and mesh.node_sets[support.region].size == 0):
                raise SpecError(f"region {support.region!r} holds no node on this mesh")
            boundaries += [BoundaryDefinition(support.region, dof, dof, support.value) for dof in sorted(support.dofs)]
        for load in spec.loads:
            if load.pressure is not None:
                pressures.append(PressureDefinition(load.region, load.pressure))
            elif load.region in edges:
                loads += consistent_edge_loads(mesh, load.region, load.dof, load.total, instance=names["instance"])
            else:
                elements = np.arange(mesh.element_count) if load.region == "Face" else mesh.element_sets[load.region]
                loads += consistent_area_loads(mesh, elements, load.dof, load.total, instance=names["instance"])
    elif spec.kind in BENDING_KINDS:
        lines = node_lines(spec)
        pins = {"Pin-Left": mesh.nearest_node((g.width / 2, lines["Support-Left"])), "Pin-Right": mesh.nearest_node((g.width / 2, lines["Support-Right"]))}
        boundaries += [BoundaryDefinition("Support-Left", 3, 3), BoundaryDefinition("Support-Right", 3, 3),
                       BoundaryDefinition("Pin-Left", 1, 2), BoundaryDefinition("Pin-Right", 1, 1)]
        boundaries += [BoundaryDefinition(name, 3, 3, loading.value) for name in lines if name.startswith("Nose")]
    elif spec.grips.kind == "coupling":
        reference_points = (ReferencePoint("RF-Bottom", 1, (g.width / 2, 0.0)), ReferencePoint("RF-Top", 2, (g.width / 2, g.length)))
        couplings = (CouplingDefinition("Grip-Bottom", "RF-Bottom", "Grip-Bottom"), CouplingDefinition("Grip-Top", "RF-Top", "Grip-Top"))
        boundaries.append(BoundaryDefinition("RF-Bottom", 1, 6))
        boundaries += [BoundaryDefinition("RF-Top", 1, 1), BoundaryDefinition("RF-Top", 3, 6)]
        if loading.control == "displacement":
            boundaries.append(BoundaryDefinition("RF-Top", 2, 2, loading.value))
        else:
            loads.append(LoadDefinition("RF-Top", 2, loading.value))
    else:
        boundaries.append(BoundaryDefinition("Grip-Bottom", 1, 6))
        boundaries += [BoundaryDefinition("Grip-Top", 1, 1), BoundaryDefinition("Grip-Top", 3, 6)]
        if loading.control == "displacement":
            boundaries.append(BoundaryDefinition("Grip-Top", 2, 2, loading.value))
        else:
            loads += consistent_edge_loads(mesh, "Grip-Top", 2, loading.value, instance=names["instance"])

    heading = (
        f"Generated by anisotropy_fea {package_version} from spec {Path(spec.source_path).name if spec.source_path else '<text>'} "
        f"(sha256 {spec.source_sha256[:16]}); do not edit by hand.",
        f"{spec.title}",
        *[f"{label}: {value}" for label, value in coupon_card(spec) if label in CARD_IN_HEADING],
        f"kind {spec.kind}; length {g.length:g} m, width {g.width:g} m" + (f", tabs {g.tab_length:g} m" if g.tab_length else "")
        + (f", central hole of diameter {g.hole_diameter:g} m" if g.hole_diameter else ""),
        f"mesh {mesh.mesher}, {mesh.element_count} elements of order {mesh.order}, {mesh.node_count} nodes",
        f"layup bottom-first {angles}" + (" (listed as the symmetric half)" if spec.layup.symmetric else "") + f", ply thickness {thickness:g} m",
        f"material {material.name}: {material.source}; rights class {material.rights}",
        *[f"  {line}" for line in material.citation_lines],
        f"out-of-plane constants: G13 {material.G13:g}, G23 {material.G23:g}, E3 {material.E3:g}, nu13 {material.nu13:g}, nu23 {material.nu23:g} (SI; "
        + ("transverse isotropy stated in the spec" if spec.material.transverse.transverse_isotropy else "given in the spec") + ")"
        + ("; nu13 = nu23 = 0 written for plane stress, as Abaqus LAMINA and our kernel assume (plane_stress = true in the spec)" if material.plane_stress else ""),
        (plate_words(spec) if spec.kind in PLATE_KINDS else
         f"supports at y = {g.overhang:g} and {g.length - g.overhang:g} m (w held along the row; the centre node of each row pins the in-plane motion), "
         f"loading nose{'s' if spec.kind == 'four_point_bending' else ''} at y = "
         + ", ".join(f"{y:g}" for name, y in node_lines(spec).items() if name.startswith("Nose")) + f" m moved {loading.value:g} m along z"
         if spec.kind in BENDING_KINDS else
         f"grips {spec.grips.kind} on the {'end node rows' if spec.grips.region == 'line' else 'whole tab regions'}; "
         f"loading {loading.control} {loading.value:g} " + ("m" if loading.control == "displacement" else "N")),
        f"units of this deck: {spec.units}",
    )
    return FEModel(spec=spec, mesh=mesh, material=material, section=section, orientation_angles=orientation_angles,
                   reference_points=reference_points, couplings=couplings, boundaries=tuple(boundaries), loads=tuple(loads),
                   probe_nodes=probe_nodes, probe_elements=probe_elements, heading=heading, instance=names["instance"], part=names["part"], pins=pins,
                   pressures=tuple(pressures))


def plate_words(spec: CouponSpec) -> str:
    """A plate's supports and loads in one line, SI, for a deck's heading."""
    held = "; ".join(f"{s.region} dofs {','.join(str(d) for d in s.dofs)}" + (f" = {s.value:g}" if s.value else "") for s in spec.supports)
    loads = "; ".join(f"{ld.region} " + (f"pressure {ld.pressure:g} Pa" if ld.pressure is not None else f"dof {ld.dof} total {ld.total:g} N") for ld in spec.loads)
    return f"plate: supports {held}" + (f"; loads {loads}" if loads else "")


def consistent_area_loads(mesh: Mesh2D, elements: np.ndarray, dof: int, total: float, instance: str) -> list[LoadDefinition]:
    """A uniform traction over the elements named, as consistent nodal loads summing to `total`: each four-node element gives a quarter of its
    area to each corner node (the bilinear element's consistent load for a uniform traction), and eight-node elements the serendipity weights
    (-1/12 at the corners, 1/3 at the midsides); the weights are scaled so their sum is the total force."""
    weights: dict[int, float] = {}
    for e in np.asarray(elements, dtype=int).tolist():
        nodes = mesh.corners[e]
        p = mesh.xy[nodes]
        area = 0.5 * abs(sum(p[i, 0] * p[(i + 1) % 4, 1] - p[(i + 1) % 4, 0] * p[i, 1] for i in range(4)))
        if mesh.midside is None:
            for node in nodes.tolist():
                weights[node] = weights.get(node, 0.0) + 0.25 * area
        else:
            for node in nodes.tolist():
                weights[node] = weights.get(node, 0.0) - area / 12.0
            for node in mesh.midside[e].tolist():
                weights[node] = weights.get(node, 0.0) + area / 3.0
    if not weights:
        raise SpecError("the region holds no element to load")
    scale = total / sum(weights.values())
    return [LoadDefinition(f"{instance}.{node + 1}", dof, w * scale) for node, w in sorted(weights.items())]


def consistent_edge_loads(mesh: Mesh2D, node_set: str, dof: int, total: float, instance: str) -> list[LoadDefinition]:
    """A uniform traction along the straight edge formed by a node set, as consistent nodal loads summing to `total`.

    Each element edge of length a carries weights [1/2, 1/2] on its corner nodes (4-node elements) or
    [1/6, 2/3, 1/6] on corner, midside, corner (8-node elements). Weights are accumulated per node and scaled so
    their sum is the total force, which also makes the loads exact for any element lengths.
    """
    members = set(mesh.node_sets[node_set].tolist())
    weights: dict[int, float] = {}
    for e, nodes in enumerate(mesh.corners):
        for k in range(4):
            a, b = int(nodes[k]), int(nodes[(k + 1) % 4])
            if a in members and b in members:
                length = float(np.linalg.norm(mesh.xy[a] - mesh.xy[b]))
                if mesh.midside is None:
                    for node, w in ((a, 0.5), (b, 0.5)):
                        weights[node] = weights.get(node, 0.0) + w * length
                else:
                    m = int(mesh.midside[e, k])
                    for node, w in ((a, 1.0 / 6.0), (m, 2.0 / 3.0), (b, 1.0 / 6.0)):
                        weights[node] = weights.get(node, 0.0) + w * length
    if not weights:
        raise SpecError(f"node set {node_set!r} forms no element edge to load")
    scale = total / sum(weights.values())
    return [LoadDefinition(f"{instance}.{node + 1}", dof, w * scale) for node, w in sorted(weights.items())]
