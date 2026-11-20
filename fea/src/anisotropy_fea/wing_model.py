"""A wing's finite element model in CalculiX, built from the same description as its hand calculation (ADR-0117).

The shape's shell mesh (wing_shape.py, ADR-0116) is promoted to eight-node shells (CalculiX's composite shells are S8R only,
ADR-0030) with straight edges. Every element carries its part's whole layup as layers, each ply in its own fibre axes and the
core between the faces: a skin's or a web's 0 degree direction is the span, a rib's is the chord, and a positive angle turns
from it about the element's normal (outward on the skins, aft on the webs, toward the root on the ribs). The fibre axes follow
the curved skins: elements are grouped by the direction of their normal in steps of ANGLE_STEP_DEG, and each group gets its
own orientations.

The ply's out-of-plane constants follow the rule the workspace writes for a tape (ADR-0090): E3 = E2, G13 = G12, G23 = E2 / 3,
and nu13 = nu23 = 0, the plane stress our engine assumes. The core's in-plane modulus is taken as its through-thickness one and
its Poisson ratios as zero; the faces are about a thousand times stiffer in the plane, so neither matters to the result.

The flight loads go on by superposition. The model is solved under four load patterns, each its own static step: the lift of
the hand calculation's spanwise shape (Schrenk's) for 1 N on one side, a pitching moment of 1 N*m per metre along the whole
span, and the aileron's lift and moment of 1 N and 1 N*m per metre over its span. Each pattern is a vertical load on the two
skins, half on each, varying linearly along the chord so that every strip's resultant is the pattern's lift at the
aerodynamic center and its moment about it; the nodal forces are the load's consistent ones (the integral of each shape
function against it over the element's plan area). Every flight case of the envelope is then a sum of the four solutions
with the factors the hand calculation uses: the lift n W / 2, the moment q c^2 c_m, the aileron's q c Delta c_l and
q c^2 Delta c_m.

The skins run round the whole airfoil, as the shape draws them, or, with skins="box", only between the spars: the hand
calculation's box, whose nose and tail then carry no load and the airload goes on the box's skins with the same resultant and
moment. Until the wing description says whether the skin ahead of and behind the box is structure or a fairing, both are run.

The root is clamped (every node at y = 0, all six freedoms). No real root is that stiff: the clamp stops the plies' Poisson
contraction and the box's warping there, which raises the stresses within about a box height of it (Saint-Venant). The checks
are read outboard of a root zone one web height long, the deeper web's, and the root's own values are kept beside them. The wing's own weight is not applied, as in the hand calculation.
CalculiX prints each layer's stresses in that layer's fibre axes (*EL PRINT, GLOBAL=NO, checked on a tilted plate); the
strength ratio of every ply at every integration point is the engine's, by the envelope's criterion; a core's transverse
shear stress is set against its shear strength.
"""

from __future__ import annotations

import argparse
import math
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from anisotropy_engine.failure import scaled_strength_ratios
from anisotropy_engine.wing.description import FlightEnvelope, Layup, Wing
from anisotropy_engine.wing.aeroelastic import divergence_dynamic_pressure, equivalent_airspeed
from anisotropy_engine.wing.atmosphere import air_density, density_ratio
from anisotropy_engine.wing.flutter import FlutterResult, TypicalSection, flutter_speed
from anisotropy_engine.wing.loads import LoadCase, flight_cases

from .calculix import run_calculix
from .wing_shape import Section, ShapeError, ShellMesh, build_wing_shape, mid_surface_section, rib_stations

ANGLE_STEP_DEG = 2.0  # the fibre axes of a curved skin follow its normal to within half of this
PARALLEL_TOLERANCE = math.sin(math.radians(2.0))  # how far an element's normal may lean toward its 0 degree direction
POINTS_IN_PLANE = 4  # an S8R composite shell expands to one C3D20R brick: 4 points in the plane ...
POINTS_PER_LAYER = 2  # ... and 2 through each layer, numbered by level from the bottom up (fea/checks/calculix-conventions.toml)
# CalculiX 2.21 as Ubuntu 24.04 builds it (the solver image's) stops with "stack smashing detected" on a composite shell section
# of 14 layers or more, and solves 13 (tried 2026-11-20 on the D3039 check's deck and on the wing's, ADR-0117 amendment 1).
MAX_LAYERS = 13
PATTERNS = ("lift", "moment", "aileron lift", "aileron moment")
SKINS = ("Upper skin", "Lower skin")
WEBS = ("Front spar", "Rear spar")
SKIN_EXTENTS = ("airfoil", "box")  # the skins round the whole airfoil, or only between the spars
MM = 1e-3
MPA = 1e6
GAUSS_3 = (np.array([-math.sqrt(0.6), 0.0, math.sqrt(0.6)]), np.array([5 / 9, 8 / 9, 5 / 9]))
SPLIT = 12  # an element the aileron's end crosses is integrated on SPLIT x SPLIT cells


class WingModelError(ValueError):
    """The wing cannot be modeled as described."""


@dataclass(frozen=True)
class QuadraticMesh:
    """The shape's mesh with a node at the middle of every edge: S8R order, the four corners then the four midsides."""

    nodes: np.ndarray  # (n, 3), m
    elements: np.ndarray  # (ne, 8), zero-based
    element_sets: dict[str, np.ndarray]
    root: np.ndarray  # nodes at y = 0


@dataclass(frozen=True)
class Layer:
    thickness_m: float
    material: str  # "PLY" or "CORE"
    angle_deg: float  # a ply's angle; 0 for the core, whose axes are the group's own


@dataclass(frozen=True)
class Group:
    """Elements of one layup whose normals point the same way to within half of ANGLE_STEP_DEG."""

    name: str
    layup: str  # "skin", "spar" or "rib"
    normal: np.ndarray  # (3,)
    reference: np.ndarray  # the 0 degree direction
    members: np.ndarray


@dataclass
class WingModel:
    wing: Wing
    envelope: FlightEnvelope
    section: Section
    mesh: QuadraticMesh
    part_of: np.ndarray  # (ne,) part name of each element
    groups: list[Group]
    layers: dict[str, list[Layer]]  # by layup
    patterns: dict[str, np.ndarray]  # pattern -> (n,) vertical nodal force, N
    deck: str
    element_size_m: float
    build_seconds: float
    skins: str = "airfoil"  # one of SKIN_EXTENTS


@dataclass(frozen=True)
class PatternResults:
    """CalculiX's answer to each load pattern: displacements of every node and stresses at every integration point."""

    displacement: dict[str, np.ndarray]  # pattern -> (n, 3), m
    stress: dict[str, np.ndarray]  # pattern -> (points, 6), Pa, in each layer's fibre axes: s11, s22, s33, s12, s13, s23
    point_element: np.ndarray  # (points,) zero-based element of each point
    point_layer: np.ndarray  # (points,) layer of each point, bottom first
    solve_seconds: float
    equations: int | None


@dataclass(frozen=True)
class FeCheck:
    name: str  # "skin plies", "spar plies", "rib plies", "core shear"
    strength_ratio: float
    margin_ultimate: float
    margin_proof: float | None
    part: str | None
    station_m: float | None
    chord_m: float | None
    ply_angle_deg: float | None
    mode: str | None


@dataclass(frozen=True)
class FeCase:
    case: LoadCase
    factors: dict[str, float]
    tip_deflection_m: float  # at the hand calculation's shear center, up positive
    tip_twist_rad: float  # nose up positive
    applied_lift_N: float  # the vertical load this case puts on one side
    checks: tuple[FeCheck, ...]  # outboard of the root zone
    root_checks: tuple[FeCheck, ...]  # everywhere, the clamped root included

    @property
    def governing(self) -> FeCheck:
        return min(self.checks, key=lambda check: check.margin_ultimate)


# ---------------------------------------------------------------------------------------------------------------- mesh and axes

def quadratic(mesh: ShellMesh) -> QuadraticMesh:
    """A node at the middle of every edge, shared by the elements on either side."""
    nodes = [tuple(p) for p in mesh.nodes]
    middle: dict[tuple[int, int], int] = {}

    def at(a: int, b: int) -> int:
        key = (min(a, b), max(a, b))
        if key not in middle:
            middle[key] = len(nodes)
            nodes.append(tuple((mesh.nodes[a] + mesh.nodes[b]) / 2))
        return middle[key]

    elements = np.array([[*q, at(q[0], q[1]), at(q[1], q[2]), at(q[2], q[3]), at(q[3], q[0])] for q in mesh.elements.tolist()], dtype=np.int64)
    nodes = np.array(nodes)
    return QuadraticMesh(nodes=nodes, elements=elements, element_sets=dict(mesh.element_sets), root=np.nonzero(np.abs(nodes[:, 1]) < 1e-9)[0])


def within_box(mesh: QuadraticMesh, part_of: np.ndarray, x_from: float, x_to: float) -> tuple[QuadraticMesh, np.ndarray]:
    """The mesh without the skin and rib elements ahead of the front spar and behind the rear spar, its nodes renumbered.
    The shape splits the skins and ribs at the webs, so every element lies wholly on one side of each web."""
    centre_x = mesh.nodes[mesh.elements[:, :4], 0].mean(axis=1)
    webs = np.isin(part_of, WEBS)
    keep = webs | ((centre_x > x_from) & (centre_x < x_to))
    kept = np.nonzero(keep)[0]
    used = np.unique(mesh.elements[kept])
    renumber = np.full(mesh.nodes.shape[0], -1, dtype=np.int64)
    renumber[used] = np.arange(used.size)
    new_index = np.full(mesh.elements.shape[0], -1, dtype=np.int64)
    new_index[kept] = np.arange(kept.size)
    sets = {name: new_index[members[keep[members]]] for name, members in mesh.element_sets.items()}
    nodes = mesh.nodes[used]
    trimmed = QuadraticMesh(nodes=nodes, elements=renumber[mesh.elements[kept]], element_sets={k: v for k, v in sets.items() if v.size},
                            root=np.nonzero(np.abs(nodes[:, 1]) < 1e-9)[0])
    return trimmed, part_of[kept]


def layup_of(part: str) -> str:
    return "rib" if part.startswith("Rib") else ("spar" if part in WEBS else "skin")


def reference_axis(part: str) -> np.ndarray:
    """The 0 degree direction: the span on the skins and webs, the chord on the ribs."""
    return np.array([1.0, 0.0, 0.0]) if part.startswith("Rib") else np.array([0.0, 1.0, 0.0])


def element_normals(mesh: QuadraticMesh) -> np.ndarray:
    p = mesh.nodes[mesh.elements[:, :4]]
    normal = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
    return normal / np.linalg.norm(normal, axis=1)[:, None]


def orientation_groups(mesh: QuadraticMesh, part_of: np.ndarray, step_deg: float = ANGLE_STEP_DEG) -> list[Group]:
    """Elements grouped by layup and by the direction of their normal about the 0 degree axis, in steps of `step_deg`."""
    normals = element_normals(mesh)
    found: dict[tuple, list[int]] = {}
    for k, (part, n) in enumerate(zip(part_of, normals)):
        r = reference_axis(part)
        # A skin element on the curved airfoil tilts a little out of the span (under 0.2 degree at 40 mm); more means the wing is not straight
        if abs(float(n @ r)) > PARALLEL_TOLERANCE:
            raise WingModelError(f"An element of {part} is not parallel to its 0 degree direction; the model needs a straight wing")
        u, v = (np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])) if r[1] == 1.0 else (np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0]))
        step = int(round(math.degrees(math.atan2(float(n @ v), float(n @ u))) / step_deg))
        found.setdefault((layup_of(part), int(r[1]), step), []).append(k)
    groups = []
    for (layup, along_span, step), members in sorted(found.items()):
        r = np.array([0.0, 1.0, 0.0]) if along_span else np.array([1.0, 0.0, 0.0])
        u, v = (np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])) if along_span else (np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0]))
        angle = math.radians(step * step_deg)
        groups.append(Group(name=f"G{len(groups) + 1}", layup=layup, normal=math.cos(angle) * u + math.sin(angle) * v, reference=r,
                            members=np.array(members)))
    return groups


def fibre_axes(group: Group, angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """The fibre direction of a ply at `angle_deg` in the group, and the in-plane direction across it."""
    side = np.cross(group.normal, group.reference)
    a = math.radians(angle_deg)
    fibre = math.cos(a) * group.reference + math.sin(a) * side
    return fibre, np.cross(group.normal, fibre)


def layers(layup: Layup) -> list[Layer]:
    """The layup's layers from one face to the other; a symmetric layup reads the same from either side. Every ply is a layer of
    its own unless that makes more than MAX_LAYERS: then neighbouring plies at one angle are one layer of their summed thickness,
    which is the same stiffness, its stresses read at two points through the pair instead of two in each."""
    face = [Layer(layup.material.ply_thickness_m, "PLY", float(angle)) for angle in layup.half_stack_deg]
    core = [Layer(layup.core_thickness_m, "CORE", 0.0)] if layup.core_thickness_m > 0 else []
    stack = face + core + face[::-1]
    if len(stack) <= MAX_LAYERS:
        return stack
    joined = [stack[0]]
    for layer in stack[1:]:
        last = joined[-1]
        if layer.material == last.material == "PLY" and layer.angle_deg == last.angle_deg:
            joined[-1] = Layer(last.thickness_m + layer.thickness_m, "PLY", layer.angle_deg)
        else:
            joined.append(layer)
    return joined


# ---------------------------------------------------------------------------------------------------------------- loads

def serendipity(xi: float, eta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The eight shape functions of the S8R element and their derivatives in xi and eta."""
    corners = np.array([(-1, -1), (1, -1), (1, 1), (-1, 1)], dtype=float)
    n, dxi, deta = np.zeros(8), np.zeros(8), np.zeros(8)
    for k, (a, b) in enumerate(corners):
        n[k] = 0.25 * (1 + a * xi) * (1 + b * eta) * (a * xi + b * eta - 1)
        dxi[k] = 0.25 * a * (1 + b * eta) * (2 * a * xi + b * eta)
        deta[k] = 0.25 * b * (1 + a * xi) * (a * xi + 2 * b * eta)
    for k, (a, b) in enumerate([(0, -1), (1, 0), (0, 1), (-1, 0)], start=4):
        if a == 0:
            n[k] = 0.5 * (1 - xi**2) * (1 + b * eta)
            dxi[k] = -xi * (1 + b * eta)
            deta[k] = 0.5 * b * (1 - xi**2)
        else:
            n[k] = 0.5 * (1 + a * xi) * (1 - eta**2)
            dxi[k] = 0.5 * a * (1 - eta**2)
            deta[k] = -eta * (1 + a * xi)
    return n, dxi, deta


def _rule(cells: int) -> list[tuple[float, float, float]]:
    """Points and weights on [-1, 1]^2: three-point Gauss on each of cells x cells squares."""
    points, weights = GAUSS_3
    out = []
    for i in range(cells):
        for j in range(cells):
            for a, wa in zip(points, weights):
                for b, wb in zip(points, weights):
                    xi = -1 + (2 * i + 1 + a) / cells
                    eta = -1 + (2 * j + 1 + b) / cells
                    out.append((xi, eta, wa * wb / cells**2))
    return out


def schrenk_lift(y: np.ndarray, half_span_m: float) -> np.ndarray:
    """The hand calculation's spanwise lift for 1 N on one side: the mean of a uniform and an elliptical load (loads.py)."""
    eta = np.clip(y / half_span_m, 0.0, 1.0)
    return 0.5 * (4 / (math.pi * half_span_m) * np.sqrt(1 - eta**2) + 1 / half_span_m)


def strip_pressure(x: np.ndarray, lift: np.ndarray, moment: np.ndarray, x_from: float, x_to: float, x_ac: float) -> np.ndarray:
    """Vertical load per unit plan area along a strip from x_from to x_to whose resultant is `lift` (per unit span) at x_ac and
    whose moment about x_ac is `moment` (nose up positive): the linear distribution p = lift / w + beta (x - x_mid)."""
    width = x_to - x_from
    middle = (x_from + x_to) / 2
    beta = 12 * (lift * (x_ac - middle) - moment) / width**3
    return lift / width + beta * (x - middle)


def load_patterns(wing: Wing, envelope: FlightEnvelope, mesh: QuadraticMesh, part_of: np.ndarray, section: Section,
                  skins: str = "airfoil") -> dict[str, np.ndarray]:
    """The vertical nodal forces of each load pattern, consistent with the S8R shape functions, half on each skin."""
    L = wing.geometry.half_span_m
    if skins == "box":
        x_from, x_to = section.spar_x_m
    else:
        x_from = float(min(section.upper[:, 0].min(), section.lower[:, 0].min()))
        x_to = float(max(section.upper[:, 0].max(), section.lower[:, 0].max()))
    x_ac = wing.aerodynamics.aerodynamic_center * wing.geometry.chord_m
    aileron = envelope.aileron
    names = PATTERNS if aileron is not None else PATTERNS[:2]
    span = (0.0, L) if aileron is None else (aileron.span_start_m, aileron.span_end_m)
    forces = {name: np.zeros(mesh.nodes.shape[0]) for name in names}
    plain, split = _rule(1), _rule(SPLIT)
    shapes = {}
    for k in np.nonzero(np.isin(part_of, SKINS))[0]:
        nodes = mesh.elements[k]
        xy = mesh.nodes[nodes][:, :2]
        ys = xy[:, 1]
        crosses = aileron is not None and any(ys.min() < edge < ys.max() for edge in span)
        for xi, eta, weight in (split if crosses else plain):
            key = (xi, eta)
            if key not in shapes:
                shapes[key] = serendipity(xi, eta)
            n, dxi, deta = shapes[key]
            jacobian = np.array([dxi @ xy, deta @ xy])
            area = abs(np.linalg.det(jacobian)) * weight
            x, y = n @ xy
            on = 1.0 if span[0] <= y <= span[1] else 0.0
            per_pattern = {"lift": (schrenk_lift(np.array(y), L), 0.0), "moment": (0.0, 1.0), "aileron lift": (on, 0.0), "aileron moment": (0.0, on)}
            for name in names:
                lift, moment = per_pattern[name]
                if lift or moment:
                    p = float(strip_pressure(np.array(x), np.array(lift), np.array(moment), x_from, x_to, x_ac))
                    np.add.at(forces[name], nodes, 0.5 * p * area * n)
    return forces


def case_factors(case: LoadCase, wing: Wing, envelope: FlightEnvelope) -> dict[str, float]:
    """How much of each pattern a flight case is: the factors of the hand calculation's running loads (loads.py)."""
    c, q = wing.geometry.chord_m, case.dynamic_pressure_Pa
    factors = {"lift": case.load_factor * envelope.gross_weight_N / 2, "moment": q * c**2 * wing.aerodynamics.pitching_moment_coefficient}
    aileron = envelope.aileron
    if aileron is not None:
        delta_cl = {"none": 0.0, "down": aileron.down_delta_cl, "up": aileron.up_delta_cl}[case.aileron]
        delta_cm = {"none": 0.0, "down": aileron.down_delta_cm, "up": aileron.up_delta_cm}[case.aileron]
        factors.update({"aileron lift": q * c * delta_cl, "aileron moment": q * c**2 * delta_cm})
    return factors


# ---------------------------------------------------------------------------------------------------------------- the deck

def _num(value: float) -> str:
    return f"{value:.9g}"


def _rows(values, per_line: int = 12) -> list[str]:
    values = [str(v) for v in values]
    return [", ".join(values[i:i + per_line]) for i in range(0, len(values), per_line)]


def check_describable(wing: Wing) -> None:
    """Refuse a wing the model cannot build: a core without its stiffness, ribs without a layup, a part of more layers than
    CalculiX solves."""
    if wing.spar_caps is not None or wing.has_zones:
        raise WingModelError("The finite element check does not take spar caps or zones along the span yet (the hand calculation does): "
                             "take them out to run it")
    for name, layup in (("skin", wing.skin), ("spar", wing.spar), ("rib", wing.rib)):
        if layup is not None and layup.core_thickness_m > 0 and layup.core is None:
            raise WingModelError(f"The finite element model needs the {name} core's stiffness: name a library core in [{name}] "
                                 "(core = \"divinycell-h45\") or give core_modulus and core_shear_modulus")
    if wing.geometry.rib_spacing_m is not None and wing.rib is None:
        raise WingModelError("The wing has ribs but no rib layup: add a [rib] table with its half_stack")
    for name, layup in (("skin", wing.skin), ("spar", wing.spar), ("rib", wing.rib)):
        if layup is not None and (count := len(layers(layup))) > MAX_LAYERS:
            raise WingModelError(f"The finite element model holds at most {MAX_LAYERS} layers through a part, the core and plies "
                                 f"of one angle side by side counting as one; the {name} layup makes {count}. Take plies out, "
                                 "or put plies of one angle next to each other")


def _model_lines(model: WingModel) -> list[str]:
    """The deck up to its steps: nodes, elements, materials, ply sections and the clamped root, in mm, N, MPa and t/mm^3."""
    wing, mesh = model.wing, model.mesh
    material = wing.skin.material
    lamina = material.lamina
    out = ["*HEADING", f"Wing {wing.name}: written by anisotropy_fea.wing_model (ADR-0117); units mm, N, MPa, t/mm^3",
           f"** {mesh.elements.shape[0]} S8R shells at {model.element_size_m / MM:g} mm, every ply a layer (plies of one angle side by side joined past {MAX_LAYERS}); one static step per load pattern",
           "*NODE, NSET=NALL"]
    out += [f"{k + 1}, {_num(x / MM)}, {_num(y / MM)}, {_num(z / MM)}" for k, (x, y, z) in enumerate(mesh.nodes)]
    out.append("*ELEMENT, TYPE=S8R, ELSET=EALL")
    out += [f"{k + 1}, " + ", ".join(str(n + 1) for n in nodes) for k, nodes in enumerate(mesh.elements.tolist())]
    for name, members in mesh.element_sets.items():
        out.append(f"*ELSET, ELSET={name.upper().replace(' ', '_')}")
        out += _rows(np.asarray(members) + 1)
    out.append("*NSET, NSET=ROOT")
    out += _rows(mesh.root + 1)
    E2 = lamina.E2
    out += ["** The ply's out-of-plane constants by the workspace's rule for a tape (ADR-0090): E3 = E2, G13 = G12, G23 = E2 / 3, nu13 = nu23 = 0.",
            "*MATERIAL, NAME=PLY", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
            ", ".join(_num(v) for v in (lamina.E1 / MPA, E2 / MPA, E2 / MPA, lamina.nu12, 0.0, 0.0, lamina.G12 / MPA, lamina.G12 / MPA)),
            f"{_num(E2 / 3 / MPA)}, 293.", "*DENSITY", _num(material.density_kg_m3 * 1e-12)]
    cores = {name: layup.core for name, layup in (("skin", wing.skin), ("spar", wing.spar), ("rib", wing.rib))
             if layup is not None and layup.core is not None and layup.core_thickness_m > 0}
    for name, core in cores.items():
        layup = {"skin": wing.skin, "spar": wing.spar, "rib": wing.rib}[name]
        E, G = core.modulus_Pa / MPA, core.shear_modulus_Pa / MPA
        out += [f"** The {name} core, {core.name}: its in-plane modulus taken as its through-thickness one, its Poisson ratios as zero.",
                f"*MATERIAL, NAME=CORE_{name.upper()}", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
                ", ".join(_num(v) for v in (E, E, E, 0.0, 0.0, 0.0, G, G)), f"{_num(G)}, 293.", "*DENSITY", _num(layup.core_density_kg_m3 * 1e-12)]
    for group in model.groups:
        out.append(f"*ELSET, ELSET={group.name}")
        out += _rows(group.members + 1)
        stack = model.layers[group.layup]
        for angle in sorted({layer.angle_deg for layer in stack}):
            fibre, across = fibre_axes(group, angle)
            out.append(f"*ORIENTATION, NAME={group.name}_{_angle_name(angle)}")
            out.append(", ".join(_num(v) for v in (*fibre, *across)))
        out.append(f"*SHELL SECTION, ELSET={group.name}, COMPOSITE")
        for layer in stack:
            name = "PLY" if layer.material == "PLY" else f"CORE_{group.layup.upper()}"
            out.append(f"{_num(layer.thickness_m / MM)}, , {name}, {group.name}_{_angle_name(layer.angle_deg)}")
    out += ["*BOUNDARY", "ROOT, 1, 6"]
    return out


def _loads(force: np.ndarray) -> list[str]:
    return ["*CLOAD, OP=NEW"] + [f"{k + 1}, 3, {_num(force[k])}" for k in np.nonzero(np.abs(force) > 0)[0]]


def write_deck(model: WingModel) -> str:
    """The CalculiX deck in mm, N, MPa and t/mm^3: one static step per load pattern."""
    out = _model_lines(model)
    for name, force in model.patterns.items():
        out += [f"** Load pattern: {name}", "*STEP", "*STATIC", *_loads(force)]
        out += ["*NODE PRINT, NSET=NALL", "U", "*EL PRINT, ELSET=EALL, GLOBAL=NO", "S", "*END STEP"]
    return "\n".join(out) + "\n"


def _angle_name(angle: float) -> str:
    whole = round(angle)
    text = str(abs(whole)) if abs(angle - whole) < 1e-9 else f"{abs(angle):g}".replace(".", "P")
    return ("M" if angle < 0 else "") + text


def build_wing_model(wing: Wing, envelope: FlightEnvelope, element_size_m: float, skins: str = "airfoil") -> WingModel:
    """The wing's mesh, ply groups, load patterns and deck; `skins` is "airfoil" or "box" (SKIN_EXTENTS)."""
    if skins not in SKIN_EXTENTS:
        raise WingModelError(f"skins is one of {', '.join(SKIN_EXTENTS)}, got {skins!r}")
    check_describable(wing)
    began = time.perf_counter()
    shape = build_wing_shape(wing, element_size_m=element_size_m)
    mesh = quadratic(shape.mesh)
    part_of = np.empty(mesh.elements.shape[0], dtype=object)
    for name, members in mesh.element_sets.items():
        part_of[members] = name
    section = mid_surface_section(wing)
    if skins == "box":
        mesh, part_of = within_box(mesh, part_of, *section.spar_x_m)
    stacks = {name: layers(layup) for name, layup in (("skin", wing.skin), ("spar", wing.spar), ("rib", wing.rib)) if layup is not None}
    model = WingModel(wing=wing, envelope=envelope, section=section, mesh=mesh, part_of=part_of, groups=orientation_groups(mesh, part_of),
                      layers=stacks, patterns=load_patterns(wing, envelope, mesh, part_of, section, skins), deck="",
                      element_size_m=element_size_m, build_seconds=0.0, skins=skins)
    model.deck = write_deck(model)
    model.build_seconds = time.perf_counter() - began
    return model


# ---------------------------------------------------------------------------------------------------------------- results

def _blocks(dat: str, marker: str) -> list[list[str]]:
    """The data lines of every block of the .dat whose header starts with `marker`, in the order printed."""
    blocks, current = [], None
    for line in dat.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker):
            current = []
            blocks.append(current)
        elif current is not None:
            if not stripped:
                if current:
                    current = None
                continue
            if stripped[0].isalpha():
                current = None
                continue
            current.append(stripped)
    return blocks


def read_results(model: WingModel, dat: str, solve_seconds: float = 0.0, equations: int | None = None) -> PatternResults:
    names = list(model.patterns)
    moves = _blocks(dat, "displacements")
    stresses = _blocks(dat, "stresses")
    if len(moves) != len(names) or len(stresses) != len(names):
        raise WingModelError(f"CalculiX printed {len(moves)} displacement and {len(stresses)} stress blocks for {len(names)} load patterns")
    n = model.mesh.nodes.shape[0]
    displacement = {}
    for name, block in zip(names, moves):
        values = np.array([[float(v) for v in line.split()[:4]] for line in block])
        u = np.zeros((n, 3))
        u[values[:, 0].astype(int) - 1] = values[:, 1:4] * MM
        displacement[name] = u
    stress, point_element, point_layer = {}, None, None
    for name, block in zip(names, stresses):
        values = np.array([[float(v) for v in line.split()[:8]] for line in block])
        if point_element is None:
            point_element = values[:, 0].astype(np.int64) - 1
            point = values[:, 1].astype(np.int64) - 1
            point_layer = point // POINTS_IN_PLANE // POINTS_PER_LAYER
            counts = np.array([len(model.layers[layup_of(model.part_of[k])]) for k in point_element])
            if (point_layer >= counts).any():
                raise WingModelError("CalculiX printed more integration points than the elements' layers hold")
        s = values[:, 2:8] * MPA  # sxx, syy, szz, sxy, sxz, syz in the layer's axes
        stress[name] = s[:, [0, 1, 2, 3, 4, 5]]
    return PatternResults(displacement=displacement, stress=stress, point_element=point_element, point_layer=point_layer,
                          solve_seconds=solve_seconds, equations=equations)


def run_wing_model(model: WingModel, workdir: Path | str | None = None, ccx: str | None = None, threads: int = 4,
                   timeout_s: float = 3600.0) -> PatternResults:
    """Solve the deck with CalculiX (the equation solver on one thread, as every run of ours, ADR-0056 amendment 7)."""
    owned = workdir is None
    folder = Path(tempfile.mkdtemp(prefix="wing-")) if owned else Path(workdir)
    folder.mkdir(parents=True, exist_ok=True)
    deck = folder / "wing.inp"
    deck.write_text(model.deck, encoding="utf-8")
    result = run_calculix(deck, ccx=ccx, workdir=folder, timeout_s=timeout_s, threads=threads)
    equations = None
    lines = result.stdout.splitlines()
    for k, line in enumerate(lines[:-1]):
        if line.strip() == "number of equations":
            equations = int(lines[k + 1].strip())
            break
    return read_results(model, result.dat_text, result.elapsed_s, equations)


def _tip(model: WingModel) -> tuple[np.ndarray, np.ndarray, float, float]:
    """The nodes of the front and of the rear web at the tip, and the webs' chord positions."""
    mesh, L = model.mesh, model.wing.geometry.half_span_m
    tip = np.abs(mesh.nodes[:, 1] - L) < 1e-9
    webs = []
    for name in WEBS:
        nodes = np.unique(mesh.elements[mesh.element_sets[name]])
        webs.append(nodes[tip[nodes]])
    return webs[0], webs[1], model.section.spar_x_m[0], model.section.spar_x_m[1]


def root_zone(model: WingModel) -> float:
    """How far from the clamped root the checks begin: the deeper web's height."""
    return max(top - bottom for top, bottom in zip(model.section.spar_top_m, model.section.spar_bottom_m))


def fe_cases(model: WingModel, results: PatternResults, shear_center_m: float) -> list[FeCase]:
    """Every flight case the envelope states, as a sum of the load patterns: tip deflection and twist, and the lowest strength
    ratio of the skins', webs' and ribs' plies and of the core in shear, outboard of the root zone and everywhere."""
    wing, envelope = model.wing, model.envelope
    cases, _ = flight_cases(envelope, wing.geometry.chord_m)
    front, rear, x_front, x_rear = _tip(model)
    lamina = wing.skin.material.lamina
    element, layer = results.point_element, results.point_layer
    parts = model.part_of[element]
    is_ply = np.array([model.layers[layup_of(p)][j].material == "PLY" for p, j in zip(parts, layer)])
    angle = np.array([model.layers[layup_of(p)][j].angle_deg for p, j in zip(parts, layer)])
    kinds = np.array([layup_of(p) for p in parts])
    centroid = model.mesh.nodes[model.mesh.elements[:, :4]].mean(axis=1)
    outboard = centroid[element, 1] >= root_zone(model)
    core_strength = {name: getattr(layup.core, "shear_strength_Pa", None) for name, layup in
                     (("skin", wing.skin), ("spar", wing.spar), ("rib", wing.rib)) if layup is not None}
    out = []
    for case in cases:
        factors = case_factors(case, wing, envelope)
        u = sum(factors[name] * results.displacement[name] for name in model.patterns)
        s = sum(factors[name] * results.stress[name] for name in model.patterns)
        w_front, w_rear = float(u[front, 2].mean()), float(u[rear, 2].mean())
        deflection = w_front + (w_rear - w_front) * (shear_center_m - x_front) / (x_rear - x_front)
        twist = (w_front - w_rear) / (x_rear - x_front)
        applied = sum(factors[name] * float(model.patterns[name].sum()) for name in model.patterns)
        checks, root_checks = [], []
        ratios = np.full(len(element), np.inf)
        modes = np.full(len(element), None, dtype=object)
        if is_ply.any():
            r, m = scaled_strength_ratios(envelope.criterion, lamina, s[is_ply][:, [0, 1, 3]], envelope.f12_star)
            ratios[is_ply] = r
            modes[is_ply] = m
        for name, kind in (("skin plies", "skin"), ("spar plies", "spar"), ("rib plies", "rib")):
            if kind not in model.layers:
                continue
            chosen = is_ply & (kinds == kind)
            checks.append(_check(name, ratios, modes, chosen & outboard, element, parts, angle, centroid, envelope))
            root_checks.append(_check(name, ratios, modes, chosen, element, parts, angle, centroid, envelope))
        tau = np.hypot(s[:, 4], s[:, 5])
        core_ratio = np.full(len(element), np.inf)
        core_points = ~is_ply
        for kind, strength in core_strength.items():
            chosen = core_points & (kinds == kind)
            if strength is not None and chosen.any():
                core_ratio[chosen] = strength / np.maximum(tau[chosen], 1e-300)
        if core_points.any() and any(v is not None for v in core_strength.values()):
            mode, no_angle = np.full(len(element), "core shear", dtype=object), np.full(len(element), np.nan)
            checks.append(_check("core shear", core_ratio, mode, core_points & outboard, element, parts, no_angle, centroid, envelope))
            root_checks.append(_check("core shear", core_ratio, mode, core_points, element, parts, no_angle, centroid, envelope))
        out.append(FeCase(case=case, factors=factors, tip_deflection_m=deflection, tip_twist_rad=twist, applied_lift_N=applied,
                          checks=tuple(checks), root_checks=tuple(root_checks)))
    return out


def _check(name, ratios, modes, chosen, element, parts, angle, centroid, envelope) -> FeCheck:
    if not chosen.any() or not np.isfinite(ratios[chosen]).any():
        return FeCheck(name, math.inf, math.inf, None if envelope.proof_factor is None else math.inf, None, None, None, None, None)
    index = np.nonzero(chosen)[0]
    k = index[np.argmin(ratios[index])]
    value = float(ratios[k])
    e = element[k]
    return FeCheck(name, value, value / envelope.ultimate_factor - 1, None if envelope.proof_factor is None else value / envelope.proof_factor - 1,
                   str(parts[k]), float(centroid[e, 1]), float(centroid[e, 0]), None if math.isnan(angle[k]) else float(angle[k]), str(modes[k]))


# ---------------------------------------------------------------------------------------------------------------- modes

VIBRATION_MODES = 6
LOCAL = 0.2  # a mode whose tip moves less than this part of its largest motion is a local one, a panel's or a rib's
PANEL_RITZ_TERMS = 12  # sine terms per direction in a panel's buckling series


@dataclass(frozen=True)
class Mode:
    number: int
    frequency_Hz: float
    kind: str  # "bending", "torsion", "fore and aft" or "local"
    part: str  # the part that moves most


@dataclass(frozen=True)
class ModeResults:
    modes: tuple[Mode, ...]
    solve_seconds: float


@dataclass(frozen=True)
class FeBuckling:
    """The panel that buckles first under one case: a skin or web bay, simply supported, under its own loads from the model."""

    case: LoadCase
    factor: float  # times the case's limit load at which the panel buckles
    margin_ultimate: float
    part: str
    station_m: float  # the middle of the bay, from the root
    loads: tuple[float, float, float]  # the bay's mean Nx, Ny, Nxy at limit load, N/m, tension positive, in its ply axes


def case_load(model: WingModel, case: LoadCase) -> np.ndarray:
    """The vertical nodal forces of one flight case at limit load: the patterns times the case's factors."""
    factors = case_factors(case, model.wing, model.envelope)
    return sum(factors[name] * force for name, force in model.patterns.items())


TIE = 1e-9  # root moments this close, relative to the largest, are the same moment (two corners at one load factor)


def buckling_cases(model: WingModel) -> list[LoadCase]:
    """The cases with the largest upward and the largest downward root bending moment, those that load each skin hardest in
    compression. Corners at the same load factor have the same moment and differ in torsion, so all of a tie are taken: picking
    one by the last digit would change with the machine. A case whose loads repeat one already taken (the same corner at another
    altitude) is left out."""
    cases, _ = flight_cases(model.envelope, model.wing.geometry.chord_m)
    if not cases:
        return []
    y = model.mesh.nodes[:, 1]
    loads = [case_load(model, case) for case in cases]
    moment = np.array([float(load @ y) for load in loads])
    tie = TIE * np.abs(moment).max()
    keep = moment >= moment.max() - tie
    if moment.min() < 0:
        keep |= moment <= moment.min() + tie
    chosen: list[int] = []
    for k in np.nonzero(keep)[0]:
        if not any(np.allclose(loads[k], loads[j], rtol=TIE, atol=TIE * np.abs(loads[j]).max()) for j in chosen):
            chosen.append(int(k))
    return [cases[k] for k in chosen]


def write_modes_deck(model: WingModel) -> str:
    """The deck for the vibration modes: the structure's own mass, nothing else."""
    out = _model_lines(model)
    out += ["** Vibration modes", "*STEP", "*FREQUENCY", str(VIBRATION_MODES), "*NODE PRINT, NSET=NALL", "U", "*END STEP"]
    return "\n".join(out) + "\n"


def _node_parts(model: WingModel) -> np.ndarray:
    parts = np.empty(model.mesh.nodes.shape[0], dtype=object)
    for k, nodes in enumerate(model.mesh.elements):
        parts[nodes] = model.part_of[k]
    return parts


def _shape(block: list[str], n: int) -> np.ndarray:
    values = np.array([[float(v) for v in line.split()[:4]] for line in block])
    u = np.zeros((n, 3))
    u[values[:, 0].astype(int) - 1] = values[:, 1:4]
    return u


def classify_mode(model: WingModel, u: np.ndarray, node_parts: np.ndarray) -> tuple[str, str]:
    """What a mode shape does at the tip, measured on the webs: heave, pitch (as the motion it gives half a chord away) or fore and aft."""
    front, rear, x_front, x_rear = _tip(model)
    w_front, w_rear = float(u[front, 2].mean()), float(u[rear, 2].mean())
    heave = abs(w_front + w_rear) / 2
    pitch = abs(w_front - w_rear) / (x_rear - x_front) * model.wing.geometry.chord_m / 2
    fore = abs(float(u[np.r_[front, rear], 0].mean()))
    size = np.linalg.norm(u, axis=1)
    part = str(node_parts[int(np.argmax(size))])
    if max(heave, pitch, fore) < LOCAL * size.max():
        return "local", part
    return ("bending" if heave >= max(pitch, fore) else "torsion" if pitch >= fore else "fore and aft"), part


def read_modes(model: WingModel, dat: str, solve_seconds: float = 0.0) -> ModeResults:
    n, parts = model.mesh.nodes.shape[0], _node_parts(model)
    table = dat.split("E I G E N V A L U E   O U T P U T")[1].split("P A R T I C I P A T I O N")[0]
    rows = [line.split() for line in table.splitlines() if line.strip() and line.split()[0].isdigit()]
    shapes = _blocks(dat, "displacements")
    if len(rows) != VIBRATION_MODES or len(shapes) != VIBRATION_MODES:
        raise WingModelError(f"CalculiX printed {len(rows)} frequencies and {len(shapes)} mode shapes for {VIBRATION_MODES} modes")
    modes = []
    for row, block in zip(rows, shapes):
        kind, part = classify_mode(model, _shape(block, n), parts)
        modes.append(Mode(int(row[0]), float(row[3]), kind, part))
    return ModeResults(tuple(modes), solve_seconds)


def run_modes(model: WingModel, workdir: Path | str | None = None, ccx: str | None = None, threads: int = 4,
              timeout_s: float = 3600.0) -> ModeResults:
    """Solve the wing's first vibration modes."""
    folder = Path(tempfile.mkdtemp(prefix="wing-modes-")) if workdir is None else Path(workdir)
    folder.mkdir(parents=True, exist_ok=True)
    deck = folder / "wing-modes.inp"
    deck.write_text(write_modes_deck(model), encoding="utf-8")
    result = run_calculix(deck, ccx=ccx, workdir=folder, timeout_s=timeout_s, threads=threads)
    return read_modes(model, result.dat_text, result.elapsed_s)


def element_loads(model: WingModel, stress: np.ndarray, results: PatternResults) -> np.ndarray:
    """Each element's in-plane resultants (Nx, Ny, Nxy) in its ply axes (x the 0 degree direction), N/m: every layer's stress
    turned from its fibre axes and multiplied by its thickness, the layer's points averaged."""
    element, layer = results.point_element, results.point_layer
    parts = model.part_of[element]
    angle = np.radians([model.layers[layup_of(p)][j].angle_deg for p, j in zip(parts, layer)])
    weight = np.array([model.layers[layup_of(p)][j].thickness_m for p, j in zip(parts, layer)]) / (POINTS_IN_PLANE * POINTS_PER_LAYER)
    c, s_ = np.cos(angle), np.sin(angle)
    s1, s2, t12 = stress[:, 0], stress[:, 1], stress[:, 3]
    local = np.c_[s1 * c**2 + s2 * s_**2 - 2 * t12 * s_ * c, s1 * s_**2 + s2 * c**2 + 2 * t12 * s_ * c, (s1 - s2) * s_ * c + t12 * (c**2 - s_**2)]
    out = np.zeros((model.mesh.elements.shape[0], 3))
    np.add.at(out, element, local * weight[:, None])
    return out


def bays(model: WingModel) -> list[tuple[str, np.ndarray, float, float, float]]:
    """The skin and web panels between ribs, inside the box: (part, elements, length along the span, width, middle station).
    Without ribs a web is one panel the length of the span, and a skin one panel too."""
    wing, mesh = model.wing, model.mesh
    stations = rib_stations(wing) or (0.0, wing.geometry.half_span_m)
    centre = mesh.nodes[mesh.elements[:, :4]].mean(axis=1)
    x_front, x_rear = model.section.spar_x_m
    heights = [top - bottom for top, bottom in zip(model.section.spar_top_m, model.section.spar_bottom_m)]
    out = []
    for y0, y1 in zip(stations[:-1], stations[1:]):
        inside = (centre[:, 1] > y0) & (centre[:, 1] < y1)
        for part, width in (("Front spar", heights[0]), ("Rear spar", heights[1])):
            out.append((part, np.nonzero(inside & (model.part_of == part))[0], y1 - y0, width, (y0 + y1) / 2))
        for part in SKINS:
            chosen = inside & (model.part_of == part) & (centre[:, 0] > x_front) & (centre[:, 0] < x_rear)
            out.append((part, np.nonzero(chosen)[0], y1 - y0, x_rear - x_front, (y0 + y1) / 2))
    return [bay for bay in out if bay[1].size]


def panel_buckling(model: WingModel, results: PatternResults, cases: list[LoadCase]) -> list[FeBuckling]:
    """Under each case, the bay that buckles first: its mean in-plane loads from the model, the plate simply supported on its four
    edges (the engine's Ritz series with the laminate's bending-twisting coupling). CalculiX's own eigenvalue buckling is not
    used: on the joined shells of a wing it missed the web's buckle (ADR-0117). A web's mean load leaves out its own bending
    stress, so for a web this is not a lower bound; the hand calculation's web check is the one to trust (fea theory, 10.4)."""
    from anisotropy_engine.buckling import ritz_buckling
    from anisotropy_engine.wing.section import WEB_PANEL_ASPECT, member_laminate

    D = {name: member_laminate(layup).D for name, layup in (("skin", model.wing.skin), ("spar", model.wing.spar))}
    area = 0.5 * np.linalg.norm(np.cross(*(model.mesh.nodes[model.mesh.elements[:, [2, 3]]] - model.mesh.nodes[model.mesh.elements[:, [0, 1]]]).transpose(1, 0, 2)), axis=1)
    panels = bays(model)
    out = []
    for case in cases:
        factors = case_factors(case, model.wing, model.envelope)
        loads = element_loads(model, sum(factors[name] * results.stress[name] for name in model.patterns), results)
        best = None
        for part, members, length, width, middle in panels:
            mean = (area[members] @ loads[members]) / area[members].sum()
            stiffness = D[layup_of(part)]
            plate_length = min(length, WEB_PANEL_ASPECT * width) if part in WEBS else length
            try:
                factor = ritz_buckling(stiffness, plate_length, width, mean, PANEL_RITZ_TERMS).load_factor
            except ValueError:  # nothing compresses the panel
                continue
            if best is None or factor < best[0]:
                best = (factor, part, middle, tuple(float(v) for v in mean))
        if best is not None:
            out.append(FeBuckling(case, best[0], best[0] / model.envelope.ultimate_factor - 1, best[1], best[2], best[3]))
    return out


# ---------------------------------------------------------------------------------------------------------------- aeroelastic

@dataclass(frozen=True)
class FeSection:
    """What the static solutions and the mesh say about the wing as a beam, per unit span, SI units."""

    shear_center_m: float  # from the leading edge: where a lift twists nothing
    torsion_stiffness: float  # GJ from the tip twist under the uniform moment
    mass_per_length_kg_m: float
    center_of_mass_m: float  # from the leading edge
    pitch_inertia_kg_m: float  # about the shear center, per unit span


def fe_section(model: WingModel, results: PatternResults) -> FeSection:
    """The beam the finite element wing behaves as. A uniform moment of 1 N*m per metre twists the tip by L^2 / (2 GJ); the
    lift pattern, acting at the aerodynamic center, twists it nose up by e times its root bending moment over GJ (e the
    distance from the aerodynamic center back to the shear center), so the two twists give both GJ and e."""
    wing, mesh = model.wing, model.mesh
    L = wing.geometry.half_span_m
    front, rear, x_front, x_rear = _tip(model)

    def tip_twist(name: str) -> float:
        u = results.displacement[name]
        return (float(u[front, 2].mean()) - float(u[rear, 2].mean())) / (x_rear - x_front)
    twist_moment, twist_lift = tip_twist("moment"), tip_twist("lift")
    GJ = L**2 / (2 * twist_moment)
    root_moment = float(model.patterns["lift"] @ mesh.nodes[:, 1])
    shear_center = wing.aerodynamics.aerodynamic_center * wing.geometry.chord_m + twist_lift * GJ / root_moment
    corners = mesh.nodes[mesh.elements[:, :4]]
    area = 0.5 * np.linalg.norm(np.cross(corners[:, 2] - corners[:, 0], corners[:, 3] - corners[:, 1]), axis=1)
    layups = {"skin": wing.skin, "spar": wing.spar, "rib": wing.rib}
    areal = {name: layup.fiber_thickness_m * layup.material.density_kg_m3 + layup.core_thickness_m * (layup.core_density_kg_m3 or 0.0)
             for name, layup in layups.items() if layup is not None}
    mass = area * np.array([areal[layup_of(part)] for part in model.part_of])
    centre = corners.mean(axis=1)
    total = float(mass.sum())
    x_cg, z_cg = float(mass @ centre[:, 0]) / total, float(mass @ centre[:, 2]) / total
    inertia = float(mass @ ((centre[:, 0] - shear_center) ** 2 + (centre[:, 2] - z_cg) ** 2))
    return FeSection(shear_center, GJ, total / L, x_cg, inertia / L)


def typical_section(model: WingModel, section: FeSection, modes: ModeResults) -> TypicalSection | None:
    """The flutter strip from the finite element wing: its mass, the shear center as the elastic axis, the first bending and
    first torsion frequencies. None when the modes found hold no torsion mode."""
    bending = next((m for m in modes.modes if m.kind == "bending"), None)
    torsion = next((m for m in modes.modes if m.kind == "torsion"), None)
    if bending is None or torsion is None:
        return None
    b = model.wing.geometry.chord_m / 2
    return TypicalSection(semichord_m=b, elastic_axis=(section.shear_center_m - b) / b, mass_offset=(section.center_of_mass_m - section.shear_center_m) / b,
                          radius_of_gyration=math.sqrt(section.pitch_inertia_kg_m / section.mass_per_length_kg_m) / b,
                          mass_per_length_kg_m=section.mass_per_length_kg_m, bending_frequency_Hz=bending.frequency_Hz,
                          torsion_frequency_Hz=torsion.frequency_Hz)


def flutter_by_altitude(strip: TypicalSection, envelope: FlightEnvelope) -> list[tuple[float, FlutterResult, float]]:
    """The flutter estimate at each altitude of the envelope: (altitude, result, the flutter speed in the envelope's airspeed)."""
    out = []
    for altitude in envelope.altitudes_m:
        result = flutter_speed(strip, air_density(altitude))
        speed = result.speed_m_s * (math.sqrt(density_ratio(altitude)) if envelope.airspeed == "equivalent" else 1.0)
        out.append((altitude, result, speed))
    return out


# ---------------------------------------------------------------------------------------------------------------- command

def _outboard_ratio(y: np.ndarray, ratio: np.ndarray, start_m: float) -> float:
    """The lowest of a hand calculation's station values (members, stations) from `start_m` to the tip."""
    at_start = [float(np.interp(start_m, y, row)) for row in np.atleast_2d(ratio)]
    beyond = np.atleast_2d(ratio)[:, y > start_m]
    return min(at_start + ([float(beyond.min())] if beyond.size else []))


def main(argv: list[str] | None = None) -> None:
    from anisotropy_engine.wing import analyze_wing, load_wing
    from anisotropy_engine.wing.section import box_section

    parser = argparse.ArgumentParser(prog="python -m anisotropy_fea.wing_model",
                                     description="Solve a wing file's finite element model in CalculiX and set it beside the hand calculation.")
    parser.add_argument("wing_file", type=Path)
    parser.add_argument("--mesh", type=float, default=40.0, help="element size in mm (default 40)")
    parser.add_argument("--skins", choices=SKIN_EXTENTS, default="airfoil",
                        help="the skins round the whole airfoil (default) or only between the spars, as the hand calculation counts them")
    parser.add_argument("--out", type=Path, default=None, help="folder for the deck and CalculiX's files (default: a temporary folder)")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--modes", action="store_true", help="also solve the vibration modes and the buckling of the hardest cases")
    args = parser.parse_args(argv)
    _, wing, envelope = load_wing(args.wing_file)
    try:
        model = build_wing_model(wing, envelope, args.mesh * MM, skins=args.skins)
    except (WingModelError, ShapeError) as error:
        sys.exit(str(error))
    print(f"{wing.name}, skins {args.skins}: {model.mesh.elements.shape[0]} S8R shells, {model.mesh.nodes.shape[0]} nodes at {args.mesh:g} mm, "
          f"{len(model.groups)} ply groups, {len(model.patterns)} load patterns; built in {model.build_seconds:.1f} s")
    results = run_wing_model(model, args.out, threads=args.threads)
    print(f"CalculiX: {results.equations} equations, {results.solve_seconds:.1f} s for {len(model.patterns)} load patterns")
    hand = analyze_wing(wing, envelope)
    by_case = {(c.case.number, c.case.altitude_m): c for c in hand.cases}
    fe = fe_cases(model, results, box_section(wing).shear_center_m)
    zone = root_zone(model)
    ultimate = envelope.ultimate_factor

    def margin(value):
        return "" if value is None else ("inf" if not math.isfinite(value) else f"{value:+.3f}")

    print(f"Margins at ultimate load from {zone * 1000:.0f} mm outboard of the root (the deeper web's height); the root's own after the bar.")
    print(f"{'case':<42}{'tip mm':>16}{'twist deg':>18}{'skin plies':>20}{'spar plies':>20}{'rib plies':>11}{'core shear':>11}{'| at the root':>16}")
    print(f"{'':<42}{'hand':>8}{'FE':>8}{'hand':>9}{'FE':>9}{'hand':>10}{'FE':>10}{'hand':>10}{'FE':>10}{'FE':>11}{'FE':>11}{'hand':>9}{'FE':>9}")
    for c in fe:
        h = by_case[(c.case.number, c.case.altitude_m)]
        checks = {check.name: check.margin_ultimate for check in c.checks}
        st = h.stations
        hand_skin = _outboard_ratio(st.y, st.skin_ratio, zone) / ultimate - 1
        hand_spar = _outboard_ratio(st.y, st.spar_ratio, zone) / ultimate - 1
        hand_root = min(ch.margin_ultimate for ch in h.checks if ch.name != "skin buckling")
        fe_root = min(ch.margin_ultimate for ch in c.root_checks)
        print(f"{c.case.number:>3} {c.case.label:<32}{c.case.altitude_m:>6.0f}"
              f"{h.tip_deflection * 1000:>8.1f}{c.tip_deflection_m * 1000:>8.1f}{math.degrees(h.tip_twist):>9.3f}{math.degrees(c.tip_twist_rad):>9.3f}"
              f"{margin(hand_skin):>10}{margin(checks.get('skin plies')):>10}{margin(hand_spar):>10}{margin(checks.get('spar plies')):>10}"
              f"{margin(checks.get('rib plies')):>11}{margin(checks.get('core shear')):>11}{margin(hand_root):>9}{margin(fe_root):>9}")

    def describe(label, worst, g):
        where = f"{g.part}, {g.station_m * 1000:.0f} mm from the root, {g.chord_m * 1000:.0f} mm from the leading edge"
        print(f"{label}: {g.margin_ultimate:+.3f}, case {worst.case.number} ({worst.case.label}), {g.name}: {where}"
              + (f", {g.ply_angle_deg:g} degree ply" if g.ply_angle_deg is not None else "") + f", {g.mode}")
    worst = min(fe, key=lambda c: c.governing.margin_ultimate)
    describe("Lowest FE margin outboard of the root zone", worst, worst.governing)
    at_root = min(fe, key=lambda c: min(ch.margin_ultimate for ch in c.root_checks))
    describe("Lowest FE margin anywhere, the clamped root included", at_root, min(at_root.root_checks, key=lambda ch: ch.margin_ultimate))
    if not args.modes:
        return
    modes = run_modes(model, args.out, threads=args.threads)
    print(f"Vibration modes: {modes.solve_seconds:.1f} s. The hand calculation's first bending frequency: "
          f"{hand.section.first_bending_frequency_Hz:.2f} Hz")
    for mode in modes.modes:
        print(f"  mode {mode.number}: {mode.frequency_Hz:9.2f} Hz  {mode.kind:<13} moves most: {mode.part}")
    section = fe_section(model, results)
    aero = hand.aeroelastic
    print(f"As a beam: shear center {section.shear_center_m * 1000:.1f} mm from the leading edge (hand {hand.section.shear_center_m * 1000:.1f}), "
          f"GJ {section.torsion_stiffness:.0f} N m^2 (hand {hand.section.GJ:.0f}), {section.mass_per_length_kg_m:.3f} kg/m, center of mass "
          f"{section.center_of_mass_m * 1000:.1f} mm")
    slope = wing.aerodynamics.lift_curve_slope_per_rad
    if slope is not None:
        arm = section.shear_center_m - wing.aerodynamics.aerodynamic_center * wing.geometry.chord_m
        q = divergence_dynamic_pressure(section.torsion_stiffness, wing.geometry.half_span_m, wing.geometry.chord_m, arm, slope)
        print(f"Divergence (equivalent airspeed): FE {equivalent_airspeed(q):.1f} m/s, hand {aero.divergence_speed_m_s:.1f} m/s")
    strip = typical_section(model, section, modes)
    if strip is None:
        print("Flutter: no torsion mode among the first modes found")
    else:
        required = envelope.speeds.flutter
        print(f"Flutter strip: a {strip.elastic_axis:+.3f}, x_theta {strip.mass_offset:+.3f}, r {strip.radius_of_gyration:.3f}, "
              f"bending {strip.bending_frequency_Hz:.2f} Hz, torsion {strip.torsion_frequency_Hz:.2f} Hz"
              + ("" if required is None else f"; the envelope's flutter speed {required:.1f} m/s ({envelope.airspeed})"))
        for altitude, result, speed in flutter_by_altitude(strip, envelope):
            if math.isinf(speed):
                print(f"  {altitude:6.0f} m: no flutter in the sweep (mu {result.mass_ratio:.1f})")
            else:
                print(f"  {altitude:6.0f} m: flutter at {speed:.1f} m/s {envelope.airspeed}, {result.frequency_Hz:.2f} Hz, k {result.reduced_frequency:.3f}, "
                      f"mu {result.mass_ratio:.1f}" + ("" if required is None else f"; {speed / required:.2f} times the envelope's"))
    for b in panel_buckling(model, results, buckling_cases(model)):
        hand_checks = {ch.name: ch for ch in by_case[(b.case.number, b.case.altitude_m)].checks}
        print(f"  buckling under case {b.case.number} ({b.case.label}): {b.part} bay at {b.station_m * 1000:.0f} mm, {b.factor:.3f} times limit load, "
              f"margin at ultimate {b.margin_ultimate:+.3f} (hand: skin {margin(hand_checks['skin buckling'].margin_ultimate)}, "
              f"web {margin(hand_checks['web buckling'].margin_ultimate)}); Nx, Ny, Nxy at limit {', '.join(f'{v:.0f}' for v in b.loads)} N/m")


if __name__ == "__main__":
    main()
