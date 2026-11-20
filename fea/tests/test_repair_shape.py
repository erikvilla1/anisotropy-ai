"""A stepped patch repair's shape (ADR-0131): the slice's mesh and the solids of its STEP file, each measured back against
the engine's figures and against sums written out here.

The mesh needs nothing beyond NumPy. Every test that builds solids skips with a reason when Gmsh is not installed
(`uv sync --extra mesh`).
"""

import math
import re
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.repair import areas, bond_lengths, region_at, regions, repair_from_dict, volumes
from anisotropy_fea.mesher import gmsh_available
from anisotropy_fea.repair_shape import ShapeError, build_repair_shape, main, read_step_volumes, slice_mesh, step_name

ENGINE = Path(__file__).parents[2] / "engine"
EXAMPLE = ENGINE / "examples" / "example-patch-repair.toml"
THROUGH = ENGINE / "validation" / "patch_repair_cases" / "constructed-cross-ply-patch-through-every-ply.toml"
needs_gmsh = pytest.mark.skipif(gmsh_available() is None,
                                reason="Gmsh is not available: from fea/ run `uv sync --extra mesh` (on Linux also apt install libglu1-mesa)")


def stated(path: Path = EXAMPLE, **changes):
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    data.pop("expected", None)
    for where, value in changes.items():
        table, key = where.split(".")
        if value is None:
            data.pop(table) if key == "*" else data[table].pop(key)
        else:
            data.setdefault(table, {})[key] = value
    return repair_from_dict(data)[0]


REPAIRS = {
    "the example": lambda: stated(),
    "the example without its cover ply": lambda: stated(**{"cover.*": None}),
    "two steps of two plies": lambda: stated(**{"steps.count": 2, "steps.plies": 2}),
    "through every ply": lambda: stated(THROUGH),
    "through every ply under a cover ply": lambda: stated(THROUGH, **{"cover.layup": [0, 90], "cover.overlap": 12.0}),
}


@pytest.mark.parametrize("name", REPAIRS)
def test_the_mesh_measures_back_to_the_description(name):
    repair = REPAIRS[name]()
    mesh = slice_mesh(repair)
    measured, by_description = mesh.areas(), areas(repair)
    for kind in by_description:
        assert measured[kind] == pytest.approx(by_description[kind], rel=1e-10, abs=1e-16), kind
    for part, area in zip(mesh.regions, mesh.region_areas()):
        assert area == pytest.approx(part.area, rel=1e-10), part.name  # every rectangle is filled, and by its own elements only
    # the bondline that touches the laminate: the ledges, the floor and the cover's overlap lying flat, and every cut face upright
    bond, lengths = mesh.bond_to_laminate(), bond_lengths(repair)
    eta, n = repair.adhesive.thickness_m, repair.steps
    radius = [repair.damage_diameter_m / 2 + (n - j) * repair.step_length_m for j in range(1, n + 1)]
    flat = (n - 1) * repair.step_length_m + (0.0 if repair.through else radius[-1]) + repair.cover_overlap_m
    assert bond["flat"] == pytest.approx(flat, rel=1e-10) == pytest.approx(lengths["ledges"] + lengths["floor"] + lengths["cover"])
    assert bond["upright"] == pytest.approx(repair.depth_m, rel=1e-10)
    assert eta < repair.group_thickness_m


@pytest.mark.parametrize("name", REPAIRS)
def test_every_element_is_one_part_and_the_mesh_has_no_gap_or_overlap(name):
    repair = REPAIRS[name]()
    mesh = slice_mesh(repair, element_size_m=repair.step_length_m / 16, per_ply=2)
    r, z = mesh.nodes_m[mesh.quads, 0], mesh.nodes_m[mesh.quads, 1]
    signed = 0.5 * np.sum(r * np.roll(z, -1, axis=1) - np.roll(r, -1, axis=1) * z, axis=1)
    assert np.all(signed > 0)  # corners counterclockwise
    assert mesh.quads.min() == 0 and len(np.unique(mesh.quads)) == len(mesh.nodes_m)  # no node left over
    for quad, index in zip(mesh.quads[::7], mesh.region[::7]):
        centre = mesh.nodes_m[quad].mean(axis=0)
        part = mesh.regions[index]
        assert part.r0 < centre[0] < part.r1 and part.z0 < centre[1] < part.z1
        assert region_at(repair, *centre) == part.kind
    # an edge belongs to two elements inside the slice and to one on its outline: no element lies on another
    edges: dict[tuple[int, int], int] = {}
    for quad in mesh.quads:
        for a, b in zip(quad, np.roll(quad, -1)):
            edges[(min(a, b), max(a, b))] = edges.get((min(a, b), max(a, b)), 0) + 1
    assert set(edges.values()) <= {1, 2}
    # the elements are no longer than asked along the slice and no thicker than half a ply
    assert (r.max(axis=1) - r.min(axis=1)).max() <= repair.step_length_m / 16 * (1 + 1e-9)
    assert (z.max(axis=1) - z.min(axis=1)).max() <= repair.ply_thickness_m / 2 * (1 + 1e-9)
    # a finer mesh has more elements and the same areas
    coarse = slice_mesh(repair)
    assert len(mesh.quads) > len(coarse.quads) and mesh.areas()["adhesive"] == pytest.approx(coarse.areas()["adhesive"], rel=1e-10)


def test_a_cut_through_every_ply_leaves_no_element_under_the_patch():
    repair = stated(THROUGH)
    mesh = slice_mesh(repair)
    eta = repair.adhesive.thickness_m
    centres = mesh.nodes_m[mesh.quads].mean(axis=1)
    under = (centres[:, 0] < repair.cut_radius_m(repair.steps) - eta) & (centres[:, 1] < eta)
    assert not under.any()
    above = centres[:, 1] > repair.thickness_m + eta  # nothing above the patch where there are no cover plies
    assert not above.any()


def test_a_mesh_that_cannot_be_made_is_refused_in_words():
    repair = stated()
    with pytest.raises(ShapeError, match="element size must be a positive number"):
        slice_mesh(repair, element_size_m=0.0)
    with pytest.raises(ShapeError, match="whole number, 1 or more"):
        slice_mesh(repair, per_ply=0)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if gmsh_available() is None:
        pytest.skip("Gmsh is not available")
    made = {}
    for name in ("the example", "through every ply"):
        repair = REPAIRS[name]()
        step = tmp_path_factory.mktemp("repair") / "repair.step"
        made[name] = (repair, build_repair_shape(repair, step, "A repair's name"), step)
    return made


@needs_gmsh
@pytest.mark.parametrize("name", ["the example", "through every ply"])
def test_the_solids_measure_back_to_the_description(built, name):
    repair, shape, _ = built[name]
    parts = regions(repair)
    assert [part.name for part in shape.parts] == [step_name(part) for part in parts]
    solid, swept = shape.volumes(), volumes(repair)
    for kind in swept:
        assert solid[kind] == pytest.approx(swept[kind], rel=1e-9, abs=1e-18), kind
    panel = repair.panel_length_m * repair.panel_width_m
    for made, part in zip(shape.parts, parts):  # each solid against its own ring, disc or slab with a hole, written out here
        height = part.z1 - part.z0
        expected = math.pi * (part.r1**2 - part.r0**2) * height if part.round else (panel - math.pi * part.r0**2) * height
        assert made.volume_m3 == pytest.approx(expected, rel=1e-9), part.name
        assert (made.kind, made.angle_deg) == (part.kind, part.angle_deg)


@needs_gmsh
@pytest.mark.parametrize("name", ["the example", "through every ply"])
def test_the_step_file_names_every_solid_and_reads_back_with_the_same_volumes(built, name):
    repair, shape, step = built[name]
    text = step.read_text(encoding="ascii")
    names = re.findall(r"PRODUCT\('((?:[^']|'')*)'", text)
    assert names[0] == "A repair''s name"  # the assembly, its apostrophe doubled as a STEP string asks
    assert sorted(names[1:]) == sorted(part.name for part in shape.parts) and len(names) == len(shape.parts) + 1
    assert "Open CASCADE STEP translator" not in "".join(names) and "deg)" in text and "°" not in text
    assert re.search(r"SI_UNIT\(\s*\.MILLI\.\s*,\s*\.METRE\.\s*\)", text)  # the file states millimetres
    # what a program that opens the file measures: the same volumes, solid for solid, in the order the names were given in
    read = read_step_volumes(step)
    ordered = {part.name: part.volume_m3 for part in shape.parts}
    assert len(read) == len(shape.parts)
    for label, volume in zip(names[1:], read):
        assert volume == pytest.approx(ordered[label], rel=1e-6), label


@needs_gmsh
def test_the_command_reports_the_mesh_and_writes_the_file(tmp_path, capsys):
    step = tmp_path / "example.step"
    main([str(EXAMPLE), "--step", str(step), "--size", "2.5"])
    out = capsys.readouterr().out
    assert "Example stepped patch repair" in out and "22 solids" in out and "mm^2 in the mesh" in out
    assert step.stat().st_size > 10_000
