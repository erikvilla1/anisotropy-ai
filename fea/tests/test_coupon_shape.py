"""A coupon's or a plate's STEP file (ADR-0146): every kind the workspace builds is drawn from the model the mesh is cut from, written,
read back and measured against the model's own sizes and against the mesh; each part is named, the part table's thickness is the
laminate's, the file states millimetres, and a shape that cannot be drawn from what is stated is refused with no file written.

Every test that builds a shape skips with a reason when Gmsh is not installed (`uv sync --extra mesh`).
"""

import copy
import json
import math
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.coupon_shape import (
    DRAWN_SIZES, HEADER_WIDTH, MM, NOT_DRAWN, SMALLEST_MM, build_coupon_shape, describe_step, header_lines, name_step_solids, part_table,
    read_step_solids, tab_run,
)
from anisotropy_fea.femodel import build_model
from anisotropy_fea.intake import FORM_VERSION, size_that_fits
from anisotropy_fea.mesher import gmsh_available, hole_centre
from anisotropy_fea.spec import MOST_ELEMENTS_STATED, Dogbone, Geometry, Tabs, outline_of, spec_from_table, spec_plies, to_si
from anisotropy_fea.wing_shape import ShapeError

from public_coupon import DESIGNATION
from test_intake import PUBLIC_FILL
from test_wing_shape import part21_text

STUDIO = Path(__file__).parents[1] / "tools" / "studio_tool.py"
needs_gmsh = pytest.mark.skipif(gmsh_available() is None,
                                reason="Gmsh is not available: from fea/ run `uv sync --extra mesh` (on Linux also apt install libglu1-mesa)")
ON_THE_OUTLINE_MM = 1e-6  # how far a node on the mesh's edge may lie from the STEP file's outline: a nanometre
SIZE_MM = 1e-6  # how far a size read back from the STEP file may be from the model's


def table_of(name: str) -> dict:
    return tomllib.loads(paths.spec_path(name).read_text(encoding="utf-8"))


def model_of(table: dict):
    return build_model(to_si(spec_from_table(copy.deepcopy(table), "0" * 64)))


def thickness_of(model) -> float:
    """The thickness the finite element model itself holds, metres: the sum of its section's plies. The shape is held against it."""
    return sum(ply.thickness_m for ply in model.section.plies)


def strip(**tabs) -> dict:
    """The public D3039 strip, 250 by 25 mm gripped over 56 mm at each end; with `tabs`, bonded tabs of that thickness and bevel."""
    table = table_of("d3039-im7-8552")
    if tabs:
        table["tabs"] = tabs
    return table


def dogbone_type_iv() -> dict:
    """A dog-bone with a reverse curve, in the size ASTM D638 gives its Type IV: 115 by 19 mm, narrowing to 6 mm over 33 mm, a 14 mm
    fillet and a 25 mm outer radius."""
    table = table_of("d638-type-i-plastic")
    table["test_method"]["variant"] = "IV"
    table["geometry"] = {"length": 115.0, "width": 19.0, "thickness": 3.2, "tab_length": 25.0,
                         "dogbone": {"narrow_width": 6.0, "narrow_length": 33.0, "radius": 14.0, "outer_radius": 25.0}}
    table["mesh"] = {"mesher": "structured", "element_order": 1, "nx": 8, "ny": 230}
    table["probes"] = {}
    table["strain"]["gauge_length"] = 25.0
    return table


def plate_with_a_hole() -> dict:
    table = table_of("plate-pressure-isotropic")
    table["geometry"]["hole_diameter"] = 20.0  # and no tab length: a plate set up in the workspace states none
    table["mesh"] = {"mesher": "gmsh", "element_order": 1, "element_size": 5.0,
                     "hole": {"circumferential": 32, "radial_layers": 4, "ring_ratio": 2.0, "growth": 1.2}}
    return table


def four_point() -> dict:
    table = table_of("three-point-im7-8552")
    del table["coupon"]
    table.update(title="Four-point bending, IM7/8552 [45/0/-45/90]s", kind="four_point_bending")
    table["geometry"]["load_span"] = 24.0
    return table


def shear() -> dict:
    table = table_of("unnotched-im7-8552-nodal")
    table.update(title="In-plane shear, IM7/8552 [45/-45]2s", kind="shear_pm45")
    table["layup"]["angles"] = [45, -45, 45, -45]
    return table


# Every kind the workspace builds (spec.Kind), and the outlines and parts each may have: name -> the spec's table
KINDS = {
    "unnotched tension, gripped strip": strip,
    "unnotched tension, bonded tabs with a 7 degree bevel": lambda: strip(thickness=1.5, bevel=7.0, material="E-glass/epoxy"),
    "unnotched tension, bonded tabs with a square end": lambda: strip(thickness=1.5, bevel=90.0),
    "unnotched tension, dog-bone": lambda: table_of("d638-type-i-plastic"),
    "unnotched tension, dog-bone with an outer radius": dogbone_type_iv,
    "open-hole tension": lambda: table_of("open-hole-im7-8552"),
    "compression": lambda: table_of("compression-im7-8552"),
    "in-plane shear": shear,
    "three-point bending": lambda: table_of("three-point-im7-8552"),
    "four-point bending": four_point,
    "plate": lambda: table_of("plate-pressure-isotropic"),
    "plate with a hole": plate_with_a_hole,
}


def test_the_kinds_tried_here_are_every_kind_a_spec_may_be():
    from typing import get_args

    from anisotropy_fea.spec import Kind

    assert {model_of(make()).spec.kind for make in KINDS.values()} == set(get_args(Kind))


@pytest.fixture(scope="module", params=list(KINDS), ids=list(KINDS))
def written(request, tmp_path_factory):
    """One kind's model, its shape, its STEP file and the file read back."""
    if gmsh_available() is None:
        pytest.skip("Gmsh is not available")
    model = model_of(KINDS[request.param]())
    step = tmp_path_factory.mktemp("shape") / "coupon.step"
    shape = build_coupon_shape(model.spec, step)
    return model, shape, step, read_step_solids(step)


def mesh_edge_sides(mesh) -> list[tuple[int, int, int | None]]:
    """The element sides on the mesh's own boundary, those only one element has: the two corner nodes of each and, on a second-order
    mesh, its midside node."""
    sides: dict[tuple[int, int], list] = {}
    for e, nodes in enumerate(mesh.corners):
        for k in range(4):
            a, b = int(nodes[k]), int(nodes[(k + 1) % 4])
            entry = sides.setdefault((min(a, b), max(a, b)), [0, None])
            entry[0] += 1
            entry[1] = None if mesh.midside is None else int(mesh.midside[e][k])
    return [(a, b, middle) for (a, b), (count, middle) in sides.items() if count == 1]


def mesh_edge_nodes(mesh) -> np.ndarray:
    """The corner nodes on the mesh's own boundary: the ends of every element side that only one element has."""
    return np.unique([node for a, b, _ in mesh_edge_sides(mesh) for node in (a, b)])


def mesh_area(mesh) -> float:
    p = mesh.xy[mesh.corners]
    return float(sum(0.5 * abs(sum(q[i, 0] * q[(i + 1) % 4, 1] - q[(i + 1) % 4, 0] * q[i, 1] for i in range(4))) for q in p))


def distance_to_the_outline(step: Path, z_mm: float, points_mm: np.ndarray) -> float:
    """The furthest any of `points_mm` (n, 2) lies from the curves of the STEP file's first solid at the height z: its outline there."""
    import gmsh

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("measure")
        solids = gmsh.model.occ.importShapes(str(step))
        gmsh.model.occ.synchronize()
        faces = gmsh.model.getBoundary([next(entity for entity in solids if entity[0] == 3)], oriented=False)
        curves = {abs(tag) for _, tag in gmsh.model.getBoundary(faces, combined=False, oriented=False)}
        level = [c for c in curves if all(abs(gmsh.model.getBoundingBox(1, c)[k] - z_mm) < SIZE_MM for k in (2, 5))]
        assert level, "the solid has no curve at that height"
        return max(min(float(np.linalg.norm(np.array(gmsh.model.getClosestPoint(1, c, [x, y, z_mm])[0]) - [x, y, z_mm])) for c in level)
                   for x, y in points_mm)
    finally:
        gmsh.finalize()


@needs_gmsh
def test_the_laminate_is_one_solid_of_the_models_length_width_and_thickness(written):
    model, shape, _, solids = written
    g, t = model.spec.geometry, thickness_of(model)
    laminate = solids[0]
    assert laminate["name"] == shape.parts[0].name == ("Coupon" if model.spec.layup is None else "Laminate")
    expected = (0.0, 0.0, -t / 2 / MM, g.width / MM, g.length / MM, t / 2 / MM)
    assert laminate["box"] == pytest.approx(expected, abs=SIZE_MM)
    # and of the mesh's own extents: the shell elements lie at z = 0, the solid's mid-thickness
    low, high = model.mesh.xy.min(axis=0) / MM, model.mesh.xy.max(axis=0) / MM
    assert (laminate["box"][0], laminate["box"][1], laminate["box"][3], laminate["box"][4]) == pytest.approx((*low, *high), abs=SIZE_MM)
    assert laminate["box"][2] + laminate["box"][5] == pytest.approx(0.0, abs=SIZE_MM)


@needs_gmsh
def test_every_node_on_the_meshs_edge_lies_on_the_step_files_outline(written):
    model, _, step, _ = written
    edge = model.mesh.xy[mesh_edge_nodes(model.mesh)] / MM
    assert len(edge) >= 8
    assert distance_to_the_outline(step, -thickness_of(model) / 2 / MM, edge) < ON_THE_OUTLINE_MM
    # a point of the mesh's inside is not on it, so the measure can tell
    inside = model.mesh.centroids()[model.mesh.nearest_element((model.spec.geometry.width / 2, model.spec.geometry.length / 4))] / MM
    assert distance_to_the_outline(step, -thickness_of(model) / 2 / MM, inside[None, :]) > 0.1


@needs_gmsh
@pytest.mark.parametrize("name, curved_mm", [("open-hole-im7-8552", 3.0), ("d638-type-i-plastic", 76.0), ("d3039-im7-8552", None)])
def test_on_a_second_order_mesh_the_corner_nodes_lie_on_the_outline_and_a_midside_node_on_a_curve_lies_on_its_chord(tmp_path, name, curved_mm):
    """What is true of a second-order mesh, measured: its corner nodes lie on the STEP file's outline as a first-order mesh's do; a
    midside node on the boundary is the middle of the straight line between its two corners, so on a straight edge it is on the outline
    and on a curve (the hole, a fillet of `curved_mm` radius) it is inside it by that chord's sagitta, c^2 / (8 r) for a chord c."""
    table = table_of(name)
    table["mesh"]["element_order"] = 2
    model = model_of(table)
    step = tmp_path / "coupon.step"
    build_coupon_shape(model.spec, step)
    mesh, z = model.mesh, -thickness_of(model) / 2 / MM
    sides = mesh_edge_sides(mesh)
    assert all(middle is not None for _, _, middle in sides)
    xy = mesh.xy / MM
    assert distance_to_the_outline(step, z, xy[mesh_edge_nodes(mesh)]) < ON_THE_OUTLINE_MM
    for a, b, middle in sides:
        assert xy[middle] == pytest.approx((xy[a] + xy[b]) / 2, abs=1e-9)  # on the chord, at its middle
    gaps = np.array([distance_to_the_outline(step, z, xy[[middle]]) for _, _, middle in sides])
    chords = np.array([float(np.linalg.norm(xy[a] - xy[b])) for a, b, _ in sides])
    if curved_mm is None:
        assert gaps.max() < ON_THE_OUTLINE_MM  # every edge is straight: the midside nodes are on the outline too
        return
    off = gaps > ON_THE_OUTLINE_MM
    assert off.any() and gaps.max() > 1e-4, "a curve's midside nodes are off the outline by an amount that can be measured"
    # the sagitta of each chord on the tightest curve bounds its gap; on that curve it is the gap
    sagitta = curved_mm - np.sqrt(curved_mm**2 - (chords / 2) ** 2)
    assert (gaps[off] <= sagitta[off] + ON_THE_OUTLINE_MM).all()
    worst = int(np.argmax(gaps))
    assert gaps[worst] == pytest.approx(sagitta[worst], abs=1e-6 if name == "open-hole-im7-8552" else 1e-3)


@needs_gmsh
def test_the_solids_volume_is_the_outlines_area_times_the_thickness_and_the_meshs_area_agrees(written):
    model, shape, _, solids = written
    g, t = model.spec.geometry, thickness_of(model)
    outline = outline_of(model.spec)
    if outline is None:
        area = g.width * g.length
    else:  # the outline's own width, summed along the length
        y = np.linspace(0.0, g.length, 400_001)
        widths = np.array([outline.width_at(float(v)) for v in y])
        area = float(np.sum((widths[1:] + widths[:-1]) / 2 * np.diff(y)))
    if g.hole_diameter is not None:
        area -= math.pi * g.hole_diameter**2 / 4
    assert solids[0]["volume"] * MM**3 == pytest.approx(area * t, rel=1e-9 if outline is None else 1e-7)
    assert shape.parts[0].volume_m3 == pytest.approx(solids[0]["volume"] * MM**3, rel=1e-12)
    # the mesh's elements have straight sides, so round a hole and along a fillet they cover a little more or less than the solid
    curved = outline is not None or g.hole_diameter is not None
    assert mesh_area(model.mesh) == pytest.approx(area, rel=2e-3 if curved else 1e-12)
    if outline is None and g.hole_diameter is not None:  # the hole's ring of nodes is a polygon inside the circle
        assert mesh_area(model.mesh) > area


@needs_gmsh
def test_a_hole_is_where_the_mesh_has_it_and_as_wide(written):
    model, _, _, solids = written
    g = model.spec.geometry
    if g.hole_diameter is None:
        assert solids[0]["holes"] == []
        return
    (hole,) = solids[0]["holes"]
    cx, cy = hole_centre(g.width, g.length)
    assert (hole["x"], hole["y"], hole["diameter"]) == pytest.approx((cx / MM, cy / MM, g.hole_diameter / MM), abs=SIZE_MM)
    ring = model.mesh.xy[model.mesh.node_sets["Hole"]] / MM  # the mesh's own nodes round the hole
    assert ring.mean(axis=0) == pytest.approx((hole["x"], hole["y"]), abs=SIZE_MM)
    assert np.hypot(*(ring - (hole["x"], hole["y"])).T) == pytest.approx(hole["diameter"] / 2, abs=SIZE_MM)


@needs_gmsh
def test_a_dog_bones_narrow_section_is_as_wide_in_the_file_as_in_the_mesh(written):
    model, _, step, _ = written
    outline = outline_of(model.spec)
    if outline is None:
        return
    g, t = model.spec.geometry, thickness_of(model)
    centre = g.width / 2
    # the sides of the narrow section at mid-length and at its ends, the full width's corners, and the points where the arcs meet
    stations = [0.0, outline.l, -outline.l, outline.s_tangent, -outline.s_tangent, outline.s_full, -outline.s_full, outline.half_length * 0.999]
    points = np.array([(centre + side * outline.half_width(s), outline.half_length + s) for s in stations for side in (1, -1)]) / MM
    assert distance_to_the_outline(step, -t / 2 / MM, points) < ON_THE_OUTLINE_MM
    # the mesh's node row at mid-length spans the narrow width, and the nodes a hair inside it are off the file's outline
    row = model.mesh.xy[np.abs(model.mesh.xy[:, 1] - g.length / 2) < 1e-9, 0]
    assert row.max() - row.min() == pytest.approx(g.dogbone.narrow_width, rel=1e-12)
    assert distance_to_the_outline(step, -t / 2 / MM, np.array([[(centre + outline.a) / MM - 0.01, g.length / 2 / MM]])) == pytest.approx(0.01, abs=ON_THE_OUTLINE_MM)


@needs_gmsh
def test_bonded_tabs_are_four_named_solids_on_the_gripped_length_and_the_gripped_strip_has_none(written):
    model, shape, _, solids = written
    spec, t = model.spec, thickness_of(model)
    g = spec.geometry
    if spec.tabs is None:
        assert len(solids) == len(shape.parts) == 1
        return
    names = ["Bottom tab, top face", "Bottom tab, bottom face", "Top tab, top face", "Top tab, bottom face"]
    assert [solid["name"] for solid in solids[1:]] == [part.name for part in shape.parts[1:]] == names
    run = tab_run(spec)
    assert run == pytest.approx(0.0 if spec.tabs.bevel == 90 else spec.tabs.thickness / math.tan(math.radians(spec.tabs.bevel)))
    for solid, part in zip(solids[1:], shape.parts[1:]):
        x0, y0, z0, x1, y1, z1 = solid["box"]
        bottom_end, top_face = solid["name"].startswith("Bottom"), solid["name"].endswith("top face")
        assert (x0, x1) == pytest.approx((0.0, g.width / MM), abs=SIZE_MM)
        assert (y0, y1) == pytest.approx((0.0, g.tab_length / MM) if bottom_end else ((g.length - g.tab_length) / MM, g.length / MM), abs=SIZE_MM)
        assert (z0, z1) == pytest.approx((t / 2 / MM, (t / 2 + spec.tabs.thickness) / MM) if top_face
                                         else (-(t / 2 + spec.tabs.thickness) / MM, -t / 2 / MM), abs=SIZE_MM)
        # a trapezoid along the length: the whole length on the coupon, less the bevel's run at the outer face
        assert solid["volume"] * MM**3 == pytest.approx(g.width * spec.tabs.thickness * (g.tab_length - run / 2), rel=1e-9)
        assert not part.in_model and part.thickness_m == spec.tabs.thickness and part.material == spec.tabs.material and part.plies is None
        # the mesh grips the same length: the elements of its tab region end where the tab's solid does
        band = model.mesh.xy[np.unique(model.mesh.corners[model.mesh.element_sets["Tab-Bottom" if bottom_end else "Tab-Top"]]), 1] / MM
        assert (band.min(), band.max()) == pytest.approx((y0, y1), abs=SIZE_MM)


def tab_faces(step: Path) -> dict[str, list[tuple[float, ...]]]:
    """Every tab solid of a STEP file by its name: the bounding box of each of its faces (mm)."""
    import gmsh

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("tabs")
        solids = [entity for entity in gmsh.model.occ.importShapes(str(step)) if entity[0] == 3]
        gmsh.model.occ.synchronize()
        return {gmsh.model.getEntityName(3, tag).rsplit("/", 1)[-1]: [tuple(gmsh.model.getBoundingBox(2, abs(face)))
                                                                    for _, face in gmsh.model.getBoundary([(3, tag)], oriented=False)]
                for _, tag in solids[1:]}
    finally:
        gmsh.finalize()


def check_the_bevels(step: Path, length: float, tab_length: float, half: float, tab_thickness: float, bevel: float) -> None:
    """Each tab's bevel is on its end toward the gauge section and rises at the stated angle from the coupon's face: the tab's face on
    the coupon runs the whole gripped length from the coupon's end, its outer face stops short of the gauge end by the bevel's run, and
    the one inclined face joins the two there. Sizes in millimetres, `half` the laminate's half thickness, `bevel` in degrees."""
    run = tab_thickness / math.tan(math.radians(bevel))
    found = tab_faces(step)
    assert len(found) == 4
    for name, boxes in found.items():
        end, gauge = (0.0, tab_length) if name.startswith("Bottom") else (length, length - tab_length)
        toward = 1.0 if gauge > end else -1.0  # the direction from the coupon's end to the gauge section, along y
        side = 1.0 if name.endswith("top face") else -1.0
        on_coupon, outer = (next(box for box in boxes if abs(box[2] - z) < SIZE_MM and abs(box[5] - z) < SIZE_MM)
                            for z in (side * half, side * (half + tab_thickness)))
        assert sorted((on_coupon[1], on_coupon[4])) == pytest.approx(sorted((end, gauge)), abs=SIZE_MM), name
        assert sorted((outer[1], outer[4])) == pytest.approx(sorted((end, gauge - toward * run)), abs=SIZE_MM), name
        (inclined,) = [box for box in boxes if box[3] - box[0] > SIZE_MM and box[4] - box[1] > SIZE_MM and box[5] - box[2] > SIZE_MM]
        assert sorted((inclined[1], inclined[4])) == pytest.approx(sorted((gauge - toward * run, gauge)), abs=SIZE_MM), name
        assert math.degrees(math.atan2(inclined[5] - inclined[2], inclined[4] - inclined[1])) == pytest.approx(bevel, abs=1e-4), name  # a box read back carries the kernel's 1e-7 mm margin


@needs_gmsh
@pytest.mark.parametrize("bevel", [7.0, 15.0, 45.0])
def test_a_tabs_bevel_is_on_its_end_toward_the_gauge_section_at_the_stated_angle(tmp_path, bevel):
    model = model_of(strip(thickness=1.5, bevel=bevel))
    step = tmp_path / "coupon.step"
    build_coupon_shape(model.spec, step)
    g = model.spec.geometry
    check_the_bevels(step, g.length / MM, g.tab_length / MM, thickness_of(model) / 2 / MM, 1.5, bevel)


@needs_gmsh
def test_the_check_of_the_bevels_fails_for_a_tab_bevelled_at_the_coupons_end_or_overhanging(tmp_path, monkeypatch):
    """The check above, tried on two wrong tabs of the same box and the same volume as the right one: one bevelled at the coupon's
    end, one whose outer face overhangs the gauge section. Every other test of this file passes for both."""
    from anisotropy_fea import coupon_shape

    def wrong(profile_of):
        def tab(occ, spec, thickness_mm, run_mm, end, face):
            g = spec.geometry
            width, length, tab_length, tab_thickness = g.width / MM, g.length / MM, g.tab_length / MM, spec.tabs.thickness / MM
            y0, into = (length, -1.0) if end else (0.0, 1.0)
            z0 = face * thickness_mm / 2
            points = [occ.addPoint(0.0, y0 + into * y, z0 + face * z) for y, z in profile_of(tab_length, tab_thickness, run_mm)]
            loop = occ.addCurveLoop([occ.addLine(points[k], points[(k + 1) % 4]) for k in range(4)])
            return next(tag for dim, tag in occ.extrude([(2, occ.addPlaneSurface([loop]))], width, 0.0, 0.0) if dim == 3)
        return tab

    at_the_end = lambda L, t, run: ((0.0, 0.0), (L, 0.0), (L, t), (run, t))  # noqa: E731
    overhanging = lambda L, t, run: ((0.0, 0.0), (L - run, 0.0), (L, t), (0.0, t))  # noqa: E731
    model = model_of(strip(thickness=1.5, bevel=15.0))
    g = model.spec.geometry
    for k, profile_of in enumerate((at_the_end, overhanging)):
        monkeypatch.setattr(coupon_shape, "_tab", wrong(profile_of))
        step = tmp_path / f"wrong-{k}.step"
        build_coupon_shape(model.spec, step)
        with pytest.raises(AssertionError):
            check_the_bevels(step, g.length / MM, g.tab_length / MM, thickness_of(model) / 2 / MM, 1.5, 15.0)


@needs_gmsh
def test_the_file_names_every_part_and_states_millimetres(written):
    model, shape, step, solids = written
    text = step.read_text(encoding="ascii")
    assert text.startswith("ISO-10303-21;") and "FILE_SCHEMA(('AUTOMOTIVE_DESIGN" in text  # AP214, as Gmsh's OpenCASCADE writes it
    assert "SI_UNIT(.MILLI.,.METRE.)" in text and ".INCH." not in text
    assert "Open CASCADE STEP translator" not in text and "'Open CASCADE Model'" not in text  # every product and the description are ours
    for part in shape.parts:
        assert text.count(f"PRODUCT('{part.name}',") == 1
    assert [solid["name"] for solid in solids] == [part.name for part in shape.parts]
    if len(shape.parts) > 1:  # several solids are an assembly under the coupon's name
        assert text.count(f"PRODUCT('{shape.title}',") == 1
    assert shape.title == (model.spec.coupon.designation if model.spec.coupon else "Model")


@needs_gmsh
def test_the_part_tables_thickness_is_the_laminates_and_the_layup_is_in_the_table_and_the_header(written):
    model, shape, step, solids = written
    spec = model.spec
    table = part_table(shape, spec.units)
    first = table["parts"][0]
    engine_thickness = sum(ply.thickness_m for ply in spec_plies(spec))  # the laminate as the engine stacks it
    assert table["units"] == {"length": "mm", "volume": "mm³", "step": "mm"} and table["title"] == shape.title
    assert first["thickness"] * MM == pytest.approx(engine_thickness, rel=1e-12)
    assert first["thickness"] == pytest.approx(solids[0]["box"][5] - solids[0]["box"][2], abs=SIZE_MM)  # and the solid's, read back from the file
    assert first["material"] == model.material.name and first["in_model"] is True
    assert first["volume"] == pytest.approx(solids[0]["volume"], rel=1e-12)
    if spec.layup is None:
        assert (first["kind"], first["layup"], first["plies"], first["ply_thickness"]) == ("coupon", "isotropic", None, None)
    else:
        assert first["kind"] == "laminate" and first["plies"] == len(model.section.plies)
        assert first["plies"] * first["ply_thickness"] == pytest.approx(first["thickness"], rel=1e-12)
        assert first["layup"] == "[" + "/".join(f"{a:g}" for a in spec.layup.angles) + "]" + ("s" if spec.layup.symmetric else "")
    json.dumps(table)  # what the API passes on
    # the same lines travel in the file's header, broken between words so that no line of the file is long
    head = step.read_text(encoding="ascii").split("ENDSEC;")[0]
    said = " ".join(piece.strip().strip(",").strip("'") for piece in head.split("FILE_DESCRIPTION((")[1].split("),'2;1');")[0].splitlines() if piece.strip())
    assert said == " ".join(header_lines(shape)).replace("'", "''")
    assert all(len(line) <= 80 for line in head.splitlines())
    assert "in millimetres" in said and "z = 0 at mid-thickness" in said
    if spec.layup is not None:
        assert f"layup {first['layup']}, {first['plies']} plies of" in said and "A STEP file carries no plies" in said
    else:
        assert "one isotropic material" in said and "no plies" not in said


@needs_gmsh
def test_a_table_in_inches_states_the_parts_in_inches_and_the_file_stays_in_millimetres(tmp_path):
    table = strip(thickness=0.062, bevel=90.0)
    table["units"] = "in-psi"
    table["geometry"] = {"length": 10.0, "width": 1.0, "tab_length": 2.25}
    table["mesh"] = {"mesher": "structured", "element_order": 1, "nx": 4, "ny": 40}
    table["layup"]["ply_thickness"] = 0.0072
    table["material"]["transverse"].update(G13=680000.0, G23=433000.0)
    table["loading"]["value"] = 0.04
    table["probes"] = {}
    table["strain"]["gauge_length"] = 1.0
    model = model_of(table)
    step = tmp_path / "inch.step"
    shape = build_coupon_shape(model.spec, step)
    stated = part_table(shape, "in-psi")
    assert stated["units"] == {"length": "in", "volume": "in³", "step": "mm"}
    assert stated["parts"][0]["thickness"] == pytest.approx(8 * 0.0072) and stated["parts"][0]["ply_thickness"] == pytest.approx(0.0072)
    assert stated["parts"][0]["volume"] == pytest.approx(10.0 * 1.0 * 8 * 0.0072) and stated["parts"][1]["thickness"] == pytest.approx(0.062)
    laminate = read_step_solids(step)[0]
    assert laminate["box"] == pytest.approx((0.0, 0.0, -4 * 0.0072 * 25.4, 25.4, 254.0, 4 * 0.0072 * 25.4), abs=SIZE_MM)
    assert "SI_UNIT(.MILLI.,.METRE.)" in step.read_text(encoding="ascii")


# --- what cannot be drawn is refused, and no file is left -----------------------------------------------------------------------


@needs_gmsh
def test_tabs_that_reach_a_dog_bones_fillet_are_refused_and_no_file_is_written(tmp_path):
    table = table_of("d638-type-i-plastic")
    table["tabs"] = {"thickness": 1.5, "bevel": 90.0}
    model = model_of(table)  # its 25 mm grips pass the fillets' start, 32.86 mm from each end: drawn
    assert len(build_coupon_shape(model.spec, tmp_path / "fits.step").parts) == 5
    table["geometry"]["tab_length"] = 40.0  # past it: the tab would lie on the fillet, where nothing states its outline
    table["mesh"] = {"mesher": "structured", "element_order": 1, "nx": 8, "ny": 165}
    model = model_of(table)
    step = tmp_path / "refused.step"
    with pytest.raises(ShapeError, match=r"The tabs cannot be drawn: they are 40 mm long and the dog-bone's full width ends 32\.857\d* mm from each end"):
        build_coupon_shape(model.spec, step)
    assert not step.exists()


@needs_gmsh
def test_a_bevel_too_shallow_for_the_tabs_length_is_refused_and_no_file_is_written(tmp_path):
    model = model_of(strip(thickness=10.0, bevel=7.0))  # 10 / tan 7 degrees = 81.4 mm of bevel on a 56 mm tab
    step = tmp_path / "refused.step"
    with pytest.raises(ShapeError, match=r"a bevel of 7 degrees over a thickness of 10 mm runs 81\.44\d* mm, and the tab is 56 mm long"):
        build_coupon_shape(model.spec, step)
    assert not step.exists()


@needs_gmsh
def test_a_file_that_is_not_named_as_a_step_file_is_refused(tmp_path):
    with pytest.raises(ShapeError, match=r"ends in \.step or \.stp"):
        build_coupon_shape(model_of(strip()).spec, tmp_path / "coupon.inp")
    assert list(tmp_path.iterdir()) == []


def test_a_step_file_with_other_products_or_another_header_is_refused_rather_than_half_named(tmp_path):
    """The names and the description are put into the text OpenCASCADE's writer gives. A release that writes other text makes these
    refuse the file; nothing is renamed by a guess."""
    one = "PRODUCT('Open CASCADE STEP translator 7.8 1',\n  'Open CASCADE STEP translator 7.8 1','',(#8));\n"
    path = tmp_path / "one.step"
    path.write_text(one, encoding="ascii")
    name_step_solids(path, "IM7-UNT-L1", ["Laminate"])
    assert path.read_text(encoding="ascii") == "PRODUCT('Laminate',\n  'Laminate','',(#8));\n"
    for text in (one + one.replace("7.8 1'", "7.8 1.1'"), one.replace("Open CASCADE STEP translator", "Some other writer"), ""):
        path.write_text(text, encoding="ascii")
        with pytest.raises(ShapeError, match="it was not named"):
            name_step_solids(path, "IM7-UNT-L1", ["Laminate"])
        assert path.read_text(encoding="ascii") == text
    with pytest.raises(ShapeError, match="it was not named"):  # two names for a file of one product: the wing's rule, kept
        name_step_solids(path, "IM7-UNT-L1", ["Laminate", "Bottom tab, top face"])
    head = "HEADER;\nFILE_DESCRIPTION(('Open CASCADE Model'),'2;1');\nENDSEC;\n"
    path.write_text(head, encoding="ascii")
    describe_step(path, ["A part's name with an apostrophe and a sentence long enough that it is broken between words into two strings."])
    lines = path.read_text(encoding="ascii").splitlines()
    assert lines[1] == "FILE_DESCRIPTION((" and lines[-1] == "ENDSEC;" and all(len(line) <= 80 for line in lines)
    assert HEADER_WIDTH < 72
    assert lines[2].startswith("  'A part''s name with an apostrophe") and lines[3].endswith("'),'2;1');")
    path.write_text(head.replace("Open CASCADE Model", "Another writer's words"), encoding="ascii")
    with pytest.raises(ShapeError, match="it was not described"):
        describe_step(path, ["anything"])


# --- through the tool the API runs (fea/tools/studio_tool.py model --program step) ---------------------------------------------


def values_file(folder: Path, **changes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, **PUBLIC_FILL, **changes}), encoding="utf-8")
    return path


def run_tool(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(STUDIO), *args], capture_output=True, text=True, encoding="utf-8", env=env)


@needs_gmsh
def test_the_tool_writes_the_step_file_named_after_the_coupon_with_its_part_table_and_solves_nothing(tmp_path):
    import hashlib

    out = tmp_path / "model"
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path)), "--program", "step", "--out", str(out))
    assert done.returncode == 0, done.stderr
    name = f"{DESIGNATION}.step"
    assert sorted(p.name for p in out.iterdir()) == sorted(["checklist.json", "model.json", name])  # no fields, no summary: nothing was solved
    head = json.loads((out / "model.json").read_text(encoding="utf-8"))
    data = (out / name).read_bytes()
    assert head["state"] == "written" and head["program"] == "step" and head["name"] == name and head["units"] == "mm" and head["solids"] == 1
    assert head["bytes"] == len(data) and head["sha256"] == hashlib.sha256(data).hexdigest() and done.stdout.startswith(f"written: {name}, ")
    (part,) = head["parts"]["parts"]
    assert head["parts"]["title"] == DESIGNATION and part["name"] == "Laminate" and part["layup"] == "[45/0/-45/90]s" and part["plies"] == 8
    assert part["material"] == "IM7-8552-Lamina"  # the material's name in this coupon's own model, as its other files name it
    (solid,) = read_step_solids(out / name)
    assert solid["name"] == "Laminate" and solid["box"] == pytest.approx((0.0, 0.0, -part["thickness"] / 2, 25.0, 250.0, part["thickness"] / 2), abs=SIZE_MM)


@needs_gmsh
def test_the_tool_draws_bonded_tabs_when_the_rows_state_them_and_refuses_ones_it_cannot_draw(tmp_path):
    out = tmp_path / "tabs"
    tabs = {"tab_thickness": 1.5, "tab_bevel": 7.0, "tab_material": "E-glass/epoxy"}
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path / "a", **tabs)), "--program", "step", "--out", str(out))
    assert done.returncode == 0 and done.stdout.startswith("written: "), done.stdout + done.stderr
    head = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert head["solids"] == 5 and [p["name"] for p in head["parts"]["parts"]][1] == "Bottom tab, top face"
    assert [p["in_model"] for p in head["parts"]["parts"]] == [True, False, False, False, False]
    refused = tmp_path / "refused"
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path / "b", **{**tabs, "tab_thickness": 10.0})), "--program", "step",
                    "--out", str(refused))
    assert done.returncode == 0 and done.stdout.startswith("refused: The tabs cannot be drawn"), done.stdout + done.stderr
    head = json.loads((refused / "model.json").read_text(encoding="utf-8"))
    assert head["state"] == "refused" and head["problem"].startswith("The tabs cannot be drawn: a bevel of 7 degrees")
    assert sorted(p.name for p in refused.iterdir()) == ["checklist.json", "model.json"]  # no STEP file


def test_the_tool_says_gmsh_is_not_installed_and_writes_no_file(tmp_path):
    """Without the optional extra the shape cannot be built: the state is `unavailable`, with how to install it, and no file."""
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "gmsh.py").write_text("raise ImportError('hidden for this test')\n", encoding="utf-8")
    import os

    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(hidden), *([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])])}
    out = tmp_path / "model"
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path)), "--program", "step", "--out", str(out), env=env)
    assert done.returncode == 0 and done.stdout.startswith("unavailable: Gmsh is not available"), done.stdout + done.stderr
    head = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert head == {"state": "unavailable", "program": "step", "problem": head["problem"]} and "uv sync --extra mesh" in head["problem"]
    assert sorted(p.name for p in out.iterdir()) == ["checklist.json", "model.json"]


@needs_gmsh
def test_a_plate_with_a_hole_set_up_as_the_workspace_writes_it_gets_its_step_file(tmp_path):
    """The rows the workspace sends for a plate (the browser tests' plate) with a hole's diameter added, and no tab length, which the
    form does not show for a plate. The setup check stopped on this until the hole's refusal was built only where it applies."""
    rows = json.loads((paths.ROOT / "tests" / "fixtures" / "studio-plate" / "values.json").read_text(encoding="utf-8"))
    assert rows["test"] == "plate" and "tab_length" not in rows and "hole_diameter" not in rows
    source = tmp_path / "values.json"
    source.write_text(json.dumps({**rows, "hole_diameter": 20.0}), encoding="utf-8")
    out = tmp_path / "model"
    done = run_tool("--root", str(tmp_path / "root"), "--every-test", "model", str(source), "--program", "step", "--out", str(out))
    assert done.returncode == 0, done.stderr
    assert json.loads((out / "checklist.json").read_text(encoding="utf-8"))["state"] != "blocked", done.stdout
    head = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert head["state"] == "written" and head["solids"] == 1, head
    (solid,) = read_step_solids(out / head["name"])
    (hole,) = solid["holes"]
    assert solid["box"][:2] == pytest.approx((0.0, 0.0), abs=SIZE_MM) and solid["box"][3:5] == pytest.approx((100.0, 100.0), abs=SIZE_MM)
    assert (hole["x"], hole["y"], hole["diameter"]) == pytest.approx((50.0, 50.0, 20.0), abs=SIZE_MM)


def test_a_blocked_setup_gets_no_step_file_as_it_gets_no_other(tmp_path):
    out = tmp_path / "model"
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path, length=None)), "--program", "step", "--out", str(out))
    assert done.returncode == 0 and done.stdout.startswith("blocked: no model written"), done.stdout + done.stderr
    assert [p.name for p in out.iterdir()] == ["checklist.json"]


@needs_gmsh
def test_a_warm_worker_answers_a_step_request_with_one_line_and_goes_on(tmp_path):
    """OpenCASCADE's STEP writer prints to the process's standard output, which is the worker's answers: nothing of it may reach them."""
    worker = subprocess.Popen([sys.executable, str(STUDIO), "--root", str(tmp_path / "root"), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    try:
        assert json.loads(worker.stdout.readline())["ready"] is True
        values = values_file(tmp_path)
        answers = []
        for request in ({"values": str(values), "out": str(tmp_path / "a"), "model": "step"}, {"values": str(values), "out": str(tmp_path / "b"), "model": "abaqus"},
                        {"values": str(values), "out": str(tmp_path / "c"), "model": "step"}):
            worker.stdin.write(json.dumps(request) + "\n")
            worker.stdin.flush()
            answers.append(json.loads(worker.stdout.readline()))
        assert answers == [{"state": "written"}] * 3
        assert (tmp_path / "a" / f"{DESIGNATION}.step").is_file() and (tmp_path / "b" / f"{DESIGNATION}-abaqus.inp").is_file()
        first, again = ((tmp_path / folder / f"{DESIGNATION}.step").read_text(encoding="ascii") for folder in ("a", "c"))
        assert first.count("PRODUCT('Laminate',") == again.count("PRODUCT('Laminate',") == 1  # the second file of one process is named too
        worker.stdin.close()
        assert worker.wait(timeout=30) == 0
    finally:
        worker.kill()


# --- no mesh for a shape, sizes the kernel cannot hold, and the header's lines (ADR-0146, review) ----------------------------------


def studio_tool():
    import importlib.util

    made = importlib.util.spec_from_file_location("studio_tool_for_shapes", STUDIO)
    module = importlib.util.module_from_spec(made)
    made.loader.exec_module(module)
    return module


def without_the_time(step: Path) -> str:
    """A STEP file's text less the one thing that differs between two writings of one shape: the time in its FILE_NAME."""
    text, count = re.subn(r"(FILE_NAME\('[^']*',')[0-9T:-]+(')", r"\1\2", step.read_text(encoding="ascii"))
    assert count == 1
    return text


@needs_gmsh
@pytest.mark.parametrize("fill", ["PUBLIC_FILL", "OHT_FILL"])
def test_a_step_file_cuts_no_mesh_so_a_very_fine_element_size_answers_as_fast_as_a_coarse_one_with_the_same_file(tmp_path, monkeypatch, fill):
    """The shape has no mesh. The request for it once built the whole mesh first, with no limit on its elements: 29 s for a 16 kB box
    at 0.15 mm, and past 150 s and 800 MB at 0.05 mm. Here the meshers are stood in by a spy that fails the test if anything calls it,
    and the fine size is among the finest a setup may state (ADR-0086 amendment 2: 100,000 elements, whatever is made of them)."""
    import time

    import test_intake
    from anisotropy_fea import checks, enabled, femodel, mesher

    called: list[str] = []

    def spy(name):
        def refuse(*args, **kwargs):
            called.append(name)
            raise AssertionError(f"{name} was called for a shape")
        return refuse

    for module, name in ((femodel, "mesh_for_spec"), (femodel, "build_model"), (checks, "build_model"), (mesher, "structured_rectangle"),
                         (mesher, "gmsh_open_hole_plate")):
        monkeypatch.setattr(module, name, spy(name))
    tool = studio_tool()
    rows = {k: v for k, v in getattr(test_intake, fill).items() if not k.startswith("mesh_")}
    fine = size_that_fits(rows["length"], rows["width"], MOST_ELEMENTS_STATED)
    assert fine < 0.35  # 0.25 mm on the strip, 100,000 elements; 0.33 mm on the coupon with a hole, 72,452
    files, seconds = {}, {}
    with enabled.every_test(True):
        for size in (5.0, fine):
            folder = tmp_path / str(size)
            folder.mkdir()
            source = folder / "values.json"
            source.write_text(json.dumps({"form_version": FORM_VERSION, **rows, "element_size": size}), encoding="utf-8")
            clock = time.perf_counter()
            state = tool.model_file(source, "step", folder / "out", tmp_path / "root")
            seconds[size] = time.perf_counter() - clock
            head = json.loads((folder / "out" / "model.json").read_text(encoding="utf-8")) if state != "blocked" else {}
            assert state == "written", json.loads((folder / "out" / "checklist.json").read_text(encoding="utf-8"))["problems"]
            files[size] = without_the_time(folder / "out" / head["name"])
    assert called == []
    assert files[fine] == files[5.0]
    assert seconds[fine] < 5.0, seconds


def test_the_shapes_checklist_judges_the_rows_the_spec_and_the_material_and_leaves_what_a_mesh_decides_pending(tmp_path):
    from anisotropy_fea.checks import setup_checklist, shape_checklist
    from anisotropy_fea.intake import read_values

    def form(**changes):
        folder = tmp_path / str(len(list(tmp_path.iterdir())))
        return read_values(values_file(folder, **changes))

    whole, model, _ = setup_checklist(form(), tmp_path / "root", element_limit=None)
    shape, spec = shape_checklist(form(), tmp_path / "root")
    assert spec is not None and spec == model.spec and shape.designation == whole.designation == DESIGNATION
    states = {item.id: item.state for item in shape.items}
    # every item the check words from the built model is left pending for a shape, which builds none: these ten, and no other
    worded_from_the_model = {"identity", "units", "geometry", "material", "laminate", "constraints", "load", "mesh", "criterion", "probes"}
    assert {item for item, state in states.items() if state == "pending"} == worded_from_the_model
    assert {item.id for item in whole.items if item.state == "pending"} == set()  # with its model built, the same setup leaves none
    assert {item: states[item] for item in states if item not in worded_from_the_model} == {
        item.id: item.state for item in whole.items if item.id not in worded_from_the_model}  # the rest is judged alike: the standard, the solver, the document
    assert states["standard"] == {item.id: item.state for item in whole.items}["standard"]
    # what the rows, the spec or the material refuse stops a shape as it stops the other files, in the same words
    for changes in ({"length": None}, {"tab_length": 200.0}, {"library": None}):
        whole, model, _ = setup_checklist(form(**changes), tmp_path / "root", element_limit=None)
        shape, spec = shape_checklist(form(**changes), tmp_path / "root")
        assert model is None and spec is None, changes
        stops = lambda checklist: [(item.id, item.state, item.message) for item in checklist.items if item.state in ("fail", "missing")]  # noqa: E731
        assert stops(shape) == stops(whole) and stops(shape), changes


@needs_gmsh
@pytest.mark.parametrize("tabs, words", [
    ({"thickness": 1e-9, "bevel": 90.0}, "The shape cannot be drawn: the tabs' thickness is 1e-09 mm, under the 0.001 mm that is the smallest size drawn"),
    # a face is left, too short to draw: its own length is said. "runs 56 mm, and the tab is 56 mm long" was said before, which is no reason
    ({"thickness": 56.0 - 1e-6, "bevel": 45.0}, "The tabs cannot be drawn: a bevel of 45 degrees over a thickness of 56 mm leaves the tab's outer face "
                                                "1e-06 mm long, under the 0.001 mm that is the smallest size drawn"),
    ({"thickness": 56.0 - 1e-7, "bevel": 45.0}, "leaves the tab's outer face 1e-07 mm long, under the 0.001 mm that is the smallest size drawn"),
    ({"thickness": 56.0 - 5e-4, "bevel": 45.0}, "leaves the tab's outer face 0.0005 mm long, under the 0.001 mm that is the smallest size drawn"),
    # no face is left, and the run and the tab's length print alike: said in words
    ({"thickness": 56.0, "bevel": 45.0}, "over a thickness of 56 mm runs the tab's whole length, 56 mm, so it has no outer face left"),
    ({"thickness": 56.0 + 1e-6, "bevel": 45.0}, "over a thickness of 56 mm runs the tab's whole length, 56 mm, so it has no outer face left"),
    ({"thickness": 60.0, "bevel": 45.0}, "over a thickness of 60 mm runs 60 mm, and the tab is 56 mm long, so it has no outer face left"),
])
def test_a_tab_the_kernel_cannot_hold_is_refused_with_its_reason_before_the_kernel_is_asked(tmp_path, monkeypatch, tabs, words):
    from anisotropy_fea import coupon_shape

    model = model_of(strip(**tabs))
    monkeypatch.setattr(coupon_shape, "_gmsh", lambda: pytest.fail("the kernel was asked"))
    step = tmp_path / "coupon.step"
    with pytest.raises(ShapeError) as refused:
        build_coupon_shape(model.spec, step)
    assert words in str(refused.value) and str(refused.value).startswith(("The shape cannot be drawn", "The tabs cannot be drawn"))
    assert not re.search(r"runs (\S+ mm), and the tab is \1 long", str(refused.value))  # never two numbers that print alike as the reason
    assert not step.exists()


@needs_gmsh
def test_a_tab_a_micrometre_thick_with_an_outer_face_a_micrometre_long_is_still_drawn(tmp_path):
    """The smallest sizes that are drawn, so the refusals above stop no shape the kernel holds."""
    step = tmp_path / "coupon.step"
    shape = build_coupon_shape(model_of(strip(thickness=1e-3, bevel=90.0)).spec, step)
    assert len(shape.parts) == 5 and len(read_step_solids(step)) == 5
    assert len(build_coupon_shape(model_of(strip(thickness=56.0 - 2e-3, bevel=45.0)).spec, tmp_path / "long-bevel.step").parts) == 5


@needs_gmsh
def test_what_the_kernel_cannot_build_is_a_plain_refusal_that_carries_none_of_its_words(tmp_path, monkeypatch):
    from anisotropy_fea import coupon_shape

    def fails(*args, **kwargs):
        raise Exception("Could not create line in /tmp/model-abc123/out/kernel.brep at BRepBuilderAPI_MakeEdge")

    step = tmp_path / "coupon.step"
    for name in ("_laminate", "_tab"):
        with monkeypatch.context() as patched:
            patched.setattr(coupon_shape, name, fails)
            with pytest.raises(ShapeError) as refused:
                build_coupon_shape(model_of(strip(thickness=1.5, bevel=7.0)).spec, step)
        assert str(refused.value) == "The shape cannot be drawn from these sizes: the geometry kernel could not build it"
        assert isinstance(refused.value.__cause__, Exception) and "BRepBuilderAPI" in str(refused.value.__cause__)  # the cause, for the log alone
        assert not step.exists()
    assert len(build_coupon_shape(model_of(strip(thickness=1.5, bevel=7.0)).spec, step).parts) == 5  # the kernel is left fit for the next shape


@needs_gmsh
def test_a_refusal_states_its_sizes_in_the_coupons_own_units(tmp_path):
    table = strip(thickness=0.4, bevel=7.0)  # inches: a bevel of 7 degrees over 0.4 in runs 3.26 in, past a 2.2 in tab
    table["units"] = "in-psi"
    table["geometry"].update(length=10.0, width=1.0, tab_length=2.2)
    table["layup"]["ply_thickness"] = 0.0072
    table["mesh"] = {"mesher": "structured", "element_order": 1, "nx": 4, "ny": 50}
    table["probes"] = {}
    table["strain"]["gauge_length"] = 2.0
    model = model_of(table)
    with pytest.raises(ShapeError) as refused:
        build_coupon_shape(model.spec, tmp_path / "coupon.step")
    said = str(refused.value)
    assert "a thickness of 0.4 in runs 3.25774 in, and the tab is 2.2 in long" in said and " mm" not in said


def test_the_headers_description_is_strings_of_at_most_its_width_as_written_broken_between_words_then_after_a_slash_then_anywhere():
    from anisotropy_fea.coupon_shape import header_strings
    from anisotropy_fea.wing_shape import _step_string

    layup = "[" + "/".join(f"{angle}.25" for angle in (12, -12, 33, -33, 47, -47, 61, -61, 75, -75, 88, -88, 5, -5, 19, -19)) + "]s"
    cases = [f"Laminate: layup {layup}, 32 plies of 0.18288 mm, 5.85216 mm thick, IM7-8552.",  # sixteen angles with fractions: one long word
             "Top tab, top face: bonded tab, 1.5 mm thick, " + "G" * 300 + ". Drawn as stated.",  # a word longer than four strings
             "Bob's tab of E-glass \u00b145\u00b0 on a\\b, 1.5 mm thick, " + "\u03b1" * 40 + "."]  # every character that is written longer than itself
    for line in cases:
        pieces = header_strings(line)
        assert all(0 < len(_step_string(piece)) <= HEADER_WIDTH for piece in pieces), line
        assert "".join(pieces).replace(" ", "") == line.replace(" ", ""), line  # nothing lost, nothing added, in order
        assert all(not piece.startswith(" ") and not piece.endswith(" ") for piece in pieces)
    short = "IM7-UNT-L1: shape only, in millimetres. x across the width, y along the length, z through the thickness, z = 0 at mid-thickness."
    assert " ".join(header_strings(short)) == short  # an ordinary sentence breaks between words alone
    assert header_strings("Bottom tab, top face: bonded tab, 1.5 mm thick, E-glass/epoxy. Drawn.") == ["Bottom tab, top face: bonded tab, 1.5 mm thick, E-glass/epoxy.", "Drawn."]
    assert HEADER_WIDTH + len("  '") + len("'),'2;1');") < 80


@needs_gmsh
def test_no_line_of_the_files_description_is_longer_than_80_characters_and_every_string_reads_back(tmp_path):
    table = strip(thickness=1.5, bevel=7.0, material="E-glass \u00b145\u00b0, Bob's own, lot a\\b " + "G" * 120)
    table["layup"]["angles"] = [12.25, -12.25, 33.25, -33.25, 47.25, -47.25, 61.25, -61.25, 75.25, -75.25, 88.25, -88.25, 5.25, -5.25, 19.25, -19.25]
    model = model_of(table)
    step = tmp_path / "coupon.step"
    shape = build_coupon_shape(model.spec, step)
    text = step.read_text(encoding="ascii")
    described = text.split("FILE_DESCRIPTION((")[1].split("),'2;1');")[0]
    lines = ("FILE_DESCRIPTION((" + described + "),'2;1');").splitlines()
    assert max(len(line) for line in lines) < 80 and len(lines) > 12
    strings = [part21_text(line.strip().removesuffix(",")[1:-1]) for line in described.splitlines() if line.strip()]
    assert "".join(strings).replace(" ", "") == "".join(header_lines(shape)).replace(" ", "")
    assert "E-glass \u00b145\u00b0, Bob's own, lot a\\b" in " ".join(strings)
    assert len(read_step_solids(step)) == 5  # and the file still opens


@needs_gmsh
@pytest.mark.parametrize("changes, state, words", [
    ({"tab_thickness": 1e-9, "tab_bevel": 90.0}, "refused", "the tabs' thickness is 1e-09 mm, under the 0.001 mm that is the smallest size drawn"),
    ({"tab_thickness": 56.0 - 1e-7, "tab_bevel": 45.0}, "refused", "leaves the tab's outer face 1e-07 mm long, under the 0.001 mm that is the smallest size drawn"),
    ({"tab_thickness": 56.0 + 1e-6, "tab_bevel": 45.0}, "refused", "runs the tab's whole length, 56 mm, so it has no outer face left"),
])
def test_the_tool_refuses_a_tab_the_kernel_cannot_hold_and_does_not_stop(tmp_path, changes, state, words):
    out = tmp_path / "model"
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path, **changes)), "--program", "step", "--out", str(out))
    assert done.returncode == 0, done.stderr[-600:]
    head = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert head["state"] == state and words in head["problem"] and "Traceback" not in done.stdout + done.stderr
    assert not list(out.glob("*.step"))


# --- every size a shape is drawn from, by the table (ADR-0146, the review's second round) -----------------------------------------


def spec_of(table: dict):
    return to_si(spec_from_table(copy.deepcopy(table), "0" * 64))


def resized(spec, tabs: dict | None = None, dogbone: dict | None = None, **geometry):
    """The spec with sizes changed past its own rules, as a caller that built one by hand could: the shape's refusals are its last word."""
    g = spec.geometry
    if dogbone:
        g = g.model_copy(update={"dogbone": g.dogbone.model_copy(update=dogbone)})
    made = spec.model_copy(update={"geometry": g.model_copy(update=geometry)})
    return made.model_copy(update={"tabs": made.tabs.model_copy(update=tabs)}) if tabs else made


TINY = 1e-6 * MM  # a nanometre, in metres: the 1e-6 mm of the review, a thousandth of the smallest size drawn
TABBED_STRIP = lambda: strip(thickness=1.5, bevel=30.0)  # noqa: E731
TYPE_I = lambda: table_of("d638-type-i-plastic")  # noqa: E731
OPEN_HOLE = lambda: table_of("open-hole-im7-8552")  # noqa: E731


def short_dogbone(spec):
    """The dog-bone with its length cut until its full width at each end is a nanometre long."""
    return resized(spec, length=2 * (outline_of(spec).s_full + TINY))


# For each row of the table: a coupon that has the size, and the same coupon with that size a nanometre long
TOO_SMALL = {
    "geometry.length": (strip, lambda spec: resized(spec, length=TINY)),
    "geometry.width": (strip, lambda spec: resized(spec, width=TINY)),
    "geometry.thickness": (TYPE_I, lambda spec: resized(spec, thickness=TINY)),
    "geometry.hole_diameter": (OPEN_HOLE, lambda spec: resized(spec, hole_diameter=TINY)),
    "beside the hole": (OPEN_HOLE, lambda spec: resized(spec, hole_diameter=spec.geometry.width - 2 * TINY)),
    "hole to end": (plate_with_a_hole, lambda spec: resized(spec, length=spec.geometry.hole_diameter + 2 * TINY)),
    "tabs.thickness": (TABBED_STRIP, lambda spec: resized(spec, tabs={"thickness": TINY})),
    "geometry.tab_length": (TABBED_STRIP, lambda spec: resized(spec, tab_length=TINY)),
    "between the tabs": (TABBED_STRIP, lambda spec: resized(spec, tab_length=spec.geometry.length / 2 - TINY / 2)),
    "geometry.dogbone.narrow_width": (TYPE_I, lambda spec: resized(spec, dogbone={"narrow_width": TINY})),
    "geometry.dogbone.narrow_length": (TYPE_I, lambda spec: resized(spec, dogbone={"narrow_length": TINY})),
    "geometry.dogbone.radius": (TYPE_I, lambda spec: resized(spec, dogbone={"radius": TINY})),
    "geometry.dogbone.outer_radius": (dogbone_type_iv, lambda spec: resized(spec, dogbone={"outer_radius": TINY})),
    "dog-bone step": (TYPE_I, lambda spec: resized(spec, dogbone={"narrow_width": spec.geometry.width - 2 * TINY})),
    "dog-bone end": (TYPE_I, short_dogbone),
}


def test_every_row_of_the_table_of_drawn_sizes_is_tried_here_and_every_size_of_the_spec_is_in_the_table_or_named_as_not_drawn():
    assert list(TOO_SMALL) == [size.key for size in DRAWN_SIZES] and len({size.words for size in DRAWN_SIZES}) == len(DRAWN_SIZES)
    stated = ({f"geometry.{name}" for name in Geometry.model_fields} | {f"geometry.dogbone.{name}" for name in Dogbone.model_fields}
              | {f"tabs.{name}" for name in Tabs.model_fields})
    drawn = {size.key for size in DRAWN_SIZES}
    assert stated <= drawn | set(NOT_DRAWN), sorted(stated - drawn - set(NOT_DRAWN))  # a key added to the spec is judged before it is drawn
    assert not drawn & set(NOT_DRAWN) and set(NOT_DRAWN) <= stated and all(NOT_DRAWN.values())


@pytest.mark.parametrize("key", list(TOO_SMALL))
def test_a_size_a_nanometre_long_is_refused_by_its_own_name_before_the_kernel_is_asked(tmp_path, monkeypatch, key):
    """A dog-bone's narrow width of 1e-6 mm was drawn before: the refusal held a list of seven sizes, and a dog-bone's were not on it."""
    from anisotropy_fea import coupon_shape

    size = next(size for size in DRAWN_SIZES if size.key == key)
    make, shrink = TOO_SMALL[key]
    spec = spec_of(make())
    thickness = sum(ply.thickness_m for ply in coupon_shape.laminate_section(spec)[1].plies)
    assert size.read(spec, thickness) >= SMALLEST_MM * MM  # the coupon has the size, and as it stands it is drawn
    small = shrink(spec)
    monkeypatch.setattr(coupon_shape, "_gmsh", lambda: pytest.fail("the kernel was asked"))
    step = tmp_path / "coupon.step"
    with pytest.raises(ShapeError) as refused:
        build_coupon_shape(small, step)
    assert re.fullmatch(rf"The shape cannot be drawn: {re.escape(size.words)} is \S+ mm, under the 0\.001 mm that is the smallest size drawn",
                        str(refused.value)), str(refused.value)
    value = float(str(refused.value).split(" is ")[1].split(" mm")[0])
    assert 0.9e-6 <= value <= 1.1e-6 and not step.exists()


@pytest.mark.parametrize("key", [size.key for size in DRAWN_SIZES if "." in size.key])
def test_a_stated_size_that_is_no_finite_number_is_refused_by_its_own_name(tmp_path, key):
    size = next(size for size in DRAWN_SIZES if size.key == key)
    make, _ = TOO_SMALL[key]
    spec = spec_of(make())
    table, _, name = key.rpartition(".")
    broken = (resized(spec, tabs={name: math.inf}) if table == "tabs" else resized(spec, dogbone={name: math.inf}) if table == "geometry.dogbone"
              else resized(spec, **{name: math.inf}))
    with pytest.raises(ShapeError) as refused:
        build_coupon_shape(broken, tmp_path / "coupon.step")
    assert str(refused.value) == f"The shape cannot be drawn: {size.words} is not a finite size"


def test_each_kind_is_judged_on_the_sizes_it_has_and_no_other():
    from anisotropy_fea.coupon_shape import laminate_section

    base = {"geometry.length", "geometry.width", "geometry.thickness"}
    tabs = {"tabs.thickness", "geometry.tab_length", "between the tabs"}
    hole = {"geometry.hole_diameter", "beside the hole", "hole to end"}
    dogbone = {"geometry.dogbone.narrow_width", "geometry.dogbone.narrow_length", "geometry.dogbone.radius", "dog-bone step", "dog-bone end"}
    expected = {
        "unnotched tension, gripped strip": base,
        "unnotched tension, bonded tabs with a 7 degree bevel": base | tabs,
        "unnotched tension, bonded tabs with a square end": base | tabs,
        "unnotched tension, dog-bone": base | dogbone,
        "unnotched tension, dog-bone with an outer radius": base | dogbone | {"geometry.dogbone.outer_radius"},
        "open-hole tension": base | hole,
        "compression": base,
        "in-plane shear": base,
        "three-point bending": base,
        "four-point bending": base,
        "plate": base,
        "plate with a hole": base | hole,
    }
    assert set(expected) == set(KINDS)
    for name, make in KINDS.items():
        spec = spec_of(make())
        thickness = sum(ply.thickness_m for ply in laminate_section(spec)[1].plies)
        read = {size.key: size.read(spec, thickness) for size in DRAWN_SIZES}
        assert {key for key, value in read.items() if value is not None} == expected[name], name
        assert all(value >= SMALLEST_MM * MM for value in read.values() if value is not None), name
