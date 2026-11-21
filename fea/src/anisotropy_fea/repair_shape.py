"""A stepped patch repair's shape from its description (ADR-0131, flush or bonded on top): the slice through its middle as a mesh of four-node
quadrilaterals, and the whole repair in its panel as named solids in a STEP file.

Both are built from the rectangles the engine lists for the repair (anisotropy_engine.repair.regions), so the hand
calculation, the mesh and the file a CAD program opens describe one repair.

The slice (`slice_mesh`): one half of the cut along the load through the repair's middle, r from the middle outward and z
up from the laminate's bottom face, in metres. The mesh is a grid: a line of nodes runs along every edge of every rectangle,
so each element lies in one part, and the stretches between those lines are divided to the element size along r and into
`per_ply` elements for each ply's thickness along z (the thinner of the laminate's ply and the patch's). An element is given its part twice, by the rectangle that holds its
centre and by the engine's level-by-level rule (`region_at`), and the mesh is refused where the two disagree. Where there
is nothing (above the laminate outside the repair, and under the deepest plies of a patch in a cut through every ply),
there is no element. For a solve (ADR-0132) the mesh is graded along r: with `fine_m`, the elements beside every edge of a
rectangle (a step's end, the patch's edge, a cut) are that long, each one further away longer by `growth`, up to the element
size; and the bondline can be given more than one element through its thickness (`adhesive_layers`).

The solids (`build_repair_shape`): every rectangle of the repair itself swept about the middle, a disc or a ring, and every
laminate ply the panel's slab less the disc its step cuts, each one a solid with its part's name. The plies and the adhesive
of a strip patch are slabs across the panel's width instead, the adhesive less the hole's disc. The shape is built in
Gmsh's OpenCASCADE kernel in millimetres, the unit its STEP file states, x along the load, the repair's middle at x = y = 0
and z = 0 at the laminate's bottom face. A STEP file holds shape and names only: no ply angle and no material. The part
table (`RepairShape.parts`) gives each solid's kind, angle and volume.

What is measured back: the area of each kind of part from the mesh's elements, the length of bondline that touches the
laminate from the mesh's edges, and the volume of each solid from OpenCASCADE, against the engine's own figures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from anisotropy_engine.repair import Region, Repair, region_at, regions

from .wing_shape import ShapeError, _gmsh, _quiet, name_step_products

MM = 1e-3
TOLERANCE = 1e-12  # m: two edges of rectangles closer than this are one line of nodes


@dataclass(frozen=True)
class SliceMesh:
    """The half slice as four-node quadrilaterals. `nodes_m` is (n, 2): r and z; `quads` is (m, 4), each element's corners
    counterclockwise; `region` gives each element's rectangle as an index into `regions`. The mesh is a grid: `r_lines_m`
    and `z_lines_m` are its lines, and `cell` (m, 2) gives each element's column along r and its layer along z, so the
    elements of one station through the thickness are those of one column."""

    nodes_m: np.ndarray
    quads: np.ndarray
    region: np.ndarray
    regions: tuple[Region, ...]
    cell: np.ndarray
    r_lines_m: np.ndarray
    z_lines_m: np.ndarray

    @property
    def element_areas(self) -> np.ndarray:
        """Each element's area, m^2, from its corners (the shoelace sum)."""
        r, z = self.nodes_m[self.quads, 0], self.nodes_m[self.quads, 1]
        return 0.5 * np.abs(np.sum(r * np.roll(z, -1, axis=1) - np.roll(r, -1, axis=1) * z, axis=1))

    def areas(self) -> dict[str, float]:
        """The area of each kind of part, m^2, summed over the elements."""
        total = {"parent": 0.0, "adhesive": 0.0, "patch": 0.0, "cover": 0.0}
        for index, area in zip(self.region, self.element_areas):
            total[self.regions[index].kind] += float(area)
        return total

    def region_areas(self) -> list[float]:
        """The area of each rectangle, m^2, summed over its elements, in the order of `regions`."""
        return [float(v) for v in np.bincount(self.region, weights=self.element_areas, minlength=len(self.regions))]

    def bond_to_laminate(self) -> dict[str, float]:
        """The length of the element edges an adhesive element shares with a laminate element, m: `flat` along the ledges,
        the floor and under the cover plies, `upright` up the cut faces."""
        kinds = [self.regions[index].kind for index in self.region]
        owners: dict[tuple[int, int], list[int]] = {}
        for element, quad in enumerate(self.quads):
            for a, b in zip(quad, np.roll(quad, -1)):
                owners.setdefault((min(a, b), max(a, b)), []).append(element)
        lengths = {"flat": 0.0, "upright": 0.0}
        for (a, b), elements in owners.items():
            if len(elements) == 2 and {kinds[elements[0]], kinds[elements[1]]} == {"adhesive", "parent"}:
                dr, dz = self.nodes_m[b] - self.nodes_m[a]
                lengths["flat" if abs(dz) < abs(dr) else "upright"] += float(math.hypot(dr, dz))
        return lengths


def _lines(edges: list[float], size: float) -> np.ndarray:
    """The grid's lines along one axis: every edge of a rectangle, and the stretch between two neighbours divided evenly into
    elements no longer than `size`."""
    marks = [edges[0]]
    for value in sorted(edges)[1:]:
        if value - marks[-1] > TOLERANCE:
            marks.append(value)
    lines = [marks[0]]
    for low, high in zip(marks, marks[1:]):
        count = max(1, math.ceil((high - low) / size - 1e-9))
        lines.extend(low + (high - low) * k / count for k in range(1, count + 1))
    return np.array(lines)


def _marks(edges: list[float]) -> list[float]:
    """The edges of the rectangles along one axis, in order, two closer than the tolerance counted once."""
    marks = [edges[0]]
    for value in sorted(edges)[1:]:
        if value - marks[-1] > TOLERANCE:
            marks.append(value)
    return marks


def _grown(length: float, fine: float, coarse: float, growth: float) -> list[float]:
    """Element lengths that fill `length` from a mark outward: `fine` first, each next one `growth` times longer and none
    longer than `coarse`; all shortened alike so that they end exactly at `length`."""
    sizes, total, size = [], 0.0, fine
    while total < length * (1 - 1e-12):
        sizes.append(size)
        total += size
        size = min(size * growth, coarse)
    return [value * length / total for value in sizes]


def _graded_lines(edges: list[float], fine: float, coarse: float, growth: float) -> np.ndarray:
    """The grid's lines along r for a graded mesh: every edge of a rectangle, the elements beside each edge `fine` long and
    growing away from it. The slice's two ends, the repair's middle and the panel's end, are not edges to refine at unless a
    rectangle ends within the slice there."""
    marks = _marks(edges)
    lines = [marks[0]]
    for k, (low, high) in enumerate(zip(marks, marks[1:])):
        at_low, at_high = k > 0, k < len(marks) - 2
        if at_low and at_high:
            half = _grown((high - low) / 2, fine, coarse, growth)
            sizes = half + half[::-1]
        elif at_low or at_high:
            sizes = _grown(high - low, fine, coarse, growth)
            sizes = sizes if at_low else sizes[::-1]
        else:
            count = max(1, math.ceil((high - low) / coarse - 1e-9))
            sizes = [(high - low) / count] * count
        lines.extend((low + np.cumsum(sizes))[:-1])
        lines.append(high)
    return np.array(lines)


def slice_mesh(repair: Repair, element_size_m: float | None = None, per_ply: int = 1, *, fine_m: float | None = None, growth: float = 1.3,
               adhesive_layers: int = 1) -> SliceMesh:
    """The half slice of a repair as quadrilaterals: `element_size_m` long at most along r (an eighth of the step length
    unless said) and `per_ply` elements for each ply's thickness. With `fine_m` the mesh is graded along r: `fine_m` long
    beside every edge of a rectangle, each element further from it `growth` times longer, up to the element size. A layer as
    thin as the bondline gets `adhesive_layers` elements through its thickness."""
    if element_size_m is None:
        element_size_m = repair.step_length_m / 8
    if not (isinstance(element_size_m, (int, float)) and math.isfinite(element_size_m) and element_size_m > 0):
        raise ShapeError("The element size must be a positive number")
    if isinstance(per_ply, bool) or not isinstance(per_ply, int) or per_ply < 1:
        raise ShapeError("The elements for each ply's thickness must be a whole number, 1 or more")
    if isinstance(adhesive_layers, bool) or not isinstance(adhesive_layers, int) or adhesive_layers < 1:
        raise ShapeError("The elements through the bondline's thickness must be a whole number, 1 or more")
    parts = regions(repair)
    r_edges = sorted({edge for part in parts for edge in (part.r0, part.r1)})
    if fine_m is None:
        r = _lines(r_edges, float(element_size_m))
    else:
        if not (isinstance(fine_m, (int, float)) and math.isfinite(fine_m) and 0 < fine_m <= element_size_m):
            raise ShapeError("The element size beside an edge must be a positive number, no larger than the element size")
        if not (isinstance(growth, (int, float)) and math.isfinite(growth) and 1 < growth <= 2):
            raise ShapeError("Each element may be longer than its neighbour by a factor above 1 and no more than 2")
        r = _graded_lines(r_edges, float(fine_m), float(element_size_m), float(growth))
    ply = min(repair.ply_thickness_m, repair.patch_material.ply_thickness_m)
    marks, bondline = _marks(sorted({edge for part in parts for edge in (part.z0, part.z1)})), repair.adhesive.thickness_m
    z = [marks[0]]
    for low, high in zip(marks, marks[1:]):
        count = max(1, math.ceil((high - low) / (ply / per_ply) - 1e-9))
        if high - low <= bondline * (1 + 1e-9):
            count = max(count, adhesive_layers)
        z.extend(low + (high - low) * k / count for k in range(1, count + 1))
    z = np.array(z)
    rc, zc = (r[:-1] + r[1:]) / 2, (z[:-1] + z[1:]) / 2
    owner = np.full((len(rc), len(zc)), -1)
    for index, part in enumerate(parts):
        inside = np.outer((rc > part.r0) & (rc < part.r1), (zc > part.z0) & (zc < part.z1))
        if np.any(owner[inside] >= 0):
            raise ShapeError(f"{part.name} overlaps another part of the repair")
        owner[inside] = index
    for i, j in np.ndindex(owner.shape):
        by_rectangle = parts[owner[i, j]].kind if owner[i, j] >= 0 else None
        by_level = region_at(repair, float(rc[i]), float(zc[j]))
        if by_rectangle != by_level:
            raise ShapeError(f"At r = {rc[i]:g} m, z = {zc[j]:g} m the repair is {by_rectangle} by its rectangles and {by_level} by its level")
    node = lambda i, j: i * len(z) + j  # noqa: E731
    cells = np.argwhere(owner >= 0)
    quads = np.array([[node(i, j), node(i + 1, j), node(i + 1, j + 1), node(i, j + 1)] for i, j in cells])
    used = np.unique(quads)
    renumber = np.full(len(r) * len(z), -1)
    renumber[used] = np.arange(len(used))
    grid_r, grid_z = np.meshgrid(r, z, indexing="ij")
    nodes = np.column_stack([grid_r.ravel(), grid_z.ravel()])[used]
    return SliceMesh(nodes_m=nodes, quads=renumber[quads], region=owner[cells[:, 0], cells[:, 1]], regions=parts, cell=cells, r_lines_m=r,
                     z_lines_m=z)


@dataclass(frozen=True)
class SolidPart:
    """One solid of the repair's STEP file: its name there, what it is, a ply's angle from the load, and its volume as
    OpenCASCADE measures it (m^3)."""

    name: str
    kind: str
    angle_deg: float | None
    volume_m3: float


@dataclass(frozen=True)
class RepairShape:
    """A repair's solids, in the order of the engine's rectangles."""

    parts: tuple[SolidPart, ...]

    def volumes(self) -> dict[str, float]:
        """The volume of each kind of part, m^3, summed over the solids."""
        total = {"parent": 0.0, "adhesive": 0.0, "patch": 0.0, "cover": 0.0}
        for part in self.parts:
            total[part.kind] += part.volume_m3
        return total


def step_name(part: Region) -> str:
    """A part's name in a STEP file, whose strings are plain ASCII: the degree sign written out."""
    return part.name.replace("°", " deg")


def _solid(occ, repair: Repair, part: Region) -> int:
    """One rectangle as a solid, in mm: a disc or a ring about the middle, or a slab across the panel's width, twice the
    rectangle's r1 long, less the disc of its r0."""
    z0, height = part.z0 / MM, (part.z1 - part.z0) / MM
    if part.round:
        solid = occ.addCylinder(0.0, 0.0, z0, 0.0, 0.0, height, part.r1 / MM)
    else:
        length, width = 2 * part.r1 / MM, repair.panel_width_m / MM
        solid = occ.addBox(-length / 2, -width / 2, z0, length, width, height)
    if part.r0 > 0:
        hole = occ.addCylinder(0.0, 0.0, z0, 0.0, 0.0, height, part.r0 / MM)
        made, _ = occ.cut([(3, solid)], [(3, hole)])
        if len(made) != 1:
            raise ShapeError(f"{part.name} did not come out as one solid")
        solid = made[0][1]
    return solid


def build_repair_shape(repair: Repair, step_path: Path | str | None = None, name: str = "Stepped patch repair") -> RepairShape:
    """The repair's parts as solids; with `step_path`, its STEP file there, each solid under its part's name."""
    gmsh = _gmsh()
    parts = regions(repair)
    owned = not gmsh.isInitialized()
    if owned:
        gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("repair")
        occ = gmsh.model.occ
        built = [(part, _solid(occ, repair, part)) for part in parts]
        occ.synchronize()
        if len(gmsh.model.getEntities(3)) != len(built):
            raise ShapeError("The repair's solids were not all built")
        volumes = {tag: occ.getMass(3, tag) * MM**3 for _, tag in built}
        if step_path is not None:
            step_path = Path(step_path)
            with _quiet():  # OpenCASCADE's STEP writer prints its transfer statistics to the terminal
                gmsh.write(str(step_path))
            # The writer puts the solids in the order of their tags, which the cuts leave out of the order they were made in.
            name_step_products(step_path, name, [step_name(part) for part, _ in sorted(built, key=lambda made: made[1])])
    finally:
        if owned:
            gmsh.finalize()
        else:
            gmsh.model.remove()
    return RepairShape(parts=tuple(SolidPart(step_name(part), part.kind, part.angle_deg, volumes[tag]) for part, tag in built))


def read_step_volumes(step_path: Path | str) -> list[float]:
    """The volume of every solid of a STEP file, m^3, in the file's order: what a program that opens the file would
    measure."""
    gmsh = _gmsh()
    owned = not gmsh.isInitialized()
    if owned:
        gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("read")
        with _quiet():
            solids = gmsh.model.occ.importShapes(str(step_path))
        gmsh.model.occ.synchronize()
        return [gmsh.model.occ.getMass(3, tag) * MM**3 for dim, tag in solids if dim == 3]
    finally:
        if owned:
            gmsh.finalize()
        else:
            gmsh.model.remove()


def read_repair_file(path: Path | str) -> dict:
    """A repair as a table of values: a repair file (TOML), or the same table as JSON, as a page sends it (ADR-0135). A
    validation case's `expected` and `solve` tables are left out, so a case reads as a repair."""
    import json
    import tomllib

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text) if path.suffix.lower() == ".json" else tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        raise ShapeError(f"{path.name} does not read as a repair file: {error}") from error
    if not isinstance(data, dict):
        raise ShapeError(f"{path.name} does not read as a repair file: it is not a table of values")
    return {key: value for key, value in data.items() if key not in ("expected", "solve")}


REFUSED = 2  # the exit status of a repair that cannot be read or shaped, its reason the last line on stderr


def main(argv: list[str] | None = None) -> int:
    """`python -m anisotropy_fea.repair_shape <repair.toml> [--step <file.step>] [--parts <file.json>] [--size <mm>]`: the
    slice's mesh measured back against the engine, the STEP file when one is asked for, and with it the table of its solids
    (each one's name, kind, ply angle and volume in mm^3)."""
    import argparse
    import json
    import sys

    from anisotropy_engine.repair import RepairError, areas, bond_lengths, repair_from_dict, volumes

    parser = argparse.ArgumentParser(description="The mesh of a stepped patch repair's slice, and its STEP file")
    parser.add_argument("repair", type=Path, help="the repair, a TOML file (engine/examples/example-patch-repair.toml) or the same table as .json")
    parser.add_argument("--step", type=Path, help="write the repair's solids to this STEP file")
    parser.add_argument("--parts", type=Path, help="with --step: write the table of the solids to this JSON file")
    parser.add_argument("--size", type=float, help="the element size along the slice, mm")
    args = parser.parse_args(argv)
    try:
        case = read_repair_file(args.repair)
        repair, _ = repair_from_dict(case)
        mesh = slice_mesh(repair, None if args.size is None else args.size * MM)
    except (RepairError, ShapeError, OSError) as error:
        print((str(error).splitlines() or [type(error).__name__])[0], file=sys.stderr)
        return REFUSED
    title = case.get("title") if isinstance(case.get("title"), str) and case.get("title") else args.repair.stem
    print(f"{title}: {len(mesh.quads)} elements, {len(mesh.nodes_m)} nodes in the half slice")
    measured, stated = mesh.areas(), areas(repair)
    for kind in stated:
        print(f"  {kind:>9}: {measured[kind] / MM**2:12.5f} mm^2 in the mesh, {stated[kind] / MM**2:12.5f} mm^2 by the description")
    bond, lengths = mesh.bond_to_laminate(), bond_lengths(repair)
    print(f"  bondline on the laminate: {bond['flat'] / MM:.4f} mm flat in the mesh, "
          f"{sum(value for name, value in lengths.items() if name != 'cut_faces') / MM:.4f} mm by the description; "
          f"{bond['upright'] / MM:.4f} mm up the cut faces, {repair.depth_m / MM:.4f} mm by the description")
    if args.step:
        try:
            shape = build_repair_shape(repair, args.step, title if "title" in case else "Stepped patch repair")
        except ShapeError as error:
            print((str(error).splitlines() or [type(error).__name__])[0], file=sys.stderr)
            return REFUSED
        solid, swept = shape.volumes(), volumes(repair)
        print(f"{args.step}: {len(shape.parts)} solids")
        for kind in swept:
            print(f"  {kind:>9}: {solid[kind] / MM**3:14.3f} mm^3 as solids, {swept[kind] / MM**3:14.3f} mm^3 by the description")
        if args.parts:
            table = {"title": title, "units": {"length": "mm", "volume": "mm^3"},
                     "parts": [{"name": part.name, "kind": part.kind, "angle": part.angle_deg, "volume": part.volume_m3 / MM**3} for part in shape.parts],
                     "volumes": {kind: value / MM**3 for kind, value in solid.items()}}
            args.parts.write_text(json.dumps(table, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
