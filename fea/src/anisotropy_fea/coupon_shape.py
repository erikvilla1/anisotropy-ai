"""A coupon's or a plate's shape from its spec: each part one solid at its real thickness, named, in a STEP file (ADR-0146).

The shape is built in Gmsh's OpenCASCADE kernel from the spec the setup check judged (`spec.CouponSpec`, in SI), the description the mesh
is cut from, so the STEP file a CAD program opens and the finite element model describe one part (the rule ADR-0116 set for the wing).
Nothing is typed here a second time: the width, the length, the tab length and the hole's diameter are the spec's geometry as
`mesh_for_spec` reads it, the hole sits where the mesher puts it (`mesher.hole_centre`), a dog-bone's outline is `dogbone.Outline`, whose
`width_at` the mesh's node rows follow, and the thickness is the sum of the plies of the section the model builds
(`femodel.laminate_section`). No mesh is cut for a shape: it has none, and a fine one would cost it minutes.

Axes, as the mesh's: x across the width from 0, y along the length from 0, z through the thickness with z = 0 at mid-thickness, where the
shell elements lie. The shape is built in millimetres, the unit its STEP file states.

The parts:
- the laminate (or, for one isotropic material, the coupon): the outline, a rectangle or a dog-bone, less the hole when there is one,
  through the whole thickness. One solid, whatever the number of plies.
- bonded tabs, when the coupon states them (`[tabs]`: a thickness and a bevel): one on each face at each end, as the page's sketch draws
  them (ADR-0072). Each is as wide as the coupon and as long as the gripped length at the coupon's face; its end toward the gauge section
  rises at the bevel angle from that face, so its outer face is shorter by thickness / tan(bevel). The finite element model holds the
  gripped length and does not carry the tabs as material; the part table says so.

A STEP file holds shape and names only: no plies, no fibre angles and no material. The part table (`part_table`) gives each part's layup,
ply count, thickness and material, and the same lines are written into the file's header (`FILE_DESCRIPTION`), where they travel with it.

What cannot be drawn without a rule nobody stated is refused with a `ShapeError`, never drawn by a guess: tabs that reach a dog-bone's
fillet (their outline there is not stated), and a bevel so shallow that the tab has no outer face left. A size under `SMALLEST_MM` is
refused before the kernel is asked, and anything the kernel still cannot build is refused in plain words: a refusal states sizes in the
coupon's own units and never a path, a module or the kernel's own message.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from .dogbone import Outline
from .femodel import laminate_section
from .mesher import hole_centre
from .spec import CouponSpec, full_angles, is_isotropic, layup_text, outline_of
from .units import UNIT_LABEL, from_si
from .wing_shape import ShapeError, _gmsh, _quiet, _step_string, name_step_products

MM = 1e-3  # metres per millimetre
ENDING = ".step"  # how the file's name ends: Gmsh picks the STEP writer by it
BOX_TOLERANCE_MM = 1e-6  # a solid whose bounding box is further than this from its stated size is refused
SMALLEST_MM = 1e-3  # a size under a micrometre is not drawn: far below any ply, and well above the 1e-7 mm at which the kernel merges points
# The header's description is a list of strings, each at most this long as written (escapes counted), so each line of it stays under 80
# characters and far under the 256 a description string may hold. Nothing is claimed of the file's other lines: the kernel writes them.
HEADER_WIDTH = 64
TAB_ENDS = (("Bottom", 0), ("Top", 1))  # the end at y = 0 and the end at y = length, as the mesh names its tab regions
TAB_FACES = (("top", 1), ("bottom", -1))  # the face at +z, where the last ply listed lies, and the face at -z (ADR-0004)


@dataclass(frozen=True)
class SolidPart:
    """One solid of the STEP file, as the file names it, with what a CAD user needs beside it."""

    name: str
    kind: str  # "laminate", "coupon" (one isotropic material) or "tab"
    layup: str | None  # the stacking sequence as written on the coupon, "isotropic", or None for a tab
    plies: int | None  # None for one isotropic material and for a tab
    ply_thickness_m: float | None
    thickness_m: float
    material: str | None  # the model's material name; a tab's as the coupon states it, None when it states none
    volume_m3: float  # as OpenCASCADE measures the solid
    in_model: bool  # whether the finite element model carries the part as material


@dataclass(frozen=True)
class FlatShape:
    """A coupon's or a plate's solids, the laminate first."""

    title: str  # the name of the whole in the STEP file: the coupon's designation
    parts: tuple[SolidPart, ...]


def _size(spec: CouponSpec, metres: float) -> str:
    """A length as a refusal states it: in the coupon's own unit, as the setup check's reasons are."""
    return f"{from_si(metres, 'length', spec.units):g} {UNIT_LABEL[spec.units]['length']}"


def tab_run(spec: CouponSpec) -> float:
    """How much shorter a bonded tab's outer face is than its face on the coupon, metres: thickness / tan(bevel), nothing for a square
    end. Refuses tabs that cannot be drawn from what the coupon states: an outer face under `SMALLEST_MM` is none."""
    tabs, g = spec.tabs, spec.geometry
    run = 0.0 if tabs.bevel >= 90.0 else tabs.thickness / math.tan(math.radians(tabs.bevel))
    if not g.tab_length - run >= SMALLEST_MM * MM:
        raise ShapeError(f"The tabs cannot be drawn: a bevel of {tabs.bevel:g} degrees over a thickness of {_size(spec, tabs.thickness)} runs "
                         f"{_size(spec, run)}, and the tab is {_size(spec, g.tab_length)} long, so it has no outer face left")
    outline = outline_of(spec)
    if outline is not None and g.tab_length > outline.half_length - outline.s_full + 1e-12:
        raise ShapeError(f"The tabs cannot be drawn: they are {_size(spec, g.tab_length)} long and the dog-bone's full width ends "
                         f"{_size(spec, outline.half_length - outline.s_full)} from each end, so they reach the fillet, where their outline is not stated")
    return run


def refuse_small_sizes(spec: CouponSpec, thickness: float) -> None:
    """Refuse, before the kernel is asked, a shape with a size it cannot hold: one that is not a finite number, or one under
    `SMALLEST_MM`. The kernel treats points 1e-7 mm apart as one and then fails with words of its own."""
    g = spec.geometry
    sizes = [("its length", g.length), ("its width", g.width), ("its thickness", thickness)]
    if g.hole_diameter is not None:
        sizes += [("the hole's diameter", g.hole_diameter), ("the material beside the hole", (g.width - g.hole_diameter) / 2)]
    if spec.tabs is not None:
        sizes += [("the tabs' thickness", spec.tabs.thickness), ("the tabs' length", g.tab_length)]
    for name, value in sizes:
        if not math.isfinite(value) or not math.isfinite(value / MM):
            raise ShapeError(f"The shape cannot be drawn: {name} is not a finite size")
        if value < SMALLEST_MM * MM:
            raise ShapeError(f"The shape cannot be drawn: {name} is {_size(spec, value)}, under the {_size(spec, SMALLEST_MM * MM)} that is the "
                             "smallest size drawn")


def _dogbone_loop(occ, outline: Outline, width_mm: float, z: float) -> int:
    """A dog-bone's outline as one closed loop of lines and arcs at height z, millimetres, centred on x = width / 2 as the mesh centres
    it. From mid-length outward one quarter is the narrow section's end, the fillet (centre level with that end, its radius beyond the
    narrow half-width), with an outer radius the second arc (centre level with where the full width begins) and the full width to the
    coupon's end; the other three quarters mirror it."""
    cx, cy = width_mm / 2, outline.half_length / MM
    corners = [(outline.a, outline.l)]  # (half-width, distance from mid-length), metres
    centres: list[tuple[float, float] | None] = [(outline.a + outline.R, outline.l)]  # of the curve from each corner to the next; None: a line
    if outline.RO is not None:
        corners.append((outline.half_width(outline.s_tangent), outline.s_tangent))
        centres.append((outline.b - outline.RO, outline.s_full))
    corners += [(outline.b, outline.s_full), (outline.b, outline.half_length)]
    centres.append(None)

    made: dict[tuple[float, float], int] = {}
    arc_centres: set[int] = set()

    def point(half: float, s: float, sx: int, sy: int) -> int:
        x, y = cx + sx * half / MM, cy + sy * s / MM
        key = (round(x, 9), round(y, 9))
        if key not in made:
            made[key] = occ.addPoint(x, y, z)
        return made[key]

    curves: list[int] = []
    first: int | None = None
    last: int | None = None
    # counterclockwise from the bottom right corner: up the right side, across the top, down the left side, back along the bottom
    for sx, sy, outward in ((1, -1, False), (1, 1, True), (-1, 1, False), (-1, -1, True)):
        order = list(range(len(corners))) if outward else list(range(len(corners) - 1, -1, -1))
        tags = [point(*corners[k], sx, sy) for k in order]
        if last is not None:
            curves.append(occ.addLine(last, tags[0]))  # between two quarters: a side of the narrow section, or an end of the coupon
        first = tags[0] if first is None else first
        for k0, k1, begin, finish in zip(order, order[1:], tags, tags[1:]):
            centre = centres[min(k0, k1)]
            if centre is None:
                curves.append(occ.addLine(begin, finish))
            else:
                middle = point(*centre, sx, sy)
                arc_centres.add(middle)
                curves.append(occ.addCircleArc(begin, middle, finish))
        last = tags[-1]
    curves.append(occ.addLine(last, first))
    occ.remove([(0, tag) for tag in arc_centres])  # a point left over would be written to the STEP file as a part of its own
    return occ.addCurveLoop(curves)


def _laminate(occ, spec: CouponSpec, thickness_mm: float) -> int:
    """The laminate as one solid: its outline, less the hole, from z = -thickness / 2 to +thickness / 2."""
    g = spec.geometry
    width, length, z = g.width / MM, g.length / MM, -thickness_mm / 2
    outline = outline_of(spec)
    if outline is None:
        points = [occ.addPoint(x, y, z) for x, y in ((0.0, 0.0), (width, 0.0), (width, length), (0.0, length))]
        loops = [occ.addCurveLoop([occ.addLine(points[k], points[(k + 1) % 4]) for k in range(4)])]
    else:
        loops = [_dogbone_loop(occ, outline, width, z)]
    if g.hole_diameter is not None:
        cx, cy = hole_centre(g.width, g.length)
        loops.append(occ.addCurveLoop([occ.addCircle(cx / MM, cy / MM, z, g.hole_diameter / 2 / MM)]))
    made = occ.extrude([(2, occ.addPlaneSurface(loops))], 0.0, 0.0, thickness_mm)
    solids = [tag for dim, tag in made if dim == 3]
    if len(solids) != 1:
        raise ShapeError("The laminate did not come out as one solid")
    return solids[0]


def _tab(occ, spec: CouponSpec, thickness_mm: float, run_mm: float, end: int, face: int) -> int:
    """One bonded tab as a solid: its profile along the length and through the thickness, swept across the width. `end` is 0 for the end
    at y = 0 and 1 for the end at y = length; `face` is +1 for the face at +z and -1 for the face at -z."""
    g = spec.geometry
    width, length, tab_length, tab_thickness = g.width / MM, g.length / MM, g.tab_length / MM, spec.tabs.thickness / MM
    y0, into = (length, -1.0) if end else (0.0, 1.0)
    z0 = face * thickness_mm / 2
    profile = ((y0, z0), (y0 + into * tab_length, z0), (y0 + into * (tab_length - run_mm), z0 + face * tab_thickness), (y0, z0 + face * tab_thickness))
    points = [occ.addPoint(0.0, y, z) for y, z in profile]
    loop = occ.addCurveLoop([occ.addLine(points[k], points[(k + 1) % 4]) for k in range(4)])
    made = occ.extrude([(2, occ.addPlaneSurface([loop]))], width, 0.0, 0.0)
    solids = [tag for dim, tag in made if dim == 3]
    if len(solids) != 1:
        raise ShapeError("A tab did not come out as one solid")
    return solids[0]


def _in_box(found: tuple[float, ...], expected: tuple[float, ...]) -> bool:
    return all(abs(a - b) <= BOX_TOLERANCE_MM + 2e-7 for a, b in zip(found, expected))  # OpenCASCADE pads a box by 1e-7


def header_lines(shape: FlatShape) -> list[str]:
    """What the STEP file says of itself in its header, in millimetres: the axes, each part with its layup, ply count, thickness and
    material, and that the file holds no plies."""
    lines = [f"{shape.title}: shape only, in millimetres. x across the width, y along the length, z through the thickness, z = 0 at "
             "mid-thickness."]
    for part in shape.parts:
        thick = f"{part.thickness_m / MM:.6g} mm thick"
        material = part.material or "material not stated"
        if part.kind == "tab":
            lines.append(f"{part.name}: bonded tab, {thick}, {material}. Drawn as stated; the finite element model holds the gripped "
                         "length and does not carry the tab as material.")
        elif part.plies is None:
            lines.append(f"{part.name}: one isotropic material, {thick}, {material}.")
        else:
            lines.append(f"{part.name}: layup {part.layup}, {part.plies} plies of {part.ply_thickness_m / MM:.6g} mm, {thick}, {material}.")
    if any(part.plies is not None for part in shape.parts):
        lines.append("A STEP file carries no plies: the layup is stated above. Ply angles are counted from y; plies are listed from the "
                     "face at -z up.")
    return lines


def name_step_solids(path: Path, title: str, names: list[str]) -> None:
    """Give the solids of a STEP file Gmsh wrote their parts' names. Several solids are an assembly named `title` with one product each
    (`wing_shape.name_step_products`). One solid alone is written as one product and no assembly, and takes its part's name; the title
    is then in the header's description. A file with another number of products than names is refused rather than half named."""
    if len(names) != 1:
        name_step_products(path, title, names)
        return
    text = path.read_text(encoding="ascii")
    pattern = re.compile(r"PRODUCT\('(Open CASCADE STEP translator [0-9.]+ \d+)',\s*'\1'")
    if len(pattern.findall(text)) != 1 or text.count("PRODUCT('") != 1:
        raise ShapeError("The STEP file does not hold the one part that was written; it was not named")
    label = _step_string(names[0])
    path.write_text(pattern.sub(lambda _: f"PRODUCT('{label}',\n  '{label}'", text), encoding="ascii")


def header_strings(line: str, width: int = HEADER_WIDTH) -> list[str]:
    """One sentence as the strings of the header's description, each at most `width` characters as written in the file (an apostrophe
    and a backslash count twice, a letter outside ASCII as its escape). It is broken between words; a word longer than a string, a long
    layup, is broken after a `/`; one still longer is cut between two characters. Read one after another, the strings are the sentence."""
    written = lambda text: len(_step_string(text))  # noqa: E731
    atoms = [(bit, " " if k == 0 else "") for word in line.split()
             for k, bit in enumerate([word] if written(word) <= width else re.findall(r"[^/]*/|[^/]+", word))]
    pieces: list[str] = []
    current = ""
    for bit, glue in atoms:
        joined = current + (glue if current else "") + bit
        if current and written(joined) > width:
            pieces.append(current)
            current = bit
        else:
            current = joined
        while written(current) > width:
            cut = max(n for n in range(1, len(current)) if written(current[:n]) <= width or n == 1)
            pieces.append(current[:cut])
            current = current[cut:]
    return pieces + ([current] if current else [])


def describe_step(path: Path, lines: list[str]) -> None:
    """Write `lines` into a STEP file's header as its description, in place of the writer's own ("Open CASCADE Model"): a list of
    strings (`header_strings`), one to a line of the file, each line of the description under 80 characters. A file whose header is not
    the one Gmsh's OpenCASCADE writes is refused rather than half described."""
    text = path.read_text(encoding="ascii")
    pattern = re.compile(r"FILE_DESCRIPTION\(\('Open CASCADE Model'\),\s*'2;1'\);")
    if len(pattern.findall(text)) != 1:
        raise ShapeError("The STEP file's header is not the one expected; it was not described")
    strings = ",\n  ".join(f"'{_step_string(piece)}'" for line in lines for piece in header_strings(line))
    path.write_text(pattern.sub(lambda _: f"FILE_DESCRIPTION((\n  {strings}),'2;1');", text), encoding="ascii")


def build_coupon_shape(spec: CouponSpec, step_path: Path | str | None = None) -> FlatShape:
    """The spec's parts as solids; with `step_path`, its STEP file there, each solid under its part's name and the part table's lines
    in the header. The spec is in SI, as the model's is. No mesh is cut. Raises `ShapeError` for a shape that cannot be drawn, and
    writes no file then."""
    if not spec.si:
        raise ShapeError("The shape is built from a spec in SI")
    if step_path is not None and Path(step_path).suffix.lower() not in (".step", ".stp"):
        raise ShapeError("A STEP file's name ends in .step or .stp")
    g = spec.geometry
    material, section = laminate_section(spec)
    thickness = sum(ply.thickness_m for ply in section.plies)
    isotropic = is_isotropic(spec)
    plies = None if isotropic else len(full_angles(spec))
    refuse_small_sizes(spec, thickness)
    run = tab_run(spec) if spec.tabs is not None else None
    title = spec.coupon.designation if spec.coupon is not None else "Model"
    stated = [("Coupon" if isotropic else "Laminate", "coupon" if isotropic else "laminate", layup_text(spec), plies,
               None if isotropic else section.plies[0].thickness_m, thickness, material.name, True)]
    if run is not None:
        stated += [(f"{end} tab, {face} face", "tab", None, None, None, spec.tabs.thickness, spec.tabs.material, False)
                   for end, _ in TAB_ENDS for face, _ in TAB_FACES]

    gmsh = _gmsh()
    owned = not gmsh.isInitialized()
    if owned:
        gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("coupon")
        occ = gmsh.model.occ
        try:
            tags = [_laminate(occ, spec, thickness / MM)]
            if run is not None:
                tags += [_tab(occ, spec, thickness / MM, run / MM, end, face) for _, end in TAB_ENDS for _, face in TAB_FACES]
            occ.synchronize()
            solids = len(gmsh.model.getEntities(3))
            box = occ.getBoundingBox(3, tags[0])
            volumes = [occ.getMass(3, tag) * MM**3 for tag in tags]
        except ShapeError:
            raise
        except Exception as exc:  # the kernel's own failure (its message names its internals): a plain refusal, the cause chained for the log
            raise ShapeError("The shape cannot be drawn from these sizes: the geometry kernel could not build it") from exc
        if solids != len(stated):
            raise ShapeError("The model's solids were not all built")
        # the laminate fills the box the model states, to the tolerance: a wrong shape is refused here, before any file is written
        if not _in_box(box, (0.0, 0.0, -thickness / MM / 2, g.width / MM, g.length / MM, thickness / MM / 2)):
            raise ShapeError("The laminate's solid does not have the model's length, width and thickness")
        if min(volumes) <= 0.0:
            raise ShapeError("A solid of the model has no volume")
        shape = FlatShape(title=title, parts=tuple(SolidPart(*row[:7], volume_m3=volume, in_model=row[7]) for row, volume in zip(stated, volumes)))
        if step_path is not None:
            step_path = Path(step_path)
            try:
                with _quiet():  # OpenCASCADE's STEP writer prints its transfer statistics to the terminal
                    gmsh.write(str(step_path))
            except Exception as exc:  # as above: the kernel's words stay out of the refusal
                step_path.unlink(missing_ok=True)
                raise ShapeError("The shape was built, and its STEP file could not be written") from exc
            try:
                # the writer puts the solids in the order of their tags
                name_step_solids(step_path, title, [part.name for _, part in sorted(zip(tags, shape.parts), key=lambda made: made[0])])
                describe_step(step_path, header_lines(shape))
            except ShapeError:
                step_path.unlink(missing_ok=True)  # never a file half named
                raise
    finally:
        if owned:
            gmsh.finalize()
        else:
            gmsh.model.remove()
    return shape


def part_table(shape: FlatShape, units: str) -> dict:
    """The part table in the coupon's unit system: what a CAD user needs beside the STEP file, which holds no plies. Each part's layup as
    written on the coupon, its ply count, the thickness of a ply and of the part, its material, its volume, and whether the finite
    element model carries it as material."""
    label = UNIT_LABEL[units]["length"]
    length = lambda value: None if value is None else from_si(value, "length", units)  # noqa: E731
    return {
        "title": shape.title,
        "units": {"length": label, "volume": f"{label}³", "step": "mm"},
        "parts": [{"name": part.name, "kind": part.kind, "layup": part.layup, "plies": part.plies, "ply_thickness": length(part.ply_thickness_m),
                   "thickness": length(part.thickness_m), "material": part.material, "volume": part.volume_m3 * from_si(1.0, "length", units) ** 3,
                   "in_model": part.in_model} for part in shape.parts],
    }


def read_step_solids(step_path: Path | str) -> list[dict]:
    """Every solid of a STEP file as a program that opens it would find it, in the file's order: its name, its volume (mm^3), its
    bounding box (mm: x0, y0, z0, x1, y1, z1) and its round holes (each one's centre x, y and diameter, mm: the faces that are a whole
    cylinder, which a fillet's face is not)."""
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
        found = []
        for dim, tag in solids:
            if dim != 3:
                continue
            holes = []
            for face_dim, face in gmsh.model.getBoundary([(3, tag)], oriented=False):
                if gmsh.model.getType(face_dim, face) != "Cylinder":
                    continue
                low, high = gmsh.model.getParametrizationBounds(face_dim, face)
                if abs((high[0] - low[0]) - 2 * math.pi) < 1e-9:  # all the way round
                    x0, y0, _, x1, y1, _ = gmsh.model.getBoundingBox(face_dim, face)
                    holes.append({"x": (x0 + x1) / 2, "y": (y0 + y1) / 2, "diameter": ((x1 - x0) + (y1 - y0)) / 2})
            found.append({"name": gmsh.model.getEntityName(3, tag).rsplit("/", 1)[-1], "volume": gmsh.model.occ.getMass(3, tag),
                          "box": tuple(gmsh.model.getBoundingBox(3, tag)), "holes": holes})
        return found
    finally:
        if owned:
            gmsh.finalize()
        else:
            gmsh.model.remove()
