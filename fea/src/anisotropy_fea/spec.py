"""Coupon model specifications: everything a finite element model is made from, stated in one TOML file (ADR-0030).

A spec names the coupon kind, its dimensions, the mesh controls, the layup, the material (from the engine's
cited library or explicit constants, with the out-of-plane constants every deck needs), the grips, the loading,
probe points and the output requests. Numbers are written in the spec's `units` and converted to SI once at
load (ADR-0002). Every key is required unless a default is stated here, and every invalid combination is
refused by name (ADR-0003). The spec is the source of the generated decks; a deck is never edited by hand.
"""

from __future__ import annotations

import hashlib
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, PositiveFloat, ValidationError

from anisotropy_engine.failure import CRITERIA
from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.library import library_material

from .units import unit_factors

Kind = Literal["unnotched_tension", "open_hole_tension", "compression", "shear_pm45", "three_point_bending", "four_point_bending"]
BENDING_KINDS = ("three_point_bending", "four_point_bending")
IN_PLANE_KINDS = ("unnotched_tension", "open_hole_tension", "compression", "shear_pm45")
LINE_TOLERANCE = 1e-9  # relative to the length: a node row must sit on a tab or support line within this


class SpecError(ValueError):
    """The spec is incomplete, inconsistent, or asks for something this version does not build."""


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Geometry(Record):
    length: PositiveFloat  # total length along the loading axis y, tabs included
    width: PositiveFloat  # along x
    tab_length: float | None = None  # in-plane kinds: gripped length at each end; 0 means no tabs
    hole_diameter: PositiveFloat | None = None  # open_hole_tension only
    span: PositiveFloat | None = None  # bending kinds: distance between the support lines
    overhang: float | None = None  # bending kinds: length = span + 2 * overhang is checked, not derived
    load_span: PositiveFloat | None = None  # four_point_bending only: distance between the loading-nose lines


class HoleMesh(Record):
    circumferential: int  # nodes around the hole, a multiple of 4
    radial_layers: int
    ring_ratio: float  # inner-square half-side = ring_ratio * hole radius
    growth: float  # radial progression coefficient


class MeshControls(Record):
    mesher: Literal["structured", "gmsh"]
    element_order: Literal[1, 2]
    element_size: PositiveFloat | None = None  # exactly one of element_size or (nx, ny)
    nx: int | None = None
    ny: int | None = None
    hole: HoleMesh | None = None


class Layup(Record):
    angles: list[float]  # bottom-first (ADR-0004); the lower half when symmetric
    symmetric: bool
    ply_thickness: PositiveFloat | Literal["library"]


class Transverse(Record):
    """Out-of-plane constants: Abaqus LAMINA needs G13 and G23; CalculiX ENGINEERING CONSTANTS also needs E3, nu13, nu23."""

    G13: PositiveFloat
    G23: PositiveFloat
    nu23: float
    transverse_isotropy: bool  # true: E3 = E2 and nu13 = nu12, a stated rule; false: E3 and nu13 must be given
    E3: PositiveFloat | None = None
    nu13: float | None = None


class MaterialSpec(Record):
    library: str | None = None  # engine library material id; with it, no explicit constants
    dataset: str | None = None  # the library's primary dataset when absent
    E1: PositiveFloat | None = None
    E2: PositiveFloat | None = None
    G12: PositiveFloat | None = None
    nu12: float | None = None
    F1t: PositiveFloat | None = None
    F1c: PositiveFloat | None = None
    F2t: PositiveFloat | None = None
    F2c: PositiveFloat | None = None
    F6: PositiveFloat | None = None
    f12_star: float | None = None  # Tsai-Wu interaction term; required when tsai_wu is requested; written as the sixth *Fail Stress value
    transverse: Transverse


class Grips(Record):
    kind: Literal["nodal", "coupling"]  # nodal: constraints on the grip node sets; coupling: reference nodes with kinematic couplings
    region: Literal["line", "tabs"]  # line: the end node rows only; tabs: every node within tab_length of each end (the team's decks)


class Loading(Record):
    control: Literal["displacement", "force"]
    value: float  # displacement: length at the moving grip (negative = compression); force: total force; bending: nose displacement (dof 3)


class Probes(Record):
    nodes: dict[str, tuple[float, float]] = {}
    elements: dict[str, tuple[float, float]] = {}


class AbaqusOutput(Record):
    field_preselect: bool
    node_print: bool
    el_print: bool


class CalculixOutput(Record):
    node_print: bool
    el_print: bool
    frd: bool
    el_print_global: bool


class OutputRequests(Record):
    fpf_criteria: list[str]
    abaqus: AbaqusOutput
    calculix: CalculixOutput


class CouponSpec(Record):
    title: str
    kind: Kind
    units: str  # the unit system of this file and of every deck written from it
    geometry: Geometry
    mesh: MeshControls
    layup: Layup
    material: MaterialSpec
    loading: Loading
    output: OutputRequests
    grips: Grips | None = None  # required for in-plane kinds, absent for bending
    probes: Probes = Probes()
    source_sha256: str = ""
    source_path: str | None = None
    si: bool = False  # True once `to_si` has run


# --- loading and validation --------------------------------------------------------------------


def parse_spec(text: str, source_path: str | None = None) -> CouponSpec:
    """The spec exactly as written (its own units), validated for completeness and consistency."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise SpecError(f"spec is not valid TOML: {exc}") from None
    data["source_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    data["source_path"] = source_path
    try:
        spec = CouponSpec(**data)
    except ValidationError as exc:
        problems = "; ".join(".".join(str(part) for part in error["loc"]) + ": " + error["msg"] for error in exc.errors())
        raise SpecError(f"spec: {problems}") from None
    validate_spec(spec)
    return spec


def load_spec(path: Path | str) -> CouponSpec:
    """Read, validate and convert a spec file to SI."""
    path = Path(path)
    return to_si(parse_spec(path.read_text(encoding="utf-8"), source_path=str(path)))


def validate_spec(spec: CouponSpec) -> None:
    """Cross-field rules. Works on the spec in its own units or in SI."""
    unit_factors(spec.units)
    g, m, kind = spec.geometry, spec.mesh, spec.kind
    bending = kind in BENDING_KINDS

    def need(condition: bool, message: str) -> None:
        if not condition:
            raise SpecError(message)

    # geometry keys per kind
    need((g.hole_diameter is None) == (kind != "open_hole_tension"), "geometry.hole_diameter is required for open_hole_tension and refused for every other kind")
    need((m.hole is None) == (kind != "open_hole_tension"), "[mesh.hole] is required for open_hole_tension and refused for every other kind")
    if bending:
        need(g.span is not None and g.overhang is not None, "bending kinds need geometry.span and geometry.overhang")
        need(g.tab_length is None, "bending kinds take no geometry.tab_length")
        need(spec.grips is None, "bending kinds take no [grips] table: the supports and noses are the constraints")
        need(spec.loading.control == "displacement", "bending kinds take loading.control = \"displacement\" (force control is a planned extension)")
        need(g.overhang >= 0, "geometry.overhang must be zero or positive")
        need(math.isclose(g.length, g.span + 2 * g.overhang, rel_tol=1e-9), f"geometry.length ({g.length:g}) must equal span + 2 overhang ({g.span + 2 * g.overhang:g}); it is checked, not derived")
        need((g.load_span is not None) == (kind == "four_point_bending"), "geometry.load_span is required for four_point_bending and refused otherwise")
        if g.load_span is not None:
            need(g.load_span < g.span, "geometry.load_span must be smaller than the span")
    else:
        need(g.span is None and g.overhang is None and g.load_span is None, "span, overhang and load_span belong to bending kinds only")
        need(g.tab_length is not None, "in-plane kinds need geometry.tab_length (0 for no tabs)")
        need(g.tab_length >= 0 and 2 * g.tab_length < g.length, "geometry.tab_length must be zero or positive and the two tabs shorter than the length")
        need(spec.grips is not None, "in-plane kinds need a [grips] table with kind = \"nodal\" or \"coupling\" and region = \"line\" or \"tabs\"")
        if spec.grips is not None and spec.grips.region == "tabs":
            need(g.tab_length > 0, "grips.region = \"tabs\" needs a positive geometry.tab_length")
    if g.hole_diameter is not None:
        need(g.hole_diameter < g.width, "geometry.hole_diameter must be smaller than the width")
        need(m.mesher == "gmsh", "open_hole_tension needs mesh.mesher = \"gmsh\"; the structured mesher cannot cut a hole")
        hole = m.hole
        need(hole.circumferential >= 8 and hole.circumferential % 4 == 0, "mesh.hole.circumferential must be a multiple of 4, at least 8")
        need(hole.radial_layers >= 1 and hole.growth >= 1.0, "mesh.hole.radial_layers must be at least 1 and growth at least 1")
        need(hole.ring_ratio > 1.0 and hole.ring_ratio * g.hole_diameter / 2 < g.width / 2, "mesh.hole.ring_ratio must exceed 1 and keep the inner square inside the width")
    # mesh counts
    need((m.element_size is None) != (m.nx is None and m.ny is None), "give mesh.element_size or both mesh.nx and mesh.ny, not both and not neither")
    need((m.nx is None) == (m.ny is None), "mesh.nx and mesh.ny go together")
    if m.nx is not None:
        need(m.nx >= 1 and m.ny >= 1, "mesh.nx and mesh.ny must be at least 1")
    if m.mesher == "structured":
        nx, ny = mesh_counts(spec)
        lines = node_lines(spec)
        bad = [name for name, y in lines.items() if not on_a_row(y, g.length, ny)]
        if bad:
            raise SpecError(f"mesh.ny = {ny} puts no node row on the line(s) {bad} (y = {[f'{lines[b]:g}' for b in bad]}); "
                            f"admissible ny near {ny}: {admissible_ny(g.length, list(lines.values()), ny)}")
    # layup
    need(len(spec.layup.angles) >= 1, "layup.angles must list at least one ply")
    if kind == "shear_pm45":
        angles = full_angles(spec)
        need(all(abs(abs(a) - 45.0) < 1e-9 for a in angles), "shear_pm45 needs every ply at +45 or -45 degrees")
        need(sum(a > 0 for a in angles) == sum(a < 0 for a in angles), "shear_pm45 needs a balanced layup: as many +45 as -45 plies")
    # material
    mat = spec.material
    explicit = [mat.E1, mat.E2, mat.G12, mat.nu12]
    if mat.library is not None:
        need(all(v is None for v in explicit + [mat.F1t, mat.F1c, mat.F2t, mat.F2c, mat.F6]), "material.library excludes explicit constants and strengths")
    else:
        need(all(v is not None for v in explicit), "material needs library or all of E1, E2, G12, nu12")
        need(mat.dataset is None, "material.dataset goes with material.library")
        strengths = [mat.F1t, mat.F1c, mat.F2t, mat.F2c, mat.F6]
        need(all(v is not None for v in strengths) or all(v is None for v in strengths), "give all five strengths F1t, F1c, F2t, F2c, F6 or none")
    t = mat.transverse
    if t.transverse_isotropy:
        need(t.E3 is None and t.nu13 is None, "material.transverse: with transverse_isotropy = true, E3 and nu13 are derived (E3 = E2, nu13 = nu12); do not give them")
    else:
        need(t.E3 is not None and t.nu13 is not None, "material.transverse: with transverse_isotropy = false, E3 and nu13 are required")
    # loading
    need(spec.loading.value != 0, "loading.value must not be zero")
    if kind == "compression":
        need(spec.loading.value < 0, "compression needs a negative loading.value (a positive value is a tension coupon)")
    if kind in ("unnotched_tension", "open_hole_tension", "shear_pm45"):
        need(spec.loading.value > 0, f"{kind} needs a positive loading.value")
    # output
    for criterion in spec.output.fpf_criteria:
        need(criterion in CRITERIA, f"output.fpf_criteria: unknown criterion {criterion!r}; known: {', '.join(CRITERIA)}")
        need(criterion != "max_strain", "output.fpf_criteria: max_strain is refused; a deck carries no strain limits")
    if "tsai_wu" in spec.output.fpf_criteria:
        need(mat.f12_star is not None, "output.fpf_criteria asks for tsai_wu, so material.f12_star is required (ADR-0021)")
    if mat.f12_star is not None:
        need(-1.0 < mat.f12_star < 1.0, "material.f12_star must lie strictly between -1 and 1")
    # probes inside the coupon
    for group, probes in (("nodes", spec.probes.nodes), ("elements", spec.probes.elements)):
        for name, (x, y) in probes.items():
            need(0 <= x <= g.width and 0 <= y <= g.length, f"probes.{group} {name!r} at ({x:g}, {y:g}) lies outside the coupon")


def full_angles(spec: CouponSpec) -> list[float]:
    angles = list(spec.layup.angles)
    return angles + angles[::-1] if spec.layup.symmetric else angles


def mesh_counts(spec: CouponSpec) -> tuple[int, int]:
    m, g = spec.mesh, spec.geometry
    if m.nx is not None:
        return m.nx, m.ny
    return max(1, math.ceil(g.width / m.element_size - 1e-9)), max(1, math.ceil(g.length / m.element_size - 1e-9))


def node_lines(spec: CouponSpec) -> dict[str, float]:
    """The y lines that must coincide with node rows: tab boundaries, support lines, loading-nose lines."""
    g = spec.geometry
    lines: dict[str, float] = {}
    if spec.kind in BENDING_KINDS:
        lines["Support-Left"] = g.overhang
        lines["Support-Right"] = g.length - g.overhang
        if spec.kind == "three_point_bending":
            lines["Nose"] = g.length / 2
        else:
            lines["Nose-1"] = g.length / 2 - g.load_span / 2
            lines["Nose-2"] = g.length / 2 + g.load_span / 2
    elif g.tab_length:
        lines["Tab-Bottom-Line"] = g.tab_length
        lines["Tab-Top-Line"] = g.length - g.tab_length
    return lines


def on_a_row(y: float, length: float, ny: int) -> bool:
    position = y / length * ny
    return abs(position - round(position)) <= LINE_TOLERANCE * ny


def admissible_ny(length: float, lines: list[float], near: int, window: int = 12) -> list[int]:
    return [ny for ny in range(max(1, near - window), near + window + 1) if all(on_a_row(y, length, ny) for y in lines)]


# --- units --------------------------------------------------------------------------------------


def to_si(spec: CouponSpec) -> CouponSpec:
    """Every dimensioned number converted from the spec's units to SI base units; `si` set."""
    if spec.si:
        return spec
    f = unit_factors(spec.units)
    L, S, F = f["length"], f["stress"], f["force"]
    scale = lambda v, k: None if v is None else v * k  # noqa: E731
    g = spec.geometry.model_copy(update={"length": spec.geometry.length * L, "width": spec.geometry.width * L,
                                         "tab_length": scale(spec.geometry.tab_length, L), "hole_diameter": scale(spec.geometry.hole_diameter, L),
                                         "span": scale(spec.geometry.span, L), "overhang": scale(spec.geometry.overhang, L),
                                         "load_span": scale(spec.geometry.load_span, L)})
    m = spec.mesh.model_copy(update={"element_size": scale(spec.mesh.element_size, L)})
    layup = spec.layup.model_copy(update={"ply_thickness": spec.layup.ply_thickness if spec.layup.ply_thickness == "library" else spec.layup.ply_thickness * L})
    t = spec.material.transverse
    transverse = t.model_copy(update={"G13": t.G13 * S, "G23": t.G23 * S, "E3": scale(t.E3, S)})
    mat = spec.material.model_copy(update={"E1": scale(spec.material.E1, S), "E2": scale(spec.material.E2, S), "G12": scale(spec.material.G12, S),
                                           "F1t": scale(spec.material.F1t, S), "F1c": scale(spec.material.F1c, S), "F2t": scale(spec.material.F2t, S),
                                           "F2c": scale(spec.material.F2c, S), "F6": scale(spec.material.F6, S), "transverse": transverse})
    loading = spec.loading.model_copy(update={"value": spec.loading.value * (L if spec.loading.control == "displacement" else F)})
    probes = spec.probes.model_copy(update={"nodes": {k: (x * L, y * L) for k, (x, y) in spec.probes.nodes.items()},
                                            "elements": {k: (x * L, y * L) for k, (x, y) in spec.probes.elements.items()}})
    return spec.model_copy(update={"geometry": g, "mesh": m, "layup": layup, "material": mat, "loading": loading, "probes": probes, "si": True})


# --- what the model takes from the spec ---------------------------------------------------------


@dataclass(frozen=True)
class MaterialDefinition:
    """One material, SI, with every constant a deck may need and where the numbers come from."""

    name: str
    E1: float
    E2: float
    nu12: float
    G12: float
    G13: float
    G23: float
    E3: float
    nu13: float
    nu23: float
    strengths: Strengths | None
    f12_star: float | None
    source: str  # "library im7-8552 / <dataset>" or "explicit constants in the spec"
    rights: str  # the library's rights class, or "spec" for explicit constants
    citation_lines: tuple[str, ...]  # one line per value, for the deck header

    @property
    def lamina(self) -> Lamina:
        return Lamina(E1=self.E1, E2=self.E2, G12=self.G12, nu12=self.nu12, strengths=self.strengths)


def spec_material(spec: CouponSpec) -> MaterialDefinition:
    """The material in SI. Library values carry their page citations; explicit constants carry none."""
    if not spec.si:
        raise SpecError("spec_material needs the spec in SI (load_spec or to_si)")
    mat = spec.material
    t = mat.transverse
    if mat.library is not None:
        try:
            lib = library_material(mat.library, mat.dataset)
        except ValueError as exc:
            raise SpecError(f"material.library: {exc}") from None
        lamina = lib.lamina
        citations = tuple(f"{v.role} = {v.source_value:g} {v.source_unit} ({v.basis}), page {v.page}: {v.reference_url}" for v in lib.values)
        source, rights, name = f"library {lib.material_id} / {lib.dataset_id} (record {lib.record_revision}; {lib.citation})", lib.rights, lib.material_id.upper()
        strengths = lamina.strengths
        E1, E2, G12, nu12 = lamina.E1, lamina.E2, lamina.G12, lamina.nu12
    else:
        E1, E2, G12, nu12 = mat.E1, mat.E2, mat.G12, mat.nu12
        strengths = Strengths(F1t=mat.F1t, F1c=mat.F1c, F2t=mat.F2t, F2c=mat.F2c, F6=mat.F6) if mat.F1t is not None else None
        citations, source, rights, name = (), "explicit constants in the spec", "spec", "EXPLICIT"
    E3 = E2 if t.transverse_isotropy else t.E3
    nu13 = nu12 if t.transverse_isotropy else t.nu13
    return MaterialDefinition(name=name, E1=E1, E2=E2, nu12=nu12, G12=G12, G13=t.G13, G23=t.G23, E3=E3, nu13=nu13, nu23=t.nu23,
                              strengths=strengths, f12_star=mat.f12_star, source=source, rights=rights, citation_lines=citations)


def spec_ply_thickness(spec: CouponSpec) -> float:
    if spec.layup.ply_thickness != "library":
        return float(spec.layup.ply_thickness)
    mat = spec.material
    if mat.library is None:
        raise SpecError("layup.ply_thickness = \"library\" needs material.library")
    lib = library_material(mat.library, mat.dataset)
    if lib.ply_thickness_m is None:
        raise SpecError(f"layup.ply_thickness = \"library\": dataset {lib.dataset_id!r} has no ply thickness ({'; '.join(lib.not_provided) or 'not provided'})")
    return lib.ply_thickness_m


def spec_plies(spec: CouponSpec) -> list[Ply]:
    """The engine plies, bottom-first, symmetric layups expanded, SI."""
    material = spec_material(spec).lamina
    thickness = spec_ply_thickness(spec)
    return [Ply(material=material, angle_deg=angle, thickness_m=thickness) for angle in full_angles(spec)]
