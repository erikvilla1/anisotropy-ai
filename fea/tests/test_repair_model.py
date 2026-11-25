"""A stepped patch repair's slice solved in CalculiX (ADR-0132): the graded mesh and the deck, which need nothing beyond
NumPy, and the solve, whose tests skip with a reason when CalculiX is not installed. The solve is checked four ways: the
forces at every station add up to the load, far from the repair every ply's stress is the laminate theory's, the model held
to the stepped lap's assumptions returns the lap's closed form (fea/checks/repair_cases/, worked without the engine in
engine/validation/closed_forms.py), and a finer mesh gives the same answer."""

import importlib.util
import json
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.repair import areas, far_field, regions, repair_from_dict
from anisotropy_fea.calculix import find_ccx
from anisotropy_fea.repair_model import (
    ADHESIVE_LAYERS, FINE_PER_BONDLINE, BondLine, SliceModelError, build_slice_model, headline, is_cut_face, main, read_results, slice_report, solve_slice,
)
from anisotropy_fea.repair_shape import ShapeError, slice_mesh

ROOT = Path(__file__).parents[2]
ENGINE = ROOT / "engine"
EXAMPLE = ENGINE / "examples" / "example-patch-repair.toml"
STRIP = ENGINE / "validation" / "patch_repair_cases" / "constructed-external-strip-patch-of-another-material.toml"
THROUGH = ENGINE / "validation" / "patch_repair_cases" / "constructed-cross-ply-patch-through-every-ply.toml"
HELD = sorted((ROOT / "fea" / "checks" / "repair_cases").glob("*.toml"))
# A real repair with its answers stays outside the repository (ADR-0042): one that states what a solve needs is solved when present.
LOCAL = sorted((ROOT / ".local" / "repair" / "patch-cases").glob("*.toml"))
SOLVE = {"parent.nu23": 0.4, "patch.nu23": 0.4, "adhesive.poisson": 0.35}  # what the engine's cases leave out and a solve needs
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)")


def stated(path: Path = EXAMPLE, **changes):
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    data.pop("expected", None)
    data.pop("solve", None)
    for where, value in changes.items():
        table, key = where.split(".")
        if value is None:
            data[table].pop(key)
        elif table in data:
            data[table][key] = value
    return repair_from_dict(data)


def closed_forms():
    spec = importlib.util.spec_from_file_location("closed_forms", ENGINE / "validation" / "closed_forms.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shear_at(line, r: float) -> float:
    """A bondline's shear stress at r, on the straight line through its two stations nearest r."""
    k = np.argsort(np.abs(line.r_m - r))[:2]
    (r0, r1), (s0, s1) = line.r_m[k], line.shear_pa[k]
    return float(s0 + (s1 - s0) * (r - r0) / (r1 - r0))


# ------------------------------------------------------------------------------------------- the mesh and the deck


@pytest.mark.parametrize("path, changes", [(EXAMPLE, {}), (THROUGH, {}), (STRIP, {})], ids=["the example", "through every ply", "a strip patch"])
def test_the_graded_mesh_is_fine_beside_every_edge_and_still_the_repair(path, changes):
    repair, _ = stated(path, **changes)
    bondline = repair.adhesive.thickness_m
    fine, coarse = bondline / FINE_PER_BONDLINE, repair.step_length_m / 8
    mesh = slice_mesh(repair, fine_m=fine, adhesive_layers=ADHESIVE_LAYERS)
    r, sizes = mesh.r_lines_m, np.diff(mesh.r_lines_m)
    parts = regions(repair)
    edges = sorted({edge for part in parts for edge in (part.r0, part.r1)})
    for edge in edges:
        k = int(np.argmin(np.abs(r - edge)))
        assert abs(r[k] - edge) < 1e-12  # a line of nodes on every edge of every rectangle
        if 0 < k < len(r) - 1:
            assert sizes[k - 1] <= fine * (1 + 1e-9) and sizes[k] <= fine * (1 + 1e-9)  # and the elements beside it are fine
    assert sizes.max() <= coarse * (1 + 1e-9) and sizes.min() > fine / 3
    assert np.max(np.maximum(sizes[1:] / sizes[:-1], sizes[:-1] / sizes[1:])) < 1.3 * 1.3  # no element much longer than its neighbour
    measured, by_description = mesh.areas(), areas(repair)
    for kind in by_description:
        assert measured[kind] == pytest.approx(by_description[kind], rel=1e-9, abs=1e-16), kind
    for index, part in enumerate(parts):  # the bondline has two elements through its thickness wherever it lies flat
        if part.kind == "adhesive" and not is_cut_face(repair, part):
            assert len(np.unique(mesh.cell[mesh.region == index, 1])) == ADHESIVE_LAYERS, part.name
    assert len(mesh.cell) == len(mesh.quads) and mesh.cell[:, 0].max() == len(r) - 2
    centres = mesh.nodes_m[mesh.quads].mean(axis=1)
    assert np.allclose(centres[:, 0], ((r[:-1] + r[1:]) / 2)[mesh.cell[:, 0]]) and len(slice_mesh(repair).quads) < len(mesh.quads)


def test_a_graded_mesh_that_cannot_be_made_is_refused():
    repair, _ = stated()
    for options in (dict(fine_m=0.0), dict(fine_m=1.0), dict(fine_m=1e-5, growth=1.0), dict(fine_m=1e-5, growth=3.0), dict(adhesive_layers=0),
                    dict(adhesive_layers=1.5)):
        with pytest.raises(ShapeError):
            slice_mesh(repair, **options)


def test_the_deck_is_the_slice_with_the_far_field_on_its_end():
    repair, load = stated()
    model = build_slice_model(repair, load, cut_faces="bonded")
    mesh, deck = model.mesh, model.deck
    assert deck.count("*ELEMENT, TYPE=CPE8R") == deck.count("*ELASTIC, TYPE=ORTHO") == deck.count("*EXPANSION, TYPE=ORTHO") == 5  # four ply angles, the adhesive
    assert len(model.elements) == len(mesh.quads) and model.elements.shape[1] == 8
    for k in range(4):  # each added node is the middle of its edge
        ends = model.nodes_m[model.elements[:, [k, (k + 1) % 4]]]
        assert np.allclose(model.nodes_m[model.elements[:, 4 + k]], ends.mean(axis=1), atol=1e-15)
    assert np.array_equal(model.elements[:, :4], mesh.quads) and len(np.unique(model.elements)) == len(model.nodes_m)
    far = far_field(repair, load)
    assert model.far == far and f"NALL, {far.strain_width:.12g}" in deck
    rows = [line.split(", ") for line in deck[deck.index("*DLOAD"):deck.index("*EL PRINT")].splitlines()[1:]]
    last = mesh.cell[:, 0].max()
    assert sorted(int(row[0]) - 1 for row in rows) == sorted(np.flatnonzero(mesh.cell[:, 0] == last)) and {row[1] for row in rows} == {"P2"}
    height = np.diff(mesh.z_lines_m)[mesh.cell[:, 1]]
    assert sum(-float(row[2]) * 1e6 * height[int(row[0]) - 1] for row in rows) == pytest.approx(load, rel=1e-9)  # the tractions are the load
    # the adhesive on the cut faces is left out unless it is asked for
    open_model = build_slice_model(repair, load)
    cut = [index for index, part in enumerate(mesh.regions) if is_cut_face(repair, part)]
    assert len(cut) == repair.steps and np.isin(mesh.region, cut).any() and not np.isin(open_model.mesh.region, cut).any()
    assert len(open_model.elements) == len(model.elements) - int(np.isin(mesh.region, cut).sum()) and open_model.cut_faces == "open"
    assert len(np.unique(open_model.elements)) == len(open_model.nodes_m)  # no node is left without an element


def test_the_largest_mean_over_a_length_of_bond_is_found_exactly():
    # five stations of unequal columns; the means over a length of 2 are worked by hand
    line = BondLine("a bond", 1, np.array([0.5, 1.5, 2.25, 2.75, 3.5]), np.array([1.0, 3.0, 7.0, -9.0, -8.0]), np.array([0.0, -4.0, 6.0, 6.0, 20.0]),
                    np.array([0.0, 1.0, 2.0, 2.5, 3.0, 4.0]))
    value, r = line.largest_mean(line.peel_pa, 2.0, lambda means: means)
    assert value == pytest.approx((6.0 * 0.5 + 6.0 * 0.5 + 20.0 * 1.0) / 2) and r == pytest.approx(3.0)  # the last two units of the bond
    value, r = line.largest_mean(line.shear_pa, 1.0)
    assert value == pytest.approx(-9.0 * 0.5 - 8.0 * 0.5) and r == pytest.approx(3.0)  # the largest in size keeps its sign: 2.5 to 3.5
    value, r = line.largest_mean(line.shear_pa, 1.0, lambda means: means)
    assert value == pytest.approx(3.0 * 0.5 + 7.0 * 0.5) and r == pytest.approx(2.0)  # 1.5 to 2.5
    value, r = line.largest_mean(line.shear_pa, 0.25)
    assert value == pytest.approx(-9.0) and 2.5 + 0.125 <= r <= 3.0 - 0.125  # a length shorter than a column reads the column
    value, r = line.largest_mean(line.peel_pa, 50.0)
    assert value == pytest.approx((0.0 - 4.0 + 3.0 + 3.0 + 20.0) / 4) and r == pytest.approx(2.0)  # a bond shorter than the length is taken whole
    fine = np.linspace(0.0, 4.0, 4001)
    brute = max(abs(float(np.interp(s + 1.0, line.edges_m, np.concatenate([[0.0], np.cumsum(line.shear_pa * np.diff(line.edges_m))]))
                          - np.interp(s, line.edges_m, np.concatenate([[0.0], np.cumsum(line.shear_pa * np.diff(line.edges_m))])))) for s in fine[fine <= 3.0])
    assert abs(line.largest_mean(line.shear_pa, 1.0)[0]) == pytest.approx(brute, rel=1e-9)  # no position between the columns' ends does better


def test_what_a_solve_lacks_is_refused_in_words():
    repair, load = stated()
    for options, words in ((dict(hold="top"), "hold must be"), (dict(cut_faces="glued"), "cut_faces must be")):
        with pytest.raises(SliceModelError, match=words):
            build_slice_model(repair, load, **options)
    for bad in (0.0, float("nan"), None, True):
        with pytest.raises(SliceModelError, match="needs a load"):
            build_slice_model(repair, bad)
    with pytest.raises(SliceModelError, match="through-thickness constants"):
        build_slice_model(stated(**{"parent.nu23": None})[0], load)
    with pytest.raises(SliceModelError, match="Poisson's ratio"):
        build_slice_model(stated(**{"adhesive.poisson": None})[0], load)
    with pytest.raises(SliceModelError, match="max_stress, tsai_hill"):
        solve_slice(repair, load, criterion="tsai_wu")
    with pytest.raises(SliceModelError, match="did not print every element"):
        model = build_slice_model(*stated(STRIP, **SOLVE))
        rows = "\n".join(f" {e} 1 1. 0. 0. 0. 0. 0." for e in range(1, 4))
        read_results(model, f" stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set EALL and time  0.1E+01\n\n{rows}\n\n"
                            f" strains (elem, integ.pnt.,exx,eyy,ezz,exy,exz,eyz) for set EALL and time  0.1E+01\n\n{rows}\n")


# ------------------------------------------------------------------------------------------------------ the solve


@pytest.fixture(scope="module")
def strip():
    return solve_slice(*stated(STRIP, **SOLVE))


@pytest.fixture(scope="module")
def example():
    return solve_slice(*stated())


@pytest.fixture(scope="module")
def bonded():
    return solve_slice(*stated(), cut_faces="bonded")


@needs_ccx
@pytest.mark.parametrize("name", ["strip", "example", "bonded"])
def test_the_forces_add_up_and_the_far_field_is_the_laminate_theorys(name, request):
    answer = request.getfixturevalue(name)
    model, load = answer.model, answer.model.load_n_per_m
    assert answer.equilibrium_error < 1e-6 and answer.far_field_error < 1e-5
    assert np.allclose(answer.patch_force + answer.laminate_force + answer.adhesive_force, load, rtol=1e-6)
    mesh = model.mesh
    column = int(np.argmin(np.abs(answer.stations_m - 0.9 * model.repair.panel_length_m / 2)))  # well outside the repair
    there = np.flatnonzero(mesh.cell[:, 0] == column)
    assert len(there) >= model.repair.plies
    for e in there:
        part = mesh.regions[mesh.region[e]]
        assert part.kind == "parent"
        assert answer.results.stress[e, 0] == pytest.approx(model.far.ply_stress_x[part.ply - 1], rel=1e-5)  # along the load
        assert abs(answer.results.stress[e, 2]) < 1e-6 * abs(load) / model.repair.thickness_m  # nothing through the thickness
        assert answer.results.strain[e, 0] == pytest.approx(model.far.strain_x, rel=1e-5)
    across = sum(answer.results.stress[e, 1] * np.diff(mesh.z_lines_m)[mesh.cell[e, 1]] for e in there)
    assert abs(across) < 1e-6 * abs(load)  # and the plies' stresses across the width cancel: the laminate is free to contract


@needs_ccx
@pytest.mark.parametrize("path", HELD, ids=[path.stem for path in HELD])
def test_held_to_the_laps_assumptions_the_model_returns_the_laps_closed_form(path):
    case = tomllib.loads(path.read_text(encoding="utf-8"))
    expected = case["expected"]
    reference = closed_forms().external_patch_repair({key: value for key, value in case.items() if key not in ("solve", "expected")})
    for key in ("boundary_forces", "shear_at_ends", "peak_shear", "elastic_limit_load"):  # the case's numbers are the closed form's
        assert np.asarray(expected[key], dtype=float).ravel() == pytest.approx(np.asarray(reference[key], dtype=float).ravel(), rel=1e-9)
    repair, load = stated(path)
    answer = solve_slice(repair, load, hold=case["solve"]["hold"])
    mm, mpa, per_mm = 1e-3, 1e6, 1e3
    forces = [boundary.patch / per_mm for boundary in answer.boundaries]
    assert len(forces) == len(expected["boundary_forces"]) - 1
    for got, want in zip(forces, expected["boundary_forces"][1:]):
        assert abs(got - want) < expected["force_tolerance"] * case["applied"]["load"]
    (line,) = answer.bond
    ends = [repair.cut_radius_m(1) - k * repair.step_length_m for k in range(repair.steps)] + [repair.damage_diameter_m / 2]
    want = [expected["shear_at_ends"][0][0]] + [row[1] for row in expected["shear_at_ends"]]
    for r, value in zip(ends, want):
        assert abs(shear_at(line, r) / mpa - value) < expected["shear_tolerance"] * expected["peak_shear"], r / mm
    # the whole curve, against the engine's lap (itself checked against the same closed form in the engine's tests)
    x, tau, _ = answer.lap.distribution(201)
    by_hand = np.interp(line.r_m, (repair.cut_radius_m(1) - x)[::-1], tau[::-1])
    assert np.max(np.abs(line.shear_pa - by_hand)) < expected["shear_tolerance"] * expected["peak_shear"] * mpa
    assert np.max(np.abs(line.peel_pa)) < 1e-6 * expected["peak_shear"] * mpa  # nothing peels when nothing can move through the thickness
    # the model's largest shear stress is a mean over one bondline's thickness of bond: the hand calculation's curve over the same length
    x, tau, _ = answer.lap.distribution(20001)
    last = x >= x[-1] - repair.adhesive.thickness_m
    mean = float(np.sum((tau[last][1:] + tau[last][:-1]) / 2 * np.diff(x[last])) / (x[last][-1] - x[last][0]))
    assert mean < 0.97 * expected["peak_shear"] * mpa and answer.peak_shear.value_pa == pytest.approx(mean, rel=0.005)
    assert answer.peak_shear.r_m == pytest.approx(repair.damage_diameter_m / 2 + repair.adhesive.thickness_m / 2, rel=1e-9)
    assert answer.elastic_limit_load == pytest.approx(load * repair.adhesive.shear_strength_pa / mean, rel=0.005)


@needs_ccx
def test_a_patch_bonded_on_top_carries_everything_at_the_holes_edge_and_bends(strip):
    repair, load = strip.model.repair, strip.model.load_n_per_m
    last = strip.boundaries[-1]
    assert last.r_m == pytest.approx(repair.damage_diameter_m / 2) and last.patch + last.adhesive == pytest.approx(load, rel=5e-3)
    assert abs(last.laminate) < 5e-3 * load
    for boundary in strip.boundaries:  # the lap's forces, within a tenth of the load, and never more than the load
        assert abs(boundary.patch - boundary.hand_patch) < 0.1 * load and 0 < boundary.patch <= load
    (line,) = strip.bond
    assert np.all(np.diff(line.r_m) > 0) and line.r_m[0] > repair.damage_diameter_m / 2 and line.r_m[-1] < repair.patch_radius_m
    # what the bondline's shear passes to the patch between its edge and the hole is what the patch carries there
    passed = float(np.sum((line.shear_pa[1:] + line.shear_pa[:-1]) / 2 * np.diff(line.r_m)))
    assert passed == pytest.approx(load, rel=0.01)
    hand = abs(strip.lap.peak_shear[0])
    assert 0.5 * hand < strip.peak_shear.value_pa < 0.75 * hand  # the patch bends where it takes the load, which the lap leaves out
    assert strip.peak_shear.r_m == pytest.approx(repair.damage_diameter_m / 2, abs=repair.thickness_m)
    assert strip.peak_peel.value_pa > 0 and strip.peak_peel.r_m == pytest.approx(repair.patch_radius_m, abs=repair.adhesive.thickness_m)
    assert line.peel_pa[0] < 0  # pressed on at the hole's edge, pulled off at its tip
    assert strip.elastic_limit_load == pytest.approx(load * repair.adhesive.shear_strength_pa / strip.peak_shear.value_pa)
    assert strip.peel_limit_load is None and strip.first == ("adhesive", strip.elastic_limit_load)
    assert all(ply.ratio is None for ply in strip.plies) and strip.first_ply is None and not strip.cut_faces  # the case states no strengths


@needs_ccx
def test_the_answer_grows_with_the_load_and_a_finer_mesh_does_not_change_it(strip):
    repair, load = strip.model.repair, strip.model.load_n_per_m
    double = solve_slice(repair, 2 * load)
    assert double.peak_shear.value_pa == pytest.approx(2 * strip.peak_shear.value_pa, rel=1e-6)
    assert double.peak_peel.value_pa == pytest.approx(2 * strip.peak_peel.value_pa, rel=1e-6)
    assert double.elastic_limit_load == pytest.approx(strip.elastic_limit_load, rel=1e-6)
    finer = solve_slice(repair, load, fine_m=repair.adhesive.thickness_m / (2 * FINE_PER_BONDLINE))
    assert len(finer.model.elements) > len(strip.model.elements)
    assert finer.peak_shear.value_pa == pytest.approx(strip.peak_shear.value_pa, rel=0.005)
    assert finer.peak_peel.value_pa == pytest.approx(strip.peak_peel.value_pa, rel=0.01)
    for a, b in zip(finer.boundaries, strip.boundaries):
        assert a.patch == pytest.approx(b.patch, rel=0.002)
    peel = solve_slice(stated(STRIP, **SOLVE, **{"adhesive.peel_strength": 5.0})[0], load)
    assert peel.peel_limit_load == pytest.approx(load * 5e6 / strip.peak_peel.value_pa, rel=1e-6) and peel.first[0] == "peel"
    pushed = solve_slice(repair, -load)  # under compression every stress changes sign, so the tip is pressed on, not pulled off
    assert pushed.peak_shear.value_pa == pytest.approx(-strip.peak_shear.value_pa, rel=1e-6)
    assert pushed.elastic_limit_load == pytest.approx(strip.elastic_limit_load, rel=1e-6)


@needs_ccx
def test_the_flush_example_with_its_cut_faces_open_is_near_the_hand_calculation(example):
    repair, load = example.model.repair, example.model.load_n_per_m
    assert [b.name for b in example.boundaries] == ["Cover overlap", "Ledge of step 1", "Ledge of step 2", "Ledge of step 3", "Floor"]
    for boundary in example.boundaries:
        assert abs(boundary.patch - boundary.hand_patch) < 0.01 * load  # the patch's force, within a hundredth of the load
        assert boundary.patch + boundary.laminate + boundary.adhesive == pytest.approx(load, rel=1e-6)
    assert example.boundaries[-1].r_m == 0.0 and not example.cut_faces
    hand = abs(example.lap.peak_shear[0])
    assert 0.85 * hand < example.peak_shear.value_pa < hand
    assert example.peak_shear.name == "Adhesive on the ledge of step 2"  # where the 0 degree patch ply begins, as in the hand calculation
    assert [line.name for line in example.bond] == ["Adhesive on the floor", "Adhesive on the ledge of step 3", "Adhesive on the ledge of step 2",
                                                    "Adhesive on the ledge of step 1", "Adhesive under the cover plies"]
    assert example.elastic_limit_load == pytest.approx(load * 30e6 / example.peak_shear.value_pa)
    # every ply is checked, and the weakest is weaker than far from the repair
    assert len(example.plies) == 8 + 4 + 1 and all(ply.ratio is not None and ply.ratio > 1 and ply.mode for ply in example.plies)
    first = example.first_ply
    far_ratio = min(64052295.25353406 / stress for stress, angle in zip(example.model.far.ply_stress_x, repair.parent_angles) if angle == 90)
    assert first.ratio < far_ratio and first.mode == "transverse tension" and 0 < first.r_m < repair.cover_radius_m
    assert example.first_ply_load == pytest.approx(load * first.ratio)
    assert example.first == ("adhesive", example.elastic_limit_load) and example.elastic_limit_load < example.first_ply_load
    # a bond is the adhesive between the patch and the laminate: not the corner of adhesive under a cut face or over one
    bondline = repair.adhesive.thickness_m
    for line, step in zip(example.bond[1:4], (3, 2, 1)):  # the ledges, from the deepest
        assert line.edges_m[0] == pytest.approx(repair.cut_radius_m(step + 1)) and line.edges_m[-1] == pytest.approx(repair.cut_radius_m(step) - bondline)
        assert len(line.edges_m) == len(line.r_m) + 1 and np.allclose(line.r_m, (line.edges_m[1:] + line.edges_m[:-1]) / 2)
    assert example.bond[0].edges_m[0] == 0.0 and example.bond[-1].edges_m[-1] == pytest.approx(repair.cover_radius_m)
    # the largest stresses are means over a square of adhesive, which a mesh twice as fine beside every edge does not change
    assert example.peak_shear.value_pa == pytest.approx(example.bond[2].largest_mean(example.bond[2].shear_pa, bondline)[0])
    assert example.peak_peel.name == "Adhesive under the cover plies" and example.peak_peel.r_m == pytest.approx(repair.cover_radius_m - bondline / 2)
    finer = solve_slice(repair, load, fine_m=bondline / (2 * FINE_PER_BONDLINE))
    assert finer.peak_shear.value_pa == pytest.approx(example.peak_shear.value_pa, rel=0.005)
    assert finer.peak_peel.value_pa == pytest.approx(example.peak_peel.value_pa, rel=0.01)
    assert finer.first_ply.ratio == pytest.approx(first.ratio, rel=0.002) and finer.first_ply.name == first.name
    assert np.max(finer.bond[2].peel_pa) > 1.2 * np.max(example.bond[2].peel_pa)  # where the last station's value does change, beside an open cut face
    hill = solve_slice(repair, load, criterion="tsai_hill")
    assert hill.first_ply.ratio <= first.ratio * (1 + 1e-9) and hill.peak_shear.value_pa == pytest.approx(example.peak_shear.value_pa, rel=1e-9)


@needs_ccx
def test_bonded_cut_faces_take_load_off_the_ledges(example, bonded):
    assert [face.step for face in bonded.cut_faces] == [4, 3, 2, 1] and all(face.normal_pa > 0 for face in bonded.cut_faces)
    by_step = {face.step: face.normal_pa for face in bonded.cut_faces}
    assert max(by_step, key=by_step.get) == 2  # the cut end of the laminate's 0 degree ply pulls hardest on its butt joint
    assert bonded.peak_shear.value_pa < 0.9 * example.peak_shear.value_pa
    assert bonded.elastic_limit_load > example.elastic_limit_load  # so leaving them open is the safe reading
    assert len(bonded.model.elements) > len(example.model.elements)


@needs_ccx
def test_the_report_is_in_the_files_units(example):
    report = slice_report(example, "mm-MPa")
    json.dumps(report)  # plain numbers and words only
    assert report["units"] == {"length": "mm", "stress": "MPa", "force": "N/mm"} and report["load"] == pytest.approx(100.0)
    assert report["model"]["element"] == "CPE8R" and report["model"]["hold"] == "bottom" and report["model"]["cut_faces"] == "open"
    assert report["model"]["elements"] == len(example.model.elements) and report["model"]["equations"] > 2 * report["model"]["nodes"] * 0.9
    assert report["model"]["fine_size"] <= 0.1 / FINE_PER_BONDLINE and report["model"]["element_size"] <= 12.5 / 8 * (1 + 1e-9)
    assert report["bond"]["peak_shear"]["value"] == pytest.approx(example.peak_shear.value_pa / 1e6) and report["bond"]["mean_over"] == pytest.approx(0.1)
    assert report["hand"]["peak_shear"] == pytest.approx(12.58, abs=0.01) and report["hand"]["elastic_limit_load"] == pytest.approx(238.5, abs=0.1)
    assert report["elastic_limit_load"] == pytest.approx(example.elastic_limit_load / 1e3)
    assert report["peel_limit_load"] == pytest.approx(example.peel_limit_load / 1e3) and report["peel_limit_load"] > 3 * report["elastic_limit_load"]
    assert report["first"] == {"what": "adhesive", "load": report["elastic_limit_load"]}
    assert report["first_ply"]["load"] == pytest.approx(100.0 * report["first_ply"]["strength_ratio"])
    assert len(report["forces"]["r"]) == len(report["forces"]["patch"]) == len(example.stations_m)
    assert "largest bondline shear" in headline(report) and "the adhesive reaches its elastic limit in shear" in headline(report)
    psi = slice_report(example, "psi")
    assert psi["bond"]["peak_shear"]["value"] == pytest.approx(example.peak_shear.value_pa / 6894.757293168, rel=1e-9)
    with pytest.raises(SliceModelError, match="units"):
        slice_report(example, "furlongs")


@needs_ccx
def test_the_command_solves_a_file_and_says_why_it_cannot(tmp_path, capsys):
    assert main([str(EXAMPLE), "--out", str(tmp_path / "run"), "--cut-faces", "bonded"]) == 0
    printed = capsys.readouterr().out
    assert "Example stepped patch repair" in printed and "CPE8R" in printed and "The adhesive on the cut faces is bonded" in printed
    assert "Adhesive on the cut face of step 2" in printed and "First, the adhesive reaches its elastic limit in shear" in printed
    report = json.loads((tmp_path / "run" / "repair-solve.json").read_text(encoding="utf-8"))
    assert report["model"]["cut_faces"] == "bonded" and (tmp_path / "run" / "repair-slice.inp").exists() and (tmp_path / "run" / "repair-slice.dat").exists()
    assert main([str(STRIP)]) == 2  # an engine case: a hand calculation's inputs only
    assert "refused: The solve of the slice needs the through-thickness constants" in capsys.readouterr().out
    silent = tmp_path / "no-load.toml"
    silent.write_text(EXAMPLE.read_text(encoding="utf-8").split("[applied]")[0], encoding="utf-8")
    assert main([str(silent)]) == 2 and "states no load" in capsys.readouterr().out


@needs_ccx
@pytest.mark.parametrize("path", LOCAL, ids=[path.stem for path in LOCAL])
def test_a_private_repair_that_states_what_a_solve_needs_is_solved(path):
    case = tomllib.loads(path.read_text(encoding="utf-8"))
    repair, load = stated(path)
    if load is None or repair.adhesive.poisson_ratio is None or repair.parent_material.through is None or repair.patch_material.through is None:
        pytest.skip("this repair states a hand calculation's inputs only")
    answer = solve_slice(repair, load)
    assert answer.equilibrium_error < 1e-6 and answer.far_field_error < 1e-4
    assert slice_report(answer, case["units"])["bond"]["peak_shear"]["value"] > 0
