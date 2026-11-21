"""A stepped patch repair's slice solved in CalculiX (ADR-0132): the model built from the repair's description, the solve, and
the answer read back.

    python -m anisotropy_fea.repair_model ../engine/examples/example-patch-repair.toml [--out DIR] [--criterion tsai_hill]

The slice is the one the engine describes (ADR-0131): one half of the cut along the load through the repair's middle, r from
the middle outward and z up from the laminate's bottom face, every ply and the adhesive a part of its own. CalculiX solves it
as a plane of eight-node elements (CPE8R) in the repair's elastic state under the load. This package writes the deck and reads
the result; every stiffness in the deck and every ply stress in the answer is the engine's (ADR-0001, ADR-0067).

What the model is, part by part:

- The mesh is `slice_mesh`'s grid, graded: an eighth of the bondline's thickness long beside every step's end, cut and edge,
  growing away from them; two elements through the bondline, one through each ply. Each four-node cell becomes an eight-node
  element by a node at the middle of every edge.
- Each ply is an orthotropic solid turned to its angle, the adhesive an isotropic one (`anisotropy_engine.repair.solid`).
- Across the width the slice strains as the laminate far from the repair does: a plane element allows no strain across the
  width, so every material is given an expansion of -1 in that direction and the whole slice a temperature equal to the
  laminate's far-field width strain. The strain that makes stress across the width is then that width strain everywhere.
- The middle is a plane of symmetry (no movement along r), and the laminate's bottom face is held flat (no movement along z):
  the panel does not bend, as the hand calculation assumes and as a panel on its structure nearly does.
- The load is put on the panel's end as the stress each ply has far from the repair, so the end is the laminate theory's.
- The adhesive on the cut faces of a flush repair carries nothing unless asked (`cut_faces="open"`): those elements are left
  out, a gap one bondline wide between the end of a laminate ply and the patch ply that butts against it. That is the hand
  calculation's assumption and the safe one, since a butt joint in tension is the first thing to crack. With
  `cut_faces="bonded"` they are solved as bonded, and the stress across each is reported.

What is read back, each from the mean of an element's integration points: the force along the load in the patch, the laminate
and the adhesive at every station; the adhesive's shear and peel stress along every bond, averaged through its thickness; the
stress across every cut face; and each ply's stresses in its own axes, averaged through the ply's thickness at every station,
with its strength ratio. Averages through a thickness are what settle as the mesh is refined: the stress at the corner where
a step ends has no upper bound in an elastic solution.

A bond is a flat stretch of adhesive with the patch (or the cover plies) on it and the laminate under it. The corner of
adhesive under or over a cut face joins nothing and is not read. Where a bond ends at a square corner the elastic stress has no
upper bound at the corner itself, and the mean through the thickness rises steeply within one bondline's thickness of it: read
at the last station it would keep changing as the mesh is refined. The largest shear and the largest peel stress are therefore
means over a square of adhesive, the bondline's thickness high and as long, which settle; the curves along each bond are the
means through the thickness, station by station.

Two checks are made on every solve and refuse it: the forces at every station add up to the load, and midway between the
repair and the panel's end the strain is the laminate theory's.

With `hold="everywhere"` every node is kept from moving through the thickness. That is not a repair: it is the hand
calculation's own assumption (nothing bends, nothing peels), used to check the model against the stepped lap.
"""

from __future__ import annotations

import json
import math
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from anisotropy_engine.failure import CRITERIA, scaled_strength_ratios
from anisotropy_engine.repair import (
    FarField, Region, Repair, RepairError, StepLap, adhesive_stiffness, far_field, lap_steps, ply_axis_stress, ply_stiffness, repair_from_dict,
    repair_lap,
)
from anisotropy_engine.units import UNIT_SYSTEMS

from .calculix import CalculixError, parse_dat, run_calculix
from .repair_shape import MM, SliceMesh, slice_mesh
from .wing_shape import ShapeError

MPA = 1e6
FINE_PER_BONDLINE = 8  # the elements beside an edge are this fraction of the bondline's thickness long (ADR-0132's mesh study)
ADHESIVE_LAYERS = 2
HOLDS = ("bottom", "everywhere")
CUT_FACES = ("open", "bonded")
CHECKED_CRITERIA = ("max_stress", "tsai_hill")  # the two the slice's plies are checked by; both need only the five ply strengths
EQUILIBRIUM_TOLERANCE = 1e-4  # of the load: how far the forces at a station may be from adding up to it
FAR_FIELD_TOLERANCE = 0.01  # of the far-field strain: how far the strain midway to the panel's end may be from it
MATCH_TOLERANCE = 1e-6  # of the largest stress: how far CalculiX's stress may be from the engine's stiffness times CalculiX's strain
REPORT = "repair-solve.json"


class SliceModelError(ValueError):
    """The repair's slice cannot be solved as stated, or its solution failed one of the model's own checks."""


@dataclass(frozen=True)
class SliceModel:
    """A repair's slice as CalculiX solves it. `nodes_m` holds the mesh's corner nodes first, in the mesh's order, then one
    node at the middle of every element edge; `elements` is (m, 8), four corners then the four edge middles, as CPE8R numbers
    them. `stiffness` is each rectangle's, in the slice's axes (Pa), in the order of the mesh's rectangles."""

    repair: Repair
    load_n_per_m: float
    mesh: SliceMesh
    nodes_m: np.ndarray
    elements: np.ndarray
    stiffness: tuple[np.ndarray, ...]
    far: FarField
    hold: str
    cut_faces: str
    deck: str

    @property
    def fine_m(self) -> float:
        return float(np.min(np.diff(self.mesh.r_lines_m)))


@dataclass(frozen=True)
class SliceResults:
    """What CalculiX returned, one row for each element: the mean of its integration points. `strain` is along the load,
    through the thickness, and the engineering shear strain between them; `stress` (Pa) is along the load, across the width,
    through the thickness, and the shear stress between the load's direction and the thickness."""

    strain: np.ndarray
    stress: np.ndarray
    seconds: float
    equations: int | None
    solver: str | None


def _number(value: float) -> str:
    return f"{float(value):.12g}"


def _rows(values: list[int], per_line: int = 12) -> list[str]:
    return [", ".join(str(v) for v in values[k:k + per_line]) for k in range(0, len(values), per_line)]


def _eight_node(mesh: SliceMesh) -> tuple[np.ndarray, np.ndarray]:
    """The mesh's cells as eight-node elements: the corner nodes kept, one node added at the middle of every edge, shared by
    the two elements that meet there."""
    nodes = [tuple(point) for point in mesh.nodes_m]
    middle: dict[tuple[int, int], int] = {}
    elements = np.zeros((len(mesh.quads), 8), dtype=int)
    for e, quad in enumerate(mesh.quads):
        elements[e, :4] = quad
        for k in range(4):
            a, b = int(quad[k]), int(quad[(k + 1) % 4])
            key = (min(a, b), max(a, b))
            if key not in middle:
                middle[key] = len(nodes)
                nodes.append(tuple((mesh.nodes_m[a] + mesh.nodes_m[b]) / 2))
            elements[e, 4 + k] = middle[key]
    return np.array(nodes), elements


def is_cut_face(repair: Repair, part: Region) -> bool:
    """An adhesive rectangle up a cut face, one bondline wide, not along the slice (a ledge, the floor, under the cover
    plies or under an external patch)."""
    return part.kind == "adhesive" and part.r1 - part.r0 <= repair.adhesive.thickness_m * (1 + 1e-6)


def _without_cut_faces(repair: Repair, mesh: SliceMesh) -> SliceMesh:
    """The mesh less the elements of the adhesive on the cut faces, and less the nodes only they used."""
    keep = np.array([not is_cut_face(repair, mesh.regions[index]) for index in mesh.region])
    quads = mesh.quads[keep]
    used = np.unique(quads)
    renumber = np.full(len(mesh.nodes_m), -1)
    renumber[used] = np.arange(len(used))
    return SliceMesh(nodes_m=mesh.nodes_m[used], quads=renumber[quads], region=mesh.region[keep], regions=mesh.regions, cell=mesh.cell[keep],
                     r_lines_m=mesh.r_lines_m, z_lines_m=mesh.z_lines_m)


def region_stiffness(repair: Repair, part: Region) -> np.ndarray:
    """A rectangle's stiffness in the slice's axes, Pa: the adhesive's, or its ply's material turned to the ply's angle (a
    cover ply is of the patch's material)."""
    if part.kind == "adhesive":
        return adhesive_stiffness(repair.adhesive)
    return ply_stiffness(repair.parent_material if part.kind == "parent" else repair.patch_material, part.angle_deg)


def _deck(repair: Repair, mesh: SliceMesh, nodes: np.ndarray, elements: np.ndarray, stiffness: tuple[np.ndarray, ...], far: FarField,
          hold: str, load_n_per_m: float) -> str:
    """The CalculiX deck, in mm, N and MPa. CalculiX's x is the load's direction, its y the thickness and its z the width, so a
    stiffness's rows are renamed on the way: of the slice's (x, width, thickness), CalculiX's 1 is x, 2 the thickness and 3
    the width. Only the nine constants of *ELASTIC, TYPE=ORTHO are written: the terms that tie a turned ply's shear across the
    width to its stretching make no stress in the plane of a slice that neither shears nor moves across its width, and the
    engine puts them back when it works out the ply's own stresses."""
    out = ["** A stepped patch repair's slice (ADR-0132), written by anisotropy_fea.repair_model. Units: mm, N, MPa.",
           f"** Load {_number(load_n_per_m / 1e3)} N/mm of width; the far-field width strain {_number(far.strain_width)} is put on as a temperature.",
           "*NODE, NSET=NALL"]
    out += [f"{k + 1}, {_number(r / MM)}, {_number(z / MM)}" for k, (r, z) in enumerate(nodes)]
    groups: dict[bytes, list[int]] = {}  # the rectangles that share one stiffness share one material
    for index, matrix in enumerate(stiffness):
        groups.setdefault(np.round(matrix / MPA, 6).tobytes(), []).append(index)
    for number, members in enumerate(groups.values(), 1):
        inside = np.flatnonzero(np.isin(mesh.region, members))
        if inside.size == 0:
            continue
        c = stiffness[members[0]] / MPA  # rows and columns: xx, yy (width), zz (thickness), yz, xz, xy
        out.append(f"** Material {number}: {', '.join(mesh.regions[index].name for index in members)}")
        out.append(f"*ELEMENT, TYPE=CPE8R, ELSET=M{number}")
        out += [", ".join(str(v) for v in [e + 1, *(elements[e] + 1)]) for e in inside]
        out += [f"*MATERIAL, NAME=MAT{number}", "*ELASTIC, TYPE=ORTHO",
                # D1111, D1122, D2222, D1133, D2233, D3333, D1212, D1313, then D2323 on the next line
                ", ".join(_number(v) for v in (c[0, 0], c[0, 2], c[2, 2], c[0, 1], c[2, 1], c[1, 1], c[4, 4], c[5, 5])), _number(c[3, 3]),
                "*EXPANSION, TYPE=ORTHO, ZERO=0.", "0., 0., -1.",
                f"*SOLID SECTION, ELSET=M{number}, MATERIAL=MAT{number}", "1."]
    out.append("*ELSET, ELSET=EALL, GENERATE")
    out.append(f"1, {len(elements)}, 1")
    close = 1e-9 * float(nodes[:, 0].max())
    out.append("*NSET, NSET=MIDDLE")
    out += _rows([k + 1 for k in np.flatnonzero(nodes[:, 0] < close)])
    out.append("*NSET, NSET=BOTTOM")
    out += _rows([k + 1 for k in np.flatnonzero(nodes[:, 1] < close)])
    out += ["*BOUNDARY", "MIDDLE, 1, 1, 0.", f"{'NALL' if hold == 'everywhere' else 'BOTTOM'}, 2, 2, 0.",
            "*INITIAL CONDITIONS, TYPE=TEMPERATURE", "NALL, 0.",
            "*STEP", "*STATIC", "*TEMPERATURE", f"NALL, {_number(far.strain_width)}",
            "** The load: each ply's far-field stress on the panel's end (face 2 of an element is its edge at the larger r).", "*DLOAD"]
    last = int(mesh.cell[:, 0].max())
    for e in np.flatnonzero(mesh.cell[:, 0] == last):
        part = mesh.regions[mesh.region[e]]
        if part.kind != "parent":
            raise SliceModelError("The panel's end must be laminate only: the repair reaches the end of the panel")
        out.append(f"{e + 1}, P2, {_number(-far.ply_stress_x[part.ply - 1] / MPA)}")
    out += ["*EL PRINT, ELSET=EALL", "S, E", "*END STEP"]
    return "\n".join(out) + "\n"


def build_slice_model(repair: Repair, load_n_per_m: float, *, element_size_m: float | None = None, fine_m: float | None = None,
                      hold: str = "bottom", cut_faces: str = "open") -> SliceModel:
    """The model of a repair's slice under a load per unit width (N/m, tension positive). `element_size_m` is the longest
    element along the slice (an eighth of the step length unless said) and `fine_m` the length of the elements beside every
    edge (an eighth of the bondline's thickness unless said). The adhesive on the cut faces carries nothing (`cut_faces =
    "open"`) or is bonded. Refused when the repair lacks what a solve needs: the adhesive's Poisson's ratio, a material's
    constants through the thickness, a load."""
    if hold not in HOLDS:
        raise SliceModelError(f"hold must be one of {', '.join(HOLDS)}, got {hold!r}")
    if cut_faces not in CUT_FACES:
        raise SliceModelError(f"cut_faces must be one of {', '.join(CUT_FACES)}, got {cut_faces!r}")
    if isinstance(load_n_per_m, bool) or not isinstance(load_n_per_m, (int, float)) or not math.isfinite(load_n_per_m) or load_n_per_m == 0:
        raise SliceModelError("The solve of the slice needs a load: a finite number that is not zero")
    try:
        far = far_field(repair, float(load_n_per_m))
        if fine_m is None:
            fine_m = repair.adhesive.thickness_m / FINE_PER_BONDLINE
        mesh = slice_mesh(repair, element_size_m, fine_m=fine_m, adhesive_layers=ADHESIVE_LAYERS)
        if cut_faces == "open":
            mesh = _without_cut_faces(repair, mesh)
        stiffness = tuple(region_stiffness(repair, part) for part in mesh.regions)
    except (RepairError, ShapeError) as error:
        raise SliceModelError(str(error)) from error
    nodes, elements = _eight_node(mesh)
    deck = _deck(repair, mesh, nodes, elements, stiffness, far, hold, float(load_n_per_m))
    return SliceModel(repair, float(load_n_per_m), mesh, nodes, elements, stiffness, far, hold, cut_faces, deck)


def read_results(model: SliceModel, dat_text: str, seconds: float = 0.0, equations: int | None = None, solver: str | None = None) -> SliceResults:
    """The element means of the stresses and strains CalculiX printed, in SI. CalculiX prints every integration point of every
    element, in its own order and its own axes (x the load, y the thickness, z the width), and a shear strain as half the
    engineering one. Refused when a row is missing, or when CalculiX's stress is not the engine's stiffness times CalculiX's
    strain: that would mean the deck's materials are not the ones the answer is worked out with."""
    dat = parse_dat(dat_text)
    count = len(model.elements)

    def means(block) -> np.ndarray:
        labels = block.ids[:, 0]
        order = np.argsort(labels, kind="stable")
        points, extra = divmod(len(labels), count)
        if extra or points < 1 or not np.array_equal(labels[order].reshape(count, points)[:, 0], np.arange(1, count + 1)):
            raise SliceModelError("CalculiX did not print every element's integration points")
        return block.values[order].reshape(count, points, -1).mean(axis=1)

    printed_stress, printed_strain = means(dat.stresses("EALL")) * MPA, means(dat.strains("EALL"))  # xx, yy, zz, xy, xz, yz
    strain = np.column_stack([printed_strain[:, 0], printed_strain[:, 1], 2 * printed_strain[:, 3]])
    stress = np.column_stack([printed_stress[:, 0], printed_stress[:, 2], printed_stress[:, 1], printed_stress[:, 3]])
    ours = _stress_in_slice_axes(model, strain)
    off = float(np.max(np.abs(ours[:, [0, 1, 2, 4]] - stress))) / float(np.max(np.abs(stress)))
    if not off < MATCH_TOLERANCE:
        raise SliceModelError(f"CalculiX's stresses are not the engine's stiffness times its strains (off by {off:.2e} of the largest stress)")
    return SliceResults(strain, stress, float(seconds), equations, solver)


def _strain_in_slice_axes(model: SliceModel, strain: np.ndarray) -> np.ndarray:
    """The six strains of every row in the slice's axes (xx, yy, zz, yz, xz, xy) from the three the plane has: the width
    strain is the laminate's far-field one, and the slice neither shears in the laminate's plane nor across its width."""
    full = np.zeros((len(strain), 6))
    full[:, 0], full[:, 1], full[:, 2], full[:, 4] = strain[:, 0], model.far.strain_width, strain[:, 1], strain[:, 2]
    return full


def _stress_in_slice_axes(model: SliceModel, strain: np.ndarray) -> np.ndarray:
    """Every element's six stresses in the slice's axes (Pa), by the engine's stiffness of its rectangle."""
    full = _strain_in_slice_axes(model, strain)
    stress = np.zeros_like(full)
    for index, matrix in enumerate(model.stiffness):
        rows = model.mesh.region == index
        stress[rows] = full[rows] @ matrix.T
    return stress


def run_slice_model(model: SliceModel, workdir: Path | str | None = None, ccx: str | None = None, threads: int = 1,
                    timeout_s: float = 600.0) -> SliceResults:
    """Solve the deck with CalculiX and read the result. With `workdir` the deck and CalculiX's files are kept there."""
    owned = workdir is None
    folder = Path(tempfile.mkdtemp(prefix="repair-slice-")) if owned else Path(workdir)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        deck = folder / "repair-slice.inp"
        deck.write_text(model.deck, encoding="utf-8", newline="\n")
        try:
            result = run_calculix(deck, ccx=ccx, threads=threads, timeout_s=timeout_s)
        except CalculixError as error:
            raise SliceModelError(str(error)) from error
        equations, lines = None, result.stdout.splitlines()
        for k, line in enumerate(lines[:-1]):
            if line.strip() == "number of equations":
                equations = int(lines[k + 1].strip())
                break
        return read_results(model, result.dat_text, result.elapsed_s, equations, result.version)
    finally:
        if owned:
            import shutil

            shutil.rmtree(folder, ignore_errors=True)


@dataclass(frozen=True)
class BondLine:
    """One bond, a flat stretch of adhesive with the patch on it and the laminate under it: where its stations are (m from
    the middle), and there the adhesive's shear stress (positive when it passes tension into the patch) and its peel stress
    (positive when it pulls the patch off), each the mean through the bondline's thickness, Pa. `edges_m` are the ends of
    the stations' columns, one more than the stations."""

    name: str
    step: int | None
    r_m: np.ndarray
    shear_pa: np.ndarray
    peel_pa: np.ndarray
    edges_m: np.ndarray

    def largest_mean(self, values: np.ndarray, length_m: float, size=np.abs) -> tuple[float, float]:
        """The mean of `values` (one per station, constant over its column) over a stretch `length_m` long, where `size` of
        that mean is largest along the bond: the mean, and the middle of the stretch. A bond shorter than the length is
        taken whole. The mean over a moving stretch changes at a constant rate between the positions where one of its ends
        meets a column's end, so the largest is at one of those positions."""
        edges = np.asarray(self.edges_m, dtype=float)
        length = min(float(length_m), float(edges[-1] - edges[0]))
        integral = np.concatenate([[0.0], np.cumsum(np.asarray(values, dtype=float) * np.diff(edges))])
        starts = np.unique(np.clip(np.concatenate([edges, edges - length]), edges[0], edges[-1] - length))
        means = (np.interp(starts + length, edges, integral) - np.interp(starts, edges, integral)) / length
        k = int(np.argmax(size(means)))
        return float(means[k]), float(starts[k] + length / 2)


@dataclass(frozen=True)
class CutFace:
    """The adhesive on one cut face: the mean stress across it (along the load, tension positive) and the mean shear stress
    along it, Pa."""

    name: str
    step: int | None
    normal_pa: float
    shear_pa: float


@dataclass(frozen=True)
class Peak:
    """A largest stress along the bondline: the mean over a square of adhesive, the bondline's thickness high and as long
    (Pa), where the square's middle is (m from the middle of the repair) and on which bond."""

    value_pa: float
    r_m: float
    name: str


@dataclass(frozen=True)
class Boundary:
    """One boundary of the repair's lap: where it is, and the force per unit width (N/m) the patch, the laminate and the
    adhesive carry across that station by the model, with the patch's force by the hand calculation."""

    name: str
    r_m: float
    patch: float
    laminate: float
    adhesive: float
    hand_patch: float


@dataclass(frozen=True)
class PlyCheck:
    """One ply's weakest station: its strength ratio there (the factor on the load at which the ply reaches a strength), the
    mode, where, and the ply's stresses in its own axes there (sigma1, sigma2, tau12, Pa). `ratio` is None for a ply whose
    material has no strengths."""

    name: str
    kind: str
    angle_deg: float
    ratio: float | None
    mode: str | None
    r_m: float | None
    stress_pa: tuple[float, float, float] | None


@dataclass(frozen=True)
class SliceAnswer:
    """The solved slice. Forces are per unit width (N/m) at `stations_m`, the middle of every column of elements."""

    model: SliceModel
    results: SliceResults
    criterion: str
    stations_m: np.ndarray
    patch_force: np.ndarray  # the patch's plies and the cover plies
    laminate_force: np.ndarray
    adhesive_force: np.ndarray
    equilibrium_error: float  # the largest gap between the three forces' sum and the load, as a fraction of the load
    far_field_error: float  # the largest gap between a ply's strain midway to the panel's end and the far-field strain, as a fraction of it
    bond: tuple[BondLine, ...]
    cut_faces: tuple[CutFace, ...]
    peak_shear: Peak
    peak_peel: Peak
    boundaries: tuple[Boundary, ...]
    lap: StepLap
    plies: tuple[PlyCheck, ...]

    @property
    def elastic_limit_load(self) -> float | None:
        """The load per unit width (N/m) at which the largest shear stress along the bondline reaches the adhesive's shear
        strength; None when the adhesive has none. Not the repair's strength: the adhesive yields before it fails."""
        strength = self.model.repair.adhesive.shear_strength_pa
        return None if strength is None else abs(self.model.load_n_per_m) * strength / abs(self.peak_shear.value_pa)

    @property
    def peel_limit_load(self) -> float | None:
        """The load per unit width (N/m) at which the largest peel stress along the bondline reaches the bond's peel
        strength; None when the adhesive states none, or when nothing along the bondline is pulled apart."""
        strength = self.model.repair.adhesive.peel_strength_pa
        if strength is None or self.peak_peel.value_pa <= 0:
            return None
        return abs(self.model.load_n_per_m) * strength / self.peak_peel.value_pa

    @property
    def first_ply(self) -> PlyCheck | None:
        """The ply that reaches a strength first, among the plies whose material has strengths."""
        checked = [ply for ply in self.plies if ply.ratio is not None]
        return min(checked, key=lambda ply: ply.ratio) if checked else None

    @property
    def first_ply_load(self) -> float | None:
        first = self.first_ply
        return None if first is None else abs(self.model.load_n_per_m) * first.ratio

    @property
    def first(self) -> tuple[str, float] | None:
        """What reaches its limit first as the load grows, and at what load per unit width (N/m): "adhesive" (its shear
        stress at its elastic limit), "peel" (the bondline's peel stress at the peel strength) or "ply" (the first ply at a
        strength). None when none of the three has a strength to reach."""
        limits = [(name, load) for name, load in (("adhesive", self.elastic_limit_load), ("peel", self.peel_limit_load),
                                                  ("ply", self.first_ply_load)) if load is not None]
        return min(limits, key=lambda limit: limit[1]) if limits else None


def slice_answer(model: SliceModel, results: SliceResults, criterion: str = "max_stress") -> SliceAnswer:
    """Read the solved slice: the forces at every station, the bondline's stresses, the lap's boundaries beside the hand
    calculation, and every ply's weakest station by `criterion` ("max_stress" or "tsai_hill"). Refused when the forces do not
    add up to the load or the far field is not the laminate theory's."""
    if criterion not in CHECKED_CRITERIA or criterion not in CRITERIA:
        raise SliceModelError(f"The plies of a slice are checked by one of {', '.join(CHECKED_CRITERIA)}, got {criterion!r}")
    repair, mesh, load = model.repair, model.mesh, model.load_n_per_m
    column, layer = mesh.cell[:, 0], mesh.cell[:, 1]
    columns = len(mesh.r_lines_m) - 1
    stations = (mesh.r_lines_m[:-1] + mesh.r_lines_m[1:]) / 2
    height = np.diff(mesh.z_lines_m)[layer]
    kinds = np.array([part.kind for part in mesh.regions])[mesh.region]

    def force(*names: str) -> np.ndarray:
        rows = np.isin(kinds, names)
        return np.bincount(column[rows], weights=(results.stress[:, 0] * height)[rows], minlength=columns)

    patch, laminate, adhesive = force("patch", "cover"), force("parent"), force("adhesive")
    equilibrium = float(np.max(np.abs(patch + laminate + adhesive - load))) / abs(load)
    if not equilibrium < EQUILIBRIUM_TOLERANCE:
        raise SliceModelError(f"The forces along the load do not add up to the load at every station (off by {equilibrium:.2e} of it)")
    outer = repair.patch_radius_m if repair.external else repair.cover_radius_m
    midway = int(np.argmin(np.abs(stations - (outer + repair.panel_length_m / 2) / 2)))
    there = (column == midway) & (kinds == "parent")
    far_error = float(np.max(np.abs(results.strain[there, 0] - model.far.strain_x))) / abs(model.far.strain_x)
    if not far_error < FAR_FIELD_TOLERANCE:
        raise SliceModelError(f"Midway between the repair and the panel's end the strain is not yet the laminate's far from a repair (off by "
                              f"{far_error:.1%}): the panel is too short around the repair for this model; give a longer panel")

    kind_at = {(int(c), int(k)): str(kind) for c, k, kind in zip(column, layer, kinds)}
    bond, faces = [], []
    for index, part in enumerate(mesh.regions):
        if part.kind != "adhesive":
            continue
        rows = mesh.region == index
        if not rows.any():
            continue  # a cut face left open
        if not is_cut_face(repair, part):
            # the bond is where the adhesive has the patch on it and the laminate under it: not its end under an open cut face
            # or over one, a corner of adhesive that joins nothing
            low, high = int(layer[rows].min()), int(layer[rows].max())
            inside = np.array([c for c in np.unique(column[rows])
                               if kind_at.get((int(c), high + 1)) in ("patch", "cover") and kind_at.get((int(c), low - 1)) == "parent"], dtype=int)
            if inside.size == 0:
                continue
            thickness = np.bincount(column[rows], weights=height[rows], minlength=columns)[inside]
            shear = np.bincount(column[rows], weights=(-results.stress[:, 3] * height)[rows], minlength=columns)[inside] / thickness
            peel = np.bincount(column[rows], weights=(results.stress[:, 2] * height)[rows], minlength=columns)[inside] / thickness
            if not np.array_equal(inside, np.arange(inside[0], inside[-1] + 1)):
                raise SliceModelError(f"{part.name} does not join the patch and the laminate along one stretch")
            bond.append(BondLine(part.name, part.step, stations[inside], shear, peel, mesh.r_lines_m[inside[0]:inside[-1] + 2]))
        else:
            area = (np.diff(mesh.r_lines_m)[column] * height)[rows]
            faces.append(CutFace(part.name, part.step, float(np.average(results.stress[rows, 0], weights=area)),
                                 float(np.average(-results.stress[rows, 3], weights=area))))
    if not bond:
        raise SliceModelError("The repair has no flat bondline to read")

    def peak(values: str, size) -> Peak:
        found = [(line, *line.largest_mean(getattr(line, values), repair.adhesive.thickness_m, size)) for line in bond]
        line, value, r = max(found, key=lambda item: float(size(item[1])))
        return Peak(value, r, line.name)

    lap = repair_lap(repair, load)
    steps, names, _ = lap_steps(repair)
    boundaries, r = [], outer
    for step, name, hand in zip(steps, names, lap.forces[1:]):
        r -= step.length_m
        at = r if r > 1e-9 * outer else 0.0  # the sum of the steps ends at the middle but for rounding
        boundaries.append(Boundary(name, at, float(np.interp(at, stations, patch)), float(np.interp(at, stations, laminate)),
                                   float(np.interp(at, stations, adhesive)), float(hand)))

    full = _strain_in_slice_axes(model, results.strain)
    plies = []
    for index, part in enumerate(mesh.regions):
        if part.kind == "adhesive":
            continue
        material = repair.parent_material if part.kind == "parent" else repair.patch_material
        if material.lamina.strengths is None:
            plies.append(PlyCheck(part.name, part.kind, part.angle_deg, None, None, None, None))
            continue
        rows = mesh.region == index
        inside = np.unique(column[rows])
        thickness = np.bincount(column[rows], weights=height[rows], minlength=columns)[inside]
        mean = np.column_stack([np.bincount(column[rows], weights=(full[:, k] * height)[rows], minlength=columns)[inside] / thickness for k in range(6)])
        own = ply_axis_stress(model.stiffness[index], part.angle_deg, mean)[:, [0, 1, 5]]  # sigma1, sigma2, tau12 at every station
        ratios, modes = scaled_strength_ratios(criterion, material.lamina, own, None)
        k = int(np.argmin(ratios))
        plies.append(PlyCheck(part.name, part.kind, part.angle_deg, float(ratios[k]), modes[k], float(stations[inside][k]),
                              tuple(float(v) for v in own[k])))
    return SliceAnswer(model, results, criterion, stations, patch, laminate, adhesive, equilibrium, far_error, tuple(bond), tuple(faces),
                       peak("shear_pa", np.abs), peak("peel_pa", lambda values: values), tuple(boundaries), lap, tuple(plies))


def solve_slice(repair: Repair, load_n_per_m: float, *, criterion: str = "max_stress", workdir: Path | str | None = None, ccx: str | None = None,
                threads: int = 1, **options) -> SliceAnswer:
    """Build the slice's model, solve it and read the answer: `build_slice_model`, `run_slice_model`, `slice_answer`."""
    if criterion not in CHECKED_CRITERIA:
        raise SliceModelError(f"The plies of a slice are checked by one of {', '.join(CHECKED_CRITERIA)}, got {criterion!r}")
    model = build_slice_model(repair, load_n_per_m, **options)
    return slice_answer(model, run_slice_model(model, workdir, ccx, threads), criterion)


def slice_report(answer: SliceAnswer, units: str) -> dict:
    """The solved slice as plain numbers in a unit system (the systems of the engine's units.py): the model, its two checks,
    the far field, the bondline, the forces along the slice and at the lap's boundaries beside the hand calculation, the
    plies, and what reaches its limit first."""
    if units not in UNIT_SYSTEMS:
        raise SliceModelError(f"units must be one of {', '.join(UNIT_SYSTEMS)}, got {units!r}")
    system = UNIT_SYSTEMS[units]
    length, stress, force = system["length"][0], system["stress"][0], system["N"][0]
    model, results, repair = answer.model, answer.results, answer.model.repair

    def peak(value: Peak) -> dict:
        return {"value": value.value_pa / stress, "r": value.r_m / length, "part": value.name}

    def ply(check: PlyCheck) -> dict:
        return {"name": check.name, "kind": check.kind, "angle": check.angle_deg, "strength_ratio": check.ratio, "mode": check.mode,
                "r": None if check.r_m is None else check.r_m / length,
                "stress": None if check.stress_pa is None else [value / stress for value in check.stress_pa]}

    hand_peak = answer.lap.peak_shear[0]
    strength = repair.adhesive.shear_strength_pa
    first, first_ply = answer.first, answer.first_ply
    return {
        "units": {"length": system["length"][1], "stress": system["stress"][1], "force": system["N"][1]},
        "load": model.load_n_per_m / force,
        "model": {"solver": "CalculiX" + (f" {results.solver}" if results.solver else ""), "element": "CPE8R", "elements": int(len(model.elements)),
                  "nodes": int(len(model.nodes_m)), "equations": results.equations, "seconds": round(results.seconds, 2),
                  "element_size": float(np.max(np.diff(model.mesh.r_lines_m))) / length, "fine_size": model.fine_m / length, "hold": model.hold,
                  "cut_faces": model.cut_faces},
        "checks": {"equilibrium": answer.equilibrium_error, "far_field": answer.far_field_error},
        "far_field": {"strain_x": model.far.strain_x, "strain_width": model.far.strain_width,
                      "ply_stress_x": [value / stress for value in model.far.ply_stress_x]},
        "bond": {
            "peak_shear": peak(answer.peak_shear), "peak_peel": peak(answer.peak_peel), "mean_over": repair.adhesive.thickness_m / length,
            "lines": [{"name": line.name, "step": line.step, "r": (line.r_m / length).tolist(), "shear": (line.shear_pa / stress).tolist(),
                       "peel": (line.peel_pa / stress).tolist()} for line in answer.bond],
            "cut_faces": [{"name": face.name, "step": face.step, "normal": face.normal_pa / stress, "shear": face.shear_pa / stress}
                          for face in answer.cut_faces],
        },
        "forces": {"r": (answer.stations_m / length).tolist(), "patch": (answer.patch_force / force).tolist(),
                   "laminate": (answer.laminate_force / force).tolist(), "adhesive": (answer.adhesive_force / force).tolist()},
        "boundaries": [{"name": b.name, "r": b.r_m / length, "patch": b.patch / force, "laminate": b.laminate / force, "adhesive": b.adhesive / force,
                        "hand_patch": b.hand_patch / force} for b in answer.boundaries],
        "hand": {"peak_shear": abs(hand_peak) / stress,
                 "elastic_limit_load": None if strength is None else abs(model.load_n_per_m) * strength / abs(hand_peak) / force},
        "elastic_limit_load": None if answer.elastic_limit_load is None else answer.elastic_limit_load / force,
        "peel_limit_load": None if answer.peel_limit_load is None else answer.peel_limit_load / force,
        "criterion": answer.criterion,
        "plies": [ply(check) for check in answer.plies],
        "first_ply": None if first_ply is None else ply(first_ply) | {"load": answer.first_ply_load / force},
        "first": None if first is None else {"what": first[0], "load": first[1] / force},
    }


FIRST_WORDS = {"adhesive": "the adhesive reaches its elastic limit in shear", "peel": "the bondline's peel stress reaches the peel strength",
               "ply": "a ply reaches a strength"}


def headline(report: dict) -> str:
    """The solve in one line."""
    u, bond = report["units"], report["bond"]
    line = (f"Under {report['load']:g} {u['force']}: largest bondline shear {abs(bond['peak_shear']['value']):.4g} {u['stress']} "
            f"(hand calculation {report['hand']['peak_shear']:.4g}), largest peel {bond['peak_peel']['value']:.4g} {u['stress']}")
    if report["first"] is not None:
        line += f"; first, {FIRST_WORDS[report['first']['what']]} at {report['first']['load']:.4g} {u['force']}"
    return line


def main(argv: list[str] | None = None) -> int:
    """`python -m anisotropy_fea.repair_model <repair.toml> [--out DIR] [--criterion NAME] [--size mm] [--fine mm]`: solve the
    slice of a repair file and print the answer in the file's units; with --out, keep the deck, CalculiX's files and
    repair-solve.json there."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m anisotropy_fea.repair_model", description="Solve a stepped patch repair's slice in CalculiX (ADR-0132).")
    parser.add_argument("repair", type=Path, help="the repair, a TOML file (engine/examples/example-patch-repair.toml)")
    parser.add_argument("--out", type=Path, help="folder for the deck, CalculiX's files and repair-solve.json")
    parser.add_argument("--criterion", default="max_stress", choices=CHECKED_CRITERIA, help="how the plies are checked (default max_stress)")
    parser.add_argument("--size", type=float, help="the longest element along the slice, mm")
    parser.add_argument("--fine", type=float, help="the element length beside every edge, mm")
    parser.add_argument("--cut-faces", default="open", choices=CUT_FACES, help="whether the adhesive on the cut faces carries load (default open: it does not)")
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        case = tomllib.loads(args.repair.read_text(encoding="utf-8"))
        repair, load = repair_from_dict({key: value for key, value in case.items() if key not in ("expected", "solve")})  # a validation case reads too
        if load is None:
            raise SliceModelError("The file states no load ([applied] load), so the slice is not solved")
        started = time.monotonic()
        answer = solve_slice(repair, load, criterion=args.criterion, workdir=args.out, threads=args.threads, cut_faces=args.cut_faces,
                             element_size_m=None if args.size is None else args.size * MM, fine_m=None if args.fine is None else args.fine * MM)
        report = slice_report(answer, case["units"])
    except (SliceModelError, RepairError, tomllib.TOMLDecodeError, OSError) as error:
        print(f"refused: {(str(error).splitlines() or [type(error).__name__])[0]}")
        return 2
    u, model, bond = report["units"], report["model"], report["bond"]
    length, stress, force = u["length"], u["stress"], u["force"]
    print(case.get("title", args.repair.stem))
    print(f"{model['solver']}: {model['elements']} elements ({model['element']}), {model['equations']} equations, {time.monotonic() - started:.1f} s; "
          f"elements {model['fine_size']:.3g} to {model['element_size']:.3g} {length} long")
    if not repair.external:
        print("The adhesive on the cut faces " + ("is bonded" if model["cut_faces"] == "bonded" else "carries nothing (a gap one bondline wide)"))
    print(f"Checks: forces add up to the load within {report['checks']['equilibrium']:.1e} of it; far-field strain within "
          f"{report['checks']['far_field']:.1e} of the laminate theory's")
    print(f"\n{'boundary of the lap':<22} {'r':>9} {'patch':>10} {'laminate':>10} {'adhesive':>10} {'patch by hand':>14}   ({length}, {force})")
    for b in report["boundaries"]:
        print(f"{b['name']:<22} {b['r']:>9.4g} {b['patch']:>10.4g} {b['laminate']:>10.4g} {b['adhesive']:>10.4g} {b['hand_patch']:>14.4g}")
    print(f"\nBondline under {report['load']:g} {force}, each stress the mean over a square of adhesive as long as the bondline is thick:")
    print(f"  largest shear {abs(bond['peak_shear']['value']):.4g} {stress} at r = {bond['peak_shear']['r']:.4g} {length} ({bond['peak_shear']['part']}); "
          f"the hand calculation's is {report['hand']['peak_shear']:.4g}")
    print(f"  largest peel {bond['peak_peel']['value']:.4g} {stress} at r = {bond['peak_peel']['r']:.4g} {length} ({bond['peak_peel']['part']})"
          + (f"; it reaches the peel strength at {report['peel_limit_load']:.4g} {force}" if report["peel_limit_load"] is not None
             else "; not judged: the adhesive states no peel strength"))
    for face in bond["cut_faces"]:
        print(f"  {face['name']}: {face['normal']:.4g} {stress} across it")
    if report["elastic_limit_load"] is not None:
        print(f"  load at the adhesive's elastic limit: {report['elastic_limit_load']:.4g} {force} (hand calculation "
              f"{report['hand']['elastic_limit_load']:.4g}); not the repair's strength: the adhesive yields before it fails")
    checked = [p for p in report["plies"] if p["strength_ratio"] is not None]
    if checked:
        print(f"\nPlies by {report['criterion'].replace('_', ' ')}, each at its weakest station (stresses the mean through the ply's thickness):")
        for p in sorted(checked, key=lambda p: p["strength_ratio"])[:6]:
            print(f"  {p['name']:<28} strength ratio {p['strength_ratio']:>7.3f}, {p['mode']}, at r = {p['r']:.4g} {length}")
    else:
        print("\nNo ply is checked: the materials state no strengths")
    if report["first"] is not None:
        print(f"\nFirst, {FIRST_WORDS[report['first']['what']]}, at {report['first']['load']:.4g} {force}")
    if args.out:
        (args.out / REPORT).write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(f"\n{args.out / REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
