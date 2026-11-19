"""A wing's shape from its description: skins, spar webs and ribs as surfaces at their mid-thickness, a STEP file and a shell mesh.

The shape is built in Gmsh's OpenCASCADE kernel from the same description the engine's hand calculation reads
(anisotropy_engine.wing.Wing), so the STEP file a CAD program opens, the mesh the finite element model is cut from and the hand
calculation all describe one wing (ADR-0116).

Axes: x along the chord from the leading edge to the trailing edge, y along the span from the root to the tip, z up. The shape is
built in millimetres, the unit its STEP file states; the mesh's nodes are returned in metres.

Every part is a surface at its mid-thickness, as a shell element sees it:
- the upper and lower skin: the airfoil's outer surface moved inward along its normal by half the skin's thickness. Where the
  airfoil grows thinner than the skin near the trailing edge, the two mid-surfaces cross; both stop at that point, which closes the
  section. If they do not cross before the trailing edge, a flat strip of skin joins their ends.
- the front and rear spar webs: flat, at their chord positions, from the lower skin's mid-surface to the upper's.
- the ribs, when the description gives a rib spacing: flat, at the root, every rib spacing outboard of it, and at the tip, each
  filling the skins' mid-surface section.

A STEP file holds shape only: faces, edges, their geometry and each part's name. It holds no thickness and no plies; the part
table (WingShape.parts) gives each part's layup and thickness, and a CAD program's thicken feature, both sides by half the
thickness, turns a part into a solid.

For the mesh the parts are cut where they meet (an OpenCASCADE fragment), so that a skin and a web share their nodes along the
line where they join, and meshed with four-node quadrilaterals. Each element's corner order makes its normal point out of the
wing for a skin, aft for a web and to the root for a rib (ADR-0004: ply angles turn counterclockwise about the normal).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from anisotropy_engine.wing import Wing

MM = 1e-3  # metres per millimetre
SECTION_POINTS = 81  # points along each side of the airfoil, cosine spaced, before the spar points are added
SPLIT_GAP = 1e-3  # an airfoil point closer than this share of the chord to a spar point is dropped, so the spline does not wiggle
CROSSING_SAMPLES = 4001


class ShapeError(ValueError):
    """The description cannot be built as a shape."""


@dataclass(frozen=True)
class Section:
    """The skins' mid-surface section at every station, metres: the upper and lower curves from the leading edge aft."""

    upper: np.ndarray  # (k, 2) x, z
    lower: np.ndarray  # (k, 2) x, z; upper[0] == lower[0] is the leading edge
    trailing_edge_closed: bool  # the two curves meet aft; otherwise a flat strip joins upper[-1] and lower[-1]
    spar_x_m: tuple[float, float]
    spar_top_m: tuple[float, float]  # z of each web's top, on the upper mid-surface
    spar_bottom_m: tuple[float, float]


@dataclass(frozen=True)
class Part:
    """One part of the shape, as the STEP file names it."""

    name: str
    layup: str  # "skin", "spar" or "rib": which layup of the description it carries
    thickness_m: float | None  # plies and core; None for a rib when the description gives no rib layup
    area_m2: float  # of its mid-surface
    mass_kg: float | None  # area times thickness times the material's density (plies) and the core's (core); None without a thickness


@dataclass(frozen=True)
class ShellMesh:
    """The shell mesh of the wing: nodes in metres and four-node quadrilaterals, with an element set per part."""

    nodes: np.ndarray  # (n, 3)
    elements: np.ndarray  # (ne, 4) node indices, ordered so the normal points out of the wing, aft or to the root
    element_sets: dict[str, np.ndarray] = field(default_factory=dict)  # part name -> sorted element indices
    node_sets: dict[str, np.ndarray] = field(default_factory=dict)  # "root": the nodes at y = 0

    @property
    def element_count(self) -> int:
        return int(self.elements.shape[0])


@dataclass(frozen=True)
class WingShape:
    """The shape's parts, its section and its rib stations; the mesh when one was asked for."""

    wing_name: str
    section: Section
    rib_stations_m: tuple[float, ...]
    parts: tuple[Part, ...]
    mesh: ShellMesh | None

    @property
    def mass_kg(self) -> float | None:
        masses = [part.mass_kg for part in self.parts]
        return None if any(mass is None for mass in masses) else float(sum(masses))


def layup_thickness(layup) -> float:
    """Plies and core, metres."""
    return layup.fiber_thickness_m + layup.core_thickness_m


def _areal_mass(layup) -> float:
    """kg per square metre of a layup: plies and core."""
    return layup.fiber_thickness_m * layup.material.density_kg_m3 + layup.core_thickness_m * (layup.core_density_kg_m3 or 0.0)


def rib_stations(wing: Wing) -> tuple[float, ...]:
    """Where the ribs stand, metres from the root: the root, every rib spacing outboard, and the tip; none without a spacing.
    The engine's geometry holds the rule (`WingGeometry.rib_stations_m`), so the page draws the ribs where the shape builds them."""
    return wing.geometry.rib_stations_m


def mid_surface_section(wing: Wing, points_per_side: int = SECTION_POINTS) -> Section:
    """The skins' mid-surface section: the airfoil's outline moved inward by half the skin's thickness, closed aft."""
    g = wing.geometry
    c = g.chord_m
    half = layup_thickness(wing.skin) / 2
    x = (1 - np.cos(np.linspace(0.0, math.pi, points_per_side))) / 2
    heights = np.array([g.airfoil.surface_heights(float(v)) for v in x])
    if abs(heights[0, 0] - heights[0, 1]) > 1e-9:
        raise ShapeError("The airfoil's upper and lower surfaces must meet at the leading edge")
    # One outline from the upper trailing edge round the leading edge to the lower trailing edge: counterclockwise, so the
    # inside of the airfoil lies to the left of the direction of travel.
    outline = np.vstack([np.c_[x[::-1], heights[::-1, 0]], np.c_[x[1:], heights[1:, 1]]]) * c
    step = np.gradient(outline, axis=0)
    tangent = step / np.linalg.norm(step, axis=1)[:, None]
    inward = np.c_[-tangent[:, 1], tangent[:, 0]]
    mid = outline + half * inward
    nose = points_per_side - 1
    upper, lower = mid[:nose + 1][::-1], mid[nose:]

    # Aft of mid-chord both curves are functions of x: find where the upper falls to the lower.
    aft = max(upper[0, 0], 0.5 * c)
    end = min(upper[-1, 0], lower[-1, 0])
    xs = np.linspace(aft, end, CROSSING_SAMPLES)
    gap = np.interp(xs, upper[:, 0], upper[:, 1]) - np.interp(xs, lower[:, 0], lower[:, 1])
    if gap[0] <= 0:
        raise ShapeError("The skin is thicker than the airfoil at mid-chord: its mid-surfaces cross")
    closed = bool((gap <= 0).any())
    if closed:
        k = int(np.argmax(gap <= 0))
        x_cross = xs[k - 1] + (xs[k] - xs[k - 1]) * gap[k - 1] / (gap[k - 1] - gap[k])
        z_cross = float(np.interp(x_cross, upper[:, 0], upper[:, 1]))
        upper = np.vstack([upper[upper[:, 0] < x_cross - SPLIT_GAP * c], [x_cross, z_cross]])
        lower = np.vstack([lower[lower[:, 0] < x_cross - SPLIT_GAP * c], [x_cross, z_cross]])
        trailing = x_cross
    else:
        trailing = end

    spar_x = (g.front_spar * c, g.rear_spar * c)
    if spar_x[1] >= trailing - SPLIT_GAP * c:
        raise ShapeError(f"The rear spar at {g.rear_spar:.3f} of the chord is aft of where the skins' mid-surfaces meet "
                         f"({trailing / c:.3f} of the chord)")
    tops = tuple(float(np.interp(v, upper[:, 0], upper[:, 1])) for v in spar_x)
    bottoms = tuple(float(np.interp(v, lower[:, 0], lower[:, 1])) for v in spar_x)
    if min(top - bottom for top, bottom in zip(tops, bottoms)) <= 0:
        raise ShapeError("A spar web has no height between the skins' mid-surfaces")

    def with_spars(curve: np.ndarray, zs: tuple[float, ...]) -> np.ndarray:
        keep = np.ones(len(curve), dtype=bool)
        for v in spar_x:
            keep &= np.abs(curve[:, 0] - v) > SPLIT_GAP * c
        keep[0] = keep[-1] = True
        points = np.vstack([curve[keep], np.c_[spar_x, zs]])
        nose_point, rest = points[:1], points[1:]
        return np.vstack([nose_point, rest[np.argsort(rest[:, 0], kind="stable")]])

    return Section(upper=with_spars(upper, tops), lower=with_spars(lower, bottoms), trailing_edge_closed=closed,
                   spar_x_m=spar_x, spar_top_m=tops, spar_bottom_m=bottoms)


def _step_string(text: str) -> str:
    """A name as a STEP string: printable ASCII, apostrophes doubled."""
    clean = "".join(ch if 32 <= ord(ch) < 127 else "_" for ch in text)
    return clean.replace("'", "''")


def name_step_products(path: Path, assembly: str, names: list[str]) -> None:
    """Give the products of a STEP file Gmsh wrote their parts' names.

    Gmsh's OpenCASCADE writer names the products "Open CASCADE STEP translator <version> <n>" (the assembly) and "... <n>.<k>" for
    the k-th top-level shape, in the order of the shapes, where n counts the files written in this process (1 for the first). The
    names are replaced in place; a file with another number of products than names is refused rather than half named.
    """
    text = path.read_text(encoding="ascii")
    pattern = re.compile(r"PRODUCT\('(Open CASCADE STEP translator [0-9.]+ \d+(?:\.(\d+))?)',\s*'\1'")
    found = pattern.findall(text)
    numbers = sorted(int(k) for _, k in found if k)
    if numbers != list(range(1, len(names) + 1)) or sum(1 for _, k in found if not k) != 1:
        raise ShapeError(f"The STEP file has {len(numbers)} parts where {len(names)} were written; it was not named")

    def rename(match: re.Match) -> str:
        label = assembly if match.group(2) is None else names[int(match.group(2)) - 1]
        label = _step_string(label)
        return f"PRODUCT('{label}',\n  '{label}'"

    path.write_text(pattern.sub(rename, text), encoding="ascii")


class _quiet:
    """Silence the process's standard output for a while: OpenCASCADE writes to file descriptor 1, below Python."""

    def __enter__(self):
        import os
        import sys

        sys.stdout.flush()
        self._saved = os.dup(1)
        self._null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self._null, 1)
        return self

    def __exit__(self, *exc):
        import os

        os.dup2(self._saved, 1)
        os.close(self._saved)
        os.close(self._null)
        return False


def _gmsh():
    try:
        import gmsh
    except (ImportError, OSError) as exc:
        raise ShapeError("Gmsh is not available; from fea/ run `uv sync --extra mesh` (on Linux the wheel also needs libGLU: "
                         f"apt install libglu1-mesa). Python said: {exc}") from None
    return gmsh


def _section_curves(occ, section: Section, y_mm: float) -> dict[str, int]:
    """The section's curves at one station: the upper and lower skin's from the leading edge aft, and the trailing edge strip's
    when the skins do not meet. Each spline leaves the leading edge vertically, as the airfoil's outline does, so the skin turns
    round the nose without a crease; the interpolation points between the ends are removed once the curve exists."""
    def spline(curve: np.ndarray, start: int, end: int | None, side: int) -> tuple[int, int]:
        tags = [start] + [occ.addPoint(x / MM, y_mm, z / MM) for x, z in curve[1:-1]]
        tags.append(end if end is not None else occ.addPoint(curve[-1, 0] / MM, y_mm, curve[-1, 1] / MM))
        tangents = [0.0] * (3 * len(tags))
        tangents[2] = float(side)
        tag = occ.addSpline(tags, tangents=tangents)
        occ.remove([(0, t) for t in tags[1:-1]])
        return tag, tags[-1]

    nose = occ.addPoint(section.upper[0, 0] / MM, y_mm, section.upper[0, 1] / MM)
    upper, aft = spline(section.upper, nose, None, +1)
    lower, lower_end = spline(section.lower, nose, aft if section.trailing_edge_closed else None, -1)
    curves = {"upper": upper, "lower": lower}
    if not section.trailing_edge_closed:
        curves["trailing"] = occ.addLine(lower_end, aft)
    return curves


def _build(gmsh, wing: Wing, section: Section, stations: tuple[float, ...]) -> list[tuple[str, int]]:
    """Every part as its own OpenCASCADE surface, in millimetres; (part name, surface tag) in the order they are made."""
    occ = gmsh.model.occ
    span = wing.geometry.half_span_m / MM
    root = _section_curves(occ, section, 0.0)
    parts: list[tuple[str, int]] = []
    for name, key in (("Upper skin", "upper"), ("Lower skin", "lower"), ("Trailing edge strip", "trailing")):
        if key in root:
            out = occ.extrude([(1, root[key])], 0, span, 0)
            parts.append((name, next(tag for dim, tag in out if dim == 2)))
    for name, x, top, bottom in zip(("Front spar", "Rear spar"), section.spar_x_m, section.spar_top_m, section.spar_bottom_m):
        line = occ.addLine(occ.addPoint(x / MM, 0.0, bottom / MM), occ.addPoint(x / MM, 0.0, top / MM))
        out = occ.extrude([(1, line)], 0, span, 0)
        parts.append((name, next(tag for dim, tag in out if dim == 2)))
    for k, y in enumerate(stations, start=1):
        curves = _section_curves(occ, section, y / MM)
        loop = [curves["upper"], curves["lower"]] + ([curves["trailing"]] if "trailing" in curves else [])
        parts.append((f"Rib {k}", occ.addPlaneSurface([occ.addCurveLoop(loop)])))
    occ.synchronize()
    return parts


LAYUP_OF = {"Upper skin": "skin", "Lower skin": "skin", "Trailing edge strip": "skin", "Front spar": "spar", "Rear spar": "spar"}


def _layup_of(name: str) -> str:
    return LAYUP_OF.get(name, "rib")


def _outward(name: str, section: Section, centers: np.ndarray) -> np.ndarray:
    """The direction each element's normal must point, for elements of one part with centroids `centers` (n, 3) in metres."""
    if name.startswith("Rib"):
        return np.tile([0.0, -1.0, 0.0], (len(centers), 1))
    if name.endswith("spar"):
        return np.tile([1.0, 0.0, 0.0], (len(centers), 1))
    # A skin: away from the middle of the box at the element's chord position, held between the spars.
    x = np.clip(centers[:, 0], *section.spar_x_m)
    middle = (np.interp(x, section.upper[:, 0], section.upper[:, 1]) + np.interp(x, section.lower[:, 0], section.lower[:, 1])) / 2
    away = centers - np.c_[x, centers[:, 1], middle]
    away[:, 1] = 0.0
    return away


def _mesh(gmsh, parts: list[tuple[str, int]], section: Section, element_size_m: float) -> ShellMesh:
    """Cut the parts where they meet, mesh them with quadrilaterals and order each element's corners to its part's normal."""
    occ = gmsh.model.occ
    out, children = occ.fragment([(2, tag) for _, tag in parts[:1]], [(2, tag) for _, tag in parts[1:]])
    occ.synchronize()
    owner: dict[int, str] = {}
    for (name, _), pieces in zip(parts, children):
        for dim, tag in pieces:
            if dim == 2:
                if tag in owner and owner[tag] != name:
                    raise ShapeError(f"{name} and {owner[tag]} overlap")
                owner[tag] = name
    size = element_size_m / MM
    # Recombination pairs triangles into quadrilaterals, and the subdivision then splits every element into quadrilaterals,
    # halving every edge: so the elements are first made twice the size asked for. Sizing by curvature is left off: on the
    # trailing edge's point it does not finish.
    gmsh.option.setNumber("Mesh.MeshSizeMin", size)
    gmsh.option.setNumber("Mesh.MeshSizeMax", 2 * size)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.Algorithm", 8)
    gmsh.option.setNumber("Mesh.RecombineAll", 1)
    gmsh.option.setNumber("Mesh.SubdivisionAlgorithm", 1)
    gmsh.model.mesh.generate(2)

    node_tags, coords, _ = gmsh.model.mesh.getNodes()
    index = {int(tag): k for k, tag in enumerate(node_tags)}
    nodes = np.asarray(coords, dtype=float).reshape(-1, 3) * MM
    elements, sets = [], {}
    for tag, name in sorted(owner.items()):
        types, _, connectivity = gmsh.model.mesh.getElements(2, tag)
        if [int(t) for t in types] != [3]:
            raise ShapeError(f"{name}: Gmsh left element types {[int(t) for t in types]}; only four-node quadrilaterals are used")
        quads = np.vectorize(index.__getitem__)(np.asarray(connectivity[0], dtype=np.int64).reshape(-1, 4))
        start = sum(len(e) for e in elements)
        sets.setdefault(name, []).extend(range(start, start + len(quads)))
        elements.append(quads)
    elements = np.vstack(elements)
    # Keep only the nodes the elements use, numbered from zero in Gmsh's order.
    used = np.unique(elements)
    renumber = np.full(nodes.shape[0], -1, dtype=np.int64)
    renumber[used] = np.arange(used.size)
    nodes, elements = nodes[used], renumber[elements]

    p = nodes[elements]  # (ne, 4, 3)
    normal = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
    for name, members in sets.items():
        members = np.asarray(members)
        wanted = _outward(name, section, p[members].mean(axis=1))
        flip = members[np.einsum("ij,ij->i", normal[members], wanted) < 0]
        elements[flip] = elements[flip][:, ::-1]
    if (np.linalg.norm(normal, axis=1) <= 1e-18).any():
        raise ShapeError("The mesh has an element without area")
    root = np.nonzero(np.abs(nodes[:, 1]) < 1e-9)[0]
    return ShellMesh(nodes=nodes, elements=elements, element_sets={name: np.array(sorted(m)) for name, m in sets.items()},
                     node_sets={"root": root})


def build_wing_shape(wing: Wing, step_path: Path | str | None = None, element_size_m: float | None = None) -> WingShape:
    """The wing's parts as mid-surfaces; with `step_path`, its STEP file there; with `element_size_m`, its shell mesh."""
    gmsh = _gmsh()
    if element_size_m is not None and not element_size_m > 0:
        raise ShapeError("The element size must be positive")
    section = mid_surface_section(wing)
    stations = rib_stations(wing)
    owned = not gmsh.isInitialized()
    if owned:
        gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("wing")
        built = _build(gmsh, wing, section, stations)
        areas = {name: gmsh.model.occ.getMass(2, tag) * MM**2 for name, tag in built}
        if step_path is not None:
            step_path = Path(step_path)
            with _quiet():  # OpenCASCADE's STEP writer prints its transfer statistics to the terminal
                gmsh.write(str(step_path))
            name_step_products(step_path, wing.name, [name for name, _ in built])
        mesh = _mesh(gmsh, built, section, element_size_m) if element_size_m is not None else None
    finally:
        if owned:
            gmsh.finalize()
        else:
            gmsh.model.remove()

    layups = {"skin": wing.skin, "spar": wing.spar, "rib": wing.rib}
    parts = []
    for name, _ in built:
        layup = layups[_layup_of(name)]
        thickness = None if layup is None else layup_thickness(layup)
        mass = None if layup is None else areas[name] * _areal_mass(layup)
        parts.append(Part(name=name, layup=_layup_of(name), thickness_m=thickness, area_m2=areas[name], mass_kg=mass))
    return WingShape(wing_name=wing.name, section=section, rib_stations_m=stations, parts=tuple(parts), mesh=mesh)


def part_table(shape: WingShape, units: str) -> dict:
    """The part table in a wing file's units (SI or US): what a CAD user needs beside the STEP file, which holds no thickness."""
    from anisotropy_engine.wing.wing_file import WING_UNITS

    u = WING_UNITS[units]
    (length, length_unit), (thickness, thickness_unit), (mass, mass_unit) = u["length"], u["thickness"], u["mass"]
    return {
        "wing": shape.wing_name,
        "units": {"thickness": thickness_unit, "area": f"{length_unit}^2", "mass": mass_unit, "step": "mm"},
        "parts": [{"name": part.name, "layup": part.layup,
                   "thickness": None if part.thickness_m is None else part.thickness_m / thickness,
                   "area": part.area_m2 / length**2,
                   "mass": None if part.mass_kg is None else part.mass_kg / mass} for part in shape.parts],
        "mass": None if shape.mass_kg is None else shape.mass_kg / mass,
    }


REFUSED = 2  # the exit status of a description the engine or the shape refuses; its reason is the last line on stderr


def main(argv: list[str] | None = None) -> None:
    """Write a wing file's STEP file and print its part table:
    `uv run --project fea --extra mesh python -m anisotropy_fea.wing_shape <wing file> <step file> [--mesh SIZE_MM] [--parts JSON]`.
    The wing file is TOML, or JSON of the same description (what the API holds, ADR-0118); `--parts` also writes the part table as JSON
    in the file's units. A description the engine or the shape refuses ends with status 2 and its reason on stderr."""
    import argparse
    import json
    import sys

    from anisotropy_engine.wing import load_wing
    from anisotropy_engine.wing.wing_file import WING_UNITS, wing_from_dict

    parser = argparse.ArgumentParser(description="Write a wing's shape as a STEP file, each part a surface at its mid-thickness.")
    parser.add_argument("wing_file", type=Path)
    parser.add_argument("step_file", type=Path)
    parser.add_argument("--mesh", type=float, metavar="SIZE_MM", help="also mesh it with elements of about this size, in mm")
    parser.add_argument("--parts", type=Path, metavar="JSON", help="also write the part table as JSON, in the wing file's units")
    args = parser.parse_args(argv)
    try:
        if args.wing_file.suffix.lower() == ".json":
            data = json.loads(args.wing_file.read_text(encoding="utf-8"))
            wing, _ = wing_from_dict(data)
        else:
            data, wing, _ = load_wing(args.wing_file)
        shape = build_wing_shape(wing, args.step_file, None if args.mesh is None else args.mesh * MM)
    except (ValueError, TypeError, KeyError) as exc:  # ShapeError is a ValueError
        print(str(exc) or exc.__class__.__name__, file=sys.stderr)
        raise SystemExit(REFUSED) from exc
    if args.parts is not None:
        args.parts.write_text(json.dumps(part_table(shape, data["units"])), encoding="utf-8")
    units = WING_UNITS[data["units"]]
    length, thickness, mass = units["length"], units["thickness"], units["mass"]
    area = (length[0] ** 2, f"{length[1]}^2")
    print(f"{shape.wing_name}: {len(shape.parts)} parts written to {args.step_file} (millimetres)")
    print(f"{'part':22} {'layup':6} {'thickness ' + thickness[1]:>15} {'area ' + area[1]:>12} {'mass ' + mass[1]:>10}")
    for part in shape.parts:
        t = "not given" if part.thickness_m is None else f"{part.thickness_m / thickness[0]:.4g}"
        m = "-" if part.mass_kg is None else f"{part.mass_kg / mass[0]:.4g}"
        print(f"{part.name:22} {part.layup:6} {t:>15} {part.area_m2 / area[0]:>12.4g} {m:>10}")
    if shape.mass_kg is not None:
        print(f"{'whole wing, one side':22} {'':6} {'':>15} {'':>12} {shape.mass_kg / mass[0]:>10.4g}")
    print("In a CAD program, thicken each part on both sides of its surface, so that the solid's whole thickness is the table's.")
    if shape.mesh is not None:
        m = shape.mesh
        print(f"Mesh: {m.nodes.shape[0]} nodes, {m.element_count} four-node shells, "
              + ", ".join(f"{name} {len(elements)}" for name, elements in m.element_sets.items()))


if __name__ == "__main__":
    main()
