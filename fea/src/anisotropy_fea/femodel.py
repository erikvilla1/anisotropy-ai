"""The complete, solver-neutral finite element model built from a spec and a mesh (ADR-0030).

Everything a deck needs is decided here once, in SI: the material definition, the section with its plies,
the orientation angles, reference points and couplings for coupled grips, every boundary condition, every
load, the probe sets, and the header lines that say where the numbers came from. The writers only format it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import __version__ as package_version
from .mesher import Mesh2D, gmsh_open_hole_plate, structured_rectangle
from .spec import BENDING_KINDS, CouponSpec, MaterialDefinition, SpecError, full_angles, mesh_counts, node_lines, spec_material, spec_ply_thickness

STEP_NAME = "Step-1"
ALL_ELEMENTS = "All"


@dataclass(frozen=True)
class PlyDefinition:
    thickness_m: float
    angle_deg: float
    material: str
    name: str


@dataclass(frozen=True)
class SectionDefinition:
    elset: str
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
    instance: str = "Coupon-1"
    part: str = "Coupon"

    @property
    def node_sets(self) -> dict[str, np.ndarray]:
        sets = dict(self.mesh.node_sets)
        for name, index in self.probe_nodes.items():
            sets[f"Probe-{name}"] = np.array([index])
        return sets

    @property
    def element_sets(self) -> dict[str, np.ndarray]:
        sets = dict(self.mesh.element_sets)
        for name, index in self.probe_elements.items():
            sets[f"Probe-{name}"] = np.array([index])
        return sets


def mesh_for_spec(spec: CouponSpec) -> Mesh2D:
    """The mesh the spec asks for: a structured rectangle, or Gmsh's O-grid for the open-hole coupon. Bending geometries are a later chunk."""
    if not spec.si:
        raise SpecError("mesh_for_spec needs the spec in SI (load_spec)")
    if spec.kind in BENDING_KINDS:
        raise SpecError(f"{spec.kind} models are not built yet (planned: the bending chunk, CalculiX only)")
    g = spec.geometry
    bands = {}
    node_bands = {}
    if g.tab_length:
        bands = {"Tab-Bottom": (0.0, g.tab_length), "Gauge": (g.tab_length, g.length - g.tab_length), "Tab-Top": (g.length - g.tab_length, g.length)}
        if spec.grips is not None and spec.grips.region == "tabs":
            # the whole tab is gripped: every node within tab_length of an end belongs to that grip set (as the team's decks do)
            node_bands = {"Grip-Bottom": (0.0, g.tab_length), "Grip-Top": (g.length - g.tab_length, g.length)}
    if spec.mesh.mesher == "gmsh":
        hole = spec.mesh.hole
        return gmsh_open_hole_plate(g.width, g.length, g.hole_diameter, spec.mesh.element_size, hole.circumferential, hole.radial_layers,
                                    hole.ring_ratio, hole.growth, order=spec.mesh.element_order, tab_length=g.tab_length or 0.0,
                                    node_rows=node_lines(spec), element_bands=bands, node_bands=node_bands)
    nx, ny = mesh_counts(spec)
    return structured_rectangle(g.width, g.length, nx, ny, spec.mesh.element_order, node_rows=node_lines(spec), element_bands=bands,
                                node_bands=node_bands)


def build_model(spec: CouponSpec, mesh: Mesh2D | None = None) -> FEModel:
    if not spec.si:
        raise SpecError("build_model needs the spec in SI (load_spec)")
    mesh = mesh if mesh is not None else mesh_for_spec(spec)
    material = spec_material(spec)
    thickness = spec_ply_thickness(spec)
    angles = full_angles(spec)
    plies = tuple(PlyDefinition(thickness, angle, material.name, f"Ply-{k}") for k, angle in enumerate(angles, start=1))
    listed = plies[: len(spec.layup.angles)] if spec.layup.symmetric else plies
    section = SectionDefinition(elset=ALL_ELEMENTS, plies=plies, symmetric=spec.layup.symmetric, listed=listed)
    orientation_angles = tuple(sorted(set(angles)))
    probe_nodes = {name: mesh.nearest_node(point) for name, point in spec.probes.nodes.items()}
    probe_elements = {name: mesh.nearest_element(point) for name, point in spec.probes.elements.items()}

    g, loading = spec.geometry, spec.loading
    reference_points: tuple[ReferencePoint, ...] = ()
    couplings: tuple[CouplingDefinition, ...] = ()
    boundaries: list[BoundaryDefinition] = []
    loads: list[LoadDefinition] = []
    if spec.grips.kind == "coupling":
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
            loads += consistent_edge_loads(mesh, "Grip-Top", 2, loading.value, instance="Coupon-1")

    heading = (
        f"Generated by anisotropy_fea {package_version} from spec {Path(spec.source_path).name if spec.source_path else '<text>'} "
        f"(sha256 {spec.source_sha256[:16]}); do not edit by hand.",
        f"{spec.title}",
        f"kind {spec.kind}; length {g.length:g} m, width {g.width:g} m" + (f", tabs {g.tab_length:g} m" if g.tab_length else "")
        + (f", central hole of diameter {g.hole_diameter:g} m" if g.hole_diameter else ""),
        f"mesh {mesh.mesher}, {mesh.element_count} elements of order {mesh.order}, {mesh.node_count} nodes",
        f"layup bottom-first {angles}" + (" (listed as the symmetric half)" if spec.layup.symmetric else "") + f", ply thickness {thickness:g} m",
        f"material {material.name}: {material.source}; rights class {material.rights}",
        *[f"  {line}" for line in material.citation_lines],
        f"out-of-plane constants: G13 {material.G13:g}, G23 {material.G23:g}, E3 {material.E3:g}, nu13 {material.nu13:g}, nu23 {material.nu23:g} (SI; "
        + ("transverse isotropy stated in the spec" if spec.material.transverse.transverse_isotropy else "given in the spec") + ")"
        + ("; nu13 = nu23 = 0 written for plane stress, as Abaqus LAMINA and our kernel assume (plane_stress = true in the spec)" if material.plane_stress else ""),
        f"grips {spec.grips.kind} on the {'end node rows' if spec.grips.region == 'line' else 'whole tab regions'}; "
        f"loading {loading.control} {loading.value:g} " + ("m" if loading.control == "displacement" else "N"),
        f"units of this deck: {spec.units}",
    )
    return FEModel(spec=spec, mesh=mesh, material=material, section=section, orientation_angles=orientation_angles,
                   reference_points=reference_points, couplings=couplings, boundaries=tuple(boundaries), loads=tuple(loads),
                   probe_nodes=probe_nodes, probe_elements=probe_elements, heading=heading)


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
