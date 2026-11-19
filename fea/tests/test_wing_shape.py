"""The wing's shape, STEP file and shell mesh (ADR-0116): mid-surfaces, part names and areas through a STEP round trip,
conforming parts, element normals, and the refusals.

Every test that builds the shape skips with a reason when Gmsh is not installed (`uv sync --extra mesh`).
"""

import math
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.wing import wing_from_dict
from anisotropy_fea.mesher import gmsh_available
from anisotropy_fea.wing_shape import (
    ShapeError, build_wing_shape, layup_thickness, main, mid_surface_section, name_step_products, rib_stations,
)

EXAMPLE = Path(__file__).parents[2] / "engine" / "examples" / "example-wing.toml"
needs_gmsh = pytest.mark.skipif(gmsh_available() is None,
                                reason="Gmsh is not available: from fea/ run `uv sync --extra mesh` (on Linux also apt install libglu1-mesa)")


def example(**changes):
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    for path, value in changes.items():
        *tables, key = path.split(".")
        table = data
        for name in tables:
            table = table[name]
        if value is None:
            table.pop(key)
        else:
            table[key] = value
    return wing_from_dict(data)[0]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if gmsh_available() is None:
        pytest.skip("Gmsh is not available")
    step = tmp_path_factory.mktemp("wing") / "wing.step"
    wing = example()
    return wing, build_wing_shape(wing, step, element_size_m=0.02), step


def outline(wing, x):
    return np.array([wing.geometry.airfoil.surface_heights(float(v)) for v in x]) * wing.geometry.chord_m


def test_the_skins_mid_surface_lies_half_the_skins_thickness_inside_the_airfoil():
    wing = example()
    section = mid_surface_section(wing)
    half = layup_thickness(wing.skin) / 2
    c = wing.geometry.chord_m
    x = np.linspace(0.0, 1.0, 2001)
    oml = outline(wing, x)
    for curve, side in ((section.upper, 0), (section.lower, 1)):
        points = np.c_[x * c, oml[:, side]]
        for p in curve[1:-1]:
            distance = np.min(np.linalg.norm(points - p, axis=1))
            assert distance == pytest.approx(half, rel=0.02)
    assert section.upper[0] == pytest.approx(section.lower[0])
    assert section.upper[0, 0] == pytest.approx(half, rel=1e-3)  # the nose moves aft by half the thickness


def test_the_mid_surfaces_meet_aft_where_the_airfoil_is_as_thin_as_the_skin():
    wing = example()
    section = mid_surface_section(wing)
    assert section.trailing_edge_closed
    x_meet = section.upper[-1, 0] / wing.geometry.chord_m
    upper, lower = wing.geometry.airfoil.surface_heights(x_meet)
    thickness_there = (upper - lower) * wing.geometry.chord_m
    assert thickness_there == pytest.approx(layup_thickness(wing.skin), rel=0.05)  # the normals lean, so not exactly


def test_the_spar_webs_run_between_the_mid_surfaces_at_their_chord_positions():
    wing = example()
    section = mid_surface_section(wing)
    assert section.spar_x_m == pytest.approx((0.25 * 0.45, 0.65 * 0.45))
    for x, top, bottom in zip(section.spar_x_m, section.spar_top_m, section.spar_bottom_m):
        assert [x, top] in section.upper.tolist() and [x, bottom] in section.lower.tolist()
        upper, lower = wing.geometry.airfoil.surface_heights(x / 0.45)
        assert bottom * 1.0 > lower * 0.45 and top < upper * 0.45


def test_ribs_stand_at_the_root_every_spacing_and_the_tip():
    assert rib_stations(example()) == pytest.approx((0.0, 0.5, 1.0, 1.5, 2.0))
    assert rib_stations(example(**{"geometry.rib_spacing": 0.6})) == pytest.approx((0.0, 0.6, 1.2, 1.8, 2.0))
    assert rib_stations(example(**{"geometry.rib_spacing": None, "rib": None})) == ()


def test_a_skin_thicker_than_the_airfoil_or_a_spar_aft_of_the_skins_meeting_is_refused():
    with pytest.raises(ShapeError, match="thicker than the airfoil"):
        mid_surface_section(example(**{"skin.core_thickness": 60.0}))
    with pytest.raises(ShapeError, match="aft of where the skins"):
        mid_surface_section(example(**{"geometry.rear_spar": 0.97}))


@needs_gmsh
def test_the_parts_are_named_and_sized_as_the_description_says(built):
    wing, shape, _ = built
    assert [p.name for p in shape.parts] == ["Upper skin", "Lower skin", "Front spar", "Rear spar", "Rib 1", "Rib 2", "Rib 3", "Rib 4", "Rib 5"]
    parts = {p.name: p for p in shape.parts}
    section, span = shape.section, wing.geometry.half_span_m
    for name, k in (("Front spar", 0), ("Rear spar", 1)):
        height = section.spar_top_m[k] - section.spar_bottom_m[k]
        assert parts[name].area_m2 == pytest.approx(height * span, rel=1e-9)
        assert parts[name].thickness_m == pytest.approx(wing.spar.fiber_thickness_m)
    for name, curve in (("Upper skin", section.upper), ("Lower skin", section.lower)):
        polyline = np.sum(np.linalg.norm(np.diff(curve, axis=0), axis=1))
        assert parts[name].area_m2 == pytest.approx(polyline * span, rel=2e-3)  # the spline is a little longer than its chords
    closed = np.vstack([section.upper, section.lower[::-1][1:]])
    shoelace = 0.5 * abs(np.dot(closed[:, 0], np.roll(closed[:, 1], -1)) - np.dot(closed[:, 1], np.roll(closed[:, 0], -1)))
    assert parts["Rib 1"].area_m2 == pytest.approx(shoelace, rel=2e-3)
    assert parts["Upper skin"].mass_kg == pytest.approx(
        parts["Upper skin"].area_m2 * (wing.skin.fiber_thickness_m * wing.skin.material.density_kg_m3 + 0.006 * 48.0))
    assert shape.mass_kg == pytest.approx(sum(p.mass_kg for p in shape.parts))


@needs_gmsh
def test_the_step_file_is_in_millimetres_and_reads_back_with_its_names_and_areas(built):
    import gmsh

    wing, shape, step = built
    text = step.read_text(encoding="ascii")
    assert "SI_UNIT(.MILLI.,.METRE.)" in text
    assert "PRODUCT('Example straight wing'" in text and "Open CASCADE STEP translator" not in text
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        entities = gmsh.model.occ.importShapes(str(step))
        gmsh.model.occ.synchronize()
        read = {gmsh.model.getEntityName(d, t).rsplit("/", 1)[-1]: gmsh.model.occ.getMass(d, t) * 1e-6 for d, t in entities}
        box = gmsh.model.getBoundingBox(-1, -1)
    finally:
        gmsh.finalize()
    assert read == pytest.approx({p.name: p.area_m2 for p in shape.parts}, rel=1e-9)
    assert box[4] - box[1] == pytest.approx(wing.geometry.half_span_m * 1e3, rel=1e-9)  # the span in millimetres


@needs_gmsh
def test_the_mesh_has_every_part_and_the_parts_share_their_nodes_where_they_meet(built):
    wing, shape, _ = built
    mesh = shape.mesh
    assert set(mesh.element_sets) == {p.name for p in shape.parts}
    assert sorted(np.concatenate(list(mesh.element_sets.values())).tolist()) == list(range(mesh.element_count))
    assert np.unique(mesh.elements).size == mesh.nodes.shape[0]  # every node is used
    nodes_of = {name: set(np.unique(mesh.elements[e]).tolist()) for name, e in mesh.element_sets.items()}
    # The front web's top edge is a line of nodes of the upper skin, and its bottom edge of the lower skin's.
    shared_top = nodes_of["Front spar"] & nodes_of["Upper skin"]
    shared_bottom = nodes_of["Front spar"] & nodes_of["Lower skin"]
    span = wing.geometry.half_span_m
    for shared, z in ((shared_top, shape.section.spar_top_m[0]), (shared_bottom, shape.section.spar_bottom_m[0])):
        points = mesh.nodes[sorted(shared)]
        assert np.allclose(points[:, 0], shape.section.spar_x_m[0], atol=1e-9) and np.allclose(points[:, 2], z, atol=1e-6)
        assert points[:, 1].min() == pytest.approx(0.0, abs=1e-12) and points[:, 1].max() == pytest.approx(span)
    assert nodes_of["Rib 3"] & nodes_of["Upper skin"] and nodes_of["Rib 3"] & nodes_of["Rear spar"]
    root = mesh.nodes[mesh.node_sets["root"]]
    assert np.allclose(root[:, 1], 0.0) and len(root) > 20


@needs_gmsh
def test_element_normals_point_out_of_the_wing_aft_and_to_the_root(built):
    _, shape, _ = built
    mesh = shape.mesh
    p = mesh.nodes[mesh.elements]
    normal = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    centre = p.mean(axis=1)
    box = (centre[:, 0] > shape.section.spar_x_m[0]) & (centre[:, 0] < shape.section.spar_x_m[1])
    upper, lower = mesh.element_sets["Upper skin"], mesh.element_sets["Lower skin"]
    assert (normal[upper[box[upper]], 2] > 0.9).all() and (normal[lower[box[lower]], 2] < -0.9).all()
    nose = upper[centre[upper, 0] < 0.01]
    assert (normal[nose, 0] < 0).all()  # round the nose the outward normal points forward
    assert (normal[mesh.element_sets["Front spar"], 0] > 0.999).all()
    assert (normal[mesh.element_sets["Rib 2"], 1] < -0.999).all()


@needs_gmsh
def test_a_wing_without_ribs_has_skins_and_webs_only_and_a_rib_without_a_layup_has_no_thickness(tmp_path):
    shape = build_wing_shape(example(**{"geometry.rib_spacing": None, "rib": None}))
    assert [p.name for p in shape.parts] == ["Upper skin", "Lower skin", "Front spar", "Rear spar"] and shape.mesh is None
    shape = build_wing_shape(example(**{"rib": None}))
    assert shape.parts[-1].thickness_m is None and shape.mass_kg is None


@needs_gmsh
def test_an_open_trailing_edge_gets_a_strip_of_skin():
    wing = example(**{"skin.core_thickness": 0.0, "skin.core_density": None, "skin.half_stack": [0]})
    section = mid_surface_section(wing)
    assert not section.trailing_edge_closed
    shape = build_wing_shape(wing, element_size_m=0.03)
    assert "Trailing edge strip" in [p.name for p in shape.parts]
    assert set(shape.mesh.element_sets) >= {"Trailing edge strip"}


def test_step_names_are_refused_when_the_file_has_another_number_of_parts(tmp_path):
    step = tmp_path / "two.step"
    step.write_text("#7 = PRODUCT('Open CASCADE STEP translator 7.8 1',\n  'Open CASCADE STEP translator 7.8 1','',(#8));\n"
                    "#33 = PRODUCT('Open CASCADE STEP translator 7.8 1.1',\n  'Open CASCADE STEP translator 7.8 1.1','',(#34));\n",
                    encoding="ascii")
    with pytest.raises(ShapeError, match="has 1 parts where 2 were written"):
        name_step_products(step, "Wing", ["Upper skin", "Lower skin"])
    name_step_products(step, "Bob's wing", ["Upper skin"])
    assert "PRODUCT('Bob''s wing'" in step.read_text(encoding="ascii")


@needs_gmsh
def test_the_command_line_writes_the_step_file_and_prints_the_part_table(tmp_path, capsys):
    step = tmp_path / "example.step"
    main([str(EXAMPLE), str(step)])
    out = capsys.readouterr().out
    assert step.exists() and "9 parts written" in out and "Rib 5" in out and "whole wing, one side" in out
    assert math.isfinite(float(out.splitlines()[-2].split()[-1]))
