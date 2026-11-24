"""A stepped patch repair's bond followed until it lets go (ADR-0137): the model built from the repair, held four ways, and
the answer read from its path.

- Its elements, load and holds are the elastic solve's: on CalculiX's own model, this package's plane elements return
  CalculiX's strains.
- Its pairs are the stepped lap's adhesive: held to the lap's assumptions, the bond first softens at the load of the lap's
  closed form (fea/checks/repair_cases/, worked without the engine in engine/validation/closed_forms.py).
- With the bond whole, the patch carries what it carries in CalculiX's slice, where the adhesive is solid elements.
- A coarser mesh gives the same loads.

The path follower itself is held to exact fracture answers in test_bond_solver.py."""

import json
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.repair import repair_from_dict
from anisotropy_fea.bond_solver import element_strains
from anisotropy_fea.calculix import find_ccx
from anisotropy_fea.repair_bond import (
    FINE_PER_BONDLINE, LET_GO_FALL, PLANE, REPORT, BondRunError, bond_answer, bond_law, bond_report, build_bond_model, elastic_slice, follow_bond,
    headline, main, run_bond,
)
from anisotropy_fea.repair_model import build_slice_model, run_slice_model, slice_answer

ROOT = Path(__file__).parents[2]
ENGINE = ROOT / "engine"
EXAMPLE = ENGINE / "examples" / "example-patch-repair.toml"
STRIP = ENGINE / "validation" / "patch_repair_cases" / "constructed-external-strip-patch-of-another-material.toml"
THROUGH = ENGINE / "validation" / "patch_repair_cases" / "constructed-cross-ply-patch-through-every-ply.toml"
HELD = ROOT / "fea" / "checks" / "repair_cases" / "constructed-external-strip-held-to-the-stepped-laps-assumptions.toml"
BOND = {"adhesive.peel_strength": 40.0, "adhesive.peel_energy": 0.5, "adhesive.shear_energy": 2.0}  # round numbers of our own, beside a case's shear strength
SOLVE = {"parent.nu23": 0.4, "patch.nu23": 0.4, "adhesive.poisson": 0.35}  # what the engine's cases leave out and a solve needs
MM, MPA, PER_MM = 1e-3, 1e6, 1e3
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)")


def table(path: Path = EXAMPLE, **changes) -> dict:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    data.pop("expected", None)
    data.pop("solve", None)
    for where, value in changes.items():
        name, key = where.split(".")
        if value is None:
            data[name].pop(key)
        elif name in data and (name != "patch" or "E1" in data[name]):  # a patch of the laminate's material states no constants of its own
            data[name][key] = value
    return data


def stated(path: Path = EXAMPLE, **changes):
    return repair_from_dict(table(path, **changes))


@pytest.fixture(scope="module")
def example():
    return run_bond(stated()[0])


# ---------------------------------------------------------------- the model


def test_the_bond_is_refused_without_its_six_numbers():
    bare, _ = stated(**{"adhesive.peel_strength": None, "adhesive.shear_energy": None, "parent.nu23": None})
    with pytest.raises(BondRunError, match="needs the laminate ply's constants through the thickness.*; the bond's peel strength; the bond's fracture energy in shear"):
        build_bond_model(bare)
    # 30 MPa on a bondline of 1000 MPa and 0.1 mm holds 0.045 N/mm when it reaches its strength
    weak, _ = stated(**{"adhesive.shear_energy": 0.04})
    with pytest.raises(BondRunError, match="shear energy is under the energy it holds when it reaches its shear strength: it must be above 45 J/m\\^2"):
        build_bond_model(weak)
    with pytest.raises(BondRunError, match="hold must be one of"):
        build_bond_model(stated()[0], hold="nowhere")


def test_the_law_is_the_adhesives_stiffness_over_the_bondlines_thickness_with_its_strengths_and_energies():
    law = bond_law(stated()[0])
    assert law.shear_stiffness == pytest.approx(1000e6 / 0.1e-3)
    modulus = 2 * 1000e6 * 1.35  # E = 2 G (1 + nu); kept from straining in its plane it is E (1 - nu) / ((1 + nu) (1 - 2 nu))
    assert law.peel_stiffness == pytest.approx(modulus * 0.65 / (1.35 * 0.30) / 0.1e-3)
    assert (law.shear_strength, law.peel_strength, law.shear_energy, law.peel_energy) == pytest.approx((30e6, 40e6, 2000.0, 500.0))
    assert law.final_slip == pytest.approx(0.1333e-3, rel=1e-3) and law.final_opening == pytest.approx(0.025e-3)


def test_the_models_pairs_are_the_flat_bondline_and_its_load_is_one_newton_per_metre():
    repair, _ = stated()
    built = build_bond_model(repair)
    model, mesh = built.model, built.mesh
    assert not any(mesh.regions[index].kind == "adhesive" for index in mesh.region)  # the adhesive is the pairs, not elements
    assert [stretch.name for stretch in built.stretches] == ["Adhesive on the floor", "Adhesive on the ledge of step 3", "Adhesive on the ledge of step 2",
                                                             "Adhesive on the ledge of step 1", "Adhesive under the cover plies"]
    # each ledge's bond is its 12.5 mm less the bondline's width under the cut face at its end; the cover's overlap is whole
    lengths = [model.weight[stretch.pairs].sum() / MM for stretch in built.stretches]
    assert lengths == pytest.approx([12.4, 12.4, 12.4, 12.4, 12.5], rel=1e-9) and built.bond_length_m == pytest.approx(62.1 * MM)
    assert np.array_equal(np.sort(np.concatenate([stretch.pairs for stretch in built.stretches])), np.arange(len(model.weight)))
    # a pair is a node of the laminate's and the node above it on the patch's side, one bondline higher
    under, over = model.nodes[model.under], model.nodes[model.over]
    assert under[:, 0] == pytest.approx(over[:, 0], abs=1e-12) and over[:, 1] - under[:, 1] == pytest.approx(0.1 * MM, rel=1e-9)
    for stretch in built.stretches:
        assert np.all(np.diff(built.pair_r_m[stretch.pairs]) > 0)
    assert built.end_load[0::2].sum() == pytest.approx(1.0) and not built.end_load[1::2].any()
    assert built.fine_m <= 0.1 * MM / FINE_PER_BONDLINE


@needs_ccx
@pytest.mark.parametrize("options", [{}, {"cut_faces": "bonded"}], ids=["open", "bonded"])
def test_on_calculixs_own_model_our_plane_elements_return_calculixs_strains(options):
    """The elastic slice of ADR-0132, solved twice on the same nodes and elements: by CalculiX, and by the plane elements,
    the load and the holds the bond's model is made of. CalculiX prints seven figures."""
    repair, load = stated()
    model = build_slice_model(repair, load, **options)
    theirs, ours = run_slice_model(model), elastic_slice(model)
    assert np.abs(ours.strain - theirs.strain).max() < 2e-6 * np.abs(theirs.strain).max()
    assert np.abs(ours.stress - theirs.stress).max() < 2e-6 * np.abs(theirs.stress).max()
    a, b = slice_answer(model, theirs), slice_answer(model, ours)
    assert b.elastic_limit_load == pytest.approx(a.elastic_limit_load, rel=1e-6) and b.peak_peel.value_pa == pytest.approx(a.peak_peel.value_pa, rel=1e-6)


def test_held_to_the_laps_assumptions_the_bond_first_softens_at_the_laps_elastic_limit_load():
    """The stepped lap of ADR-0130 is rods joined by springs in shear. With every Poisson's ratio zero, the plies all but
    rigid in shear through their thickness and no node free to move through the thickness, the bond's model is that, and its
    pairs are the lap's springs exactly: the load at which the first pair reaches the shear strength is the closed form's
    elastic limit load, and the shear stress at the bond's outer end is the closed form's."""
    case = tomllib.loads(HELD.read_text(encoding="utf-8"))
    expected = case["expected"]
    repair, load = stated(HELD, **BOND)
    built = build_bond_model(repair, hold="everywhere")
    path, _ = follow_bond(built, steps=1)
    assert path.onset_load / PER_MM == pytest.approx(expected["elastic_limit_load"], rel=1e-4)
    first = path.points[0]
    _, slip = built.model.jumps(first.displacement / first.load)  # per newton per metre, the bond whole
    shear = -built.law.shear_stiffness * slip * load
    (stretch,) = built.stretches
    assert built.pair_r_m[stretch.pairs][[0, -1]] == pytest.approx([10 * MM, 55 * MM])  # from the hole's edge to the patch's
    assert shear[stretch.pairs][0] / MPA == pytest.approx(expected["peak_shear"], rel=1e-4)
    assert shear[stretch.pairs][-1] / MPA == pytest.approx(expected["shear_at_ends"][0][0], rel=1e-4)
    assert not np.abs(built.model.jumps(first.displacement)[0]).max() > 0  # nothing peels when nothing moves through the thickness


@needs_ccx
def test_with_the_bond_whole_the_patch_carries_what_it_carries_in_calculixs_slice():
    """Pairs in place of the adhesive's elements leave the load's path as it was. Midway along every step the patch's force
    is CalculiX's within a third of a percent of the load. At a step's end the two differ, as they should: a solid adhesive's
    shear stress falls to nothing at its free end, a pair's is largest there."""
    repair, load = stated()
    theirs = slice_answer(*(lambda model: (model, run_slice_model(model)))(build_slice_model(repair, load)))
    built = build_bond_model(repair)
    path, _ = follow_bond(built, steps=1)
    first = path.points[0]
    displacement = first.displacement * load / first.load
    mesh, model = built.mesh, built.model
    strain = element_strains(model.nodes, model.elements, displacement)
    stress = np.empty(len(strain))
    for index, matrix in enumerate(built.solid):
        rows = mesh.region == index
        stress[rows] = strain[rows] @ matrix[0, PLANE] + matrix[0, 1] * built.far.strain_width * load
    kinds = np.array([part.kind for part in mesh.regions])[mesh.region]
    rows = np.isin(kinds, ("patch", "cover"))
    height = np.diff(mesh.z_lines_m)[mesh.cell[:, 1]]
    patch = np.bincount(mesh.cell[rows, 0], weights=(stress * height)[rows], minlength=len(mesh.r_lines_m) - 1)
    stations = (mesh.r_lines_m[:-1] + mesh.r_lines_m[1:]) / 2
    for middle in (6.25, 18.75, 31.25, 43.75, 56.25):
        ours, want = np.interp(middle * MM, stations, patch), np.interp(middle * MM, theirs.stations_m, theirs.patch_force)
        assert abs(ours - want) < 0.003 * load, middle
    assert abs(np.interp(6.25 * MM, stations, patch) / load - 0.534) < 0.005  # over the floor the patch carries a little over half the load


# ---------------------------------------------------------------- the example repair followed until its bond lets go


def test_the_example_repairs_bond_softens_over_a_third_of_its_length_and_then_lets_go(example):
    """The mesh study behind the numbers is in ADR-0137: over eight meshes the load at which the bond lets go stays within
    0.3 % and the load of first softening settles within 0.5 % from a quarter of the bondline's thickness beside each edge."""
    answer = example
    assert answer.ended == "let_go" and answer.let_go is not None
    assert answer.onset.load / PER_MM == pytest.approx(184.0, abs=1.5)
    stretch = answer.stretch_of(answer.onset_pair)
    # the first point to soften is the outer end of the second step's ledge, in shear, the bond pressed together there
    assert stretch.name == "Adhesive on the ledge of step 2" and answer.built.pair_r_m[answer.onset_pair] / MM == pytest.approx(37.4, abs=0.05)
    assert abs(answer.onset.shear_pa[answer.onset_pair]) == pytest.approx(30e6, rel=1e-6) and answer.onset.peel_pa[answer.onset_pair] < 0
    assert answer.let_go.load / PER_MM == pytest.approx(1340.0, abs=7.0)
    assert answer.let_go.load > 7 * answer.onset.load  # first softening is far below the load the bond takes
    assert answer.softening_m(answer.let_go) / MM == pytest.approx(18.7, abs=0.6) and answer.parted_m(answer.let_go) == 0.0
    assert answer.softening_m(answer.onset) == 0.0 and answer.onset.spent == 0.0 and answer.let_go.spent > 0
    assert answer.largest.load == answer.let_go.load and answer.last.load < (1 - LET_GO_FALL) * answer.let_go.load
    # nowhere is the bond over its strengths
    for state in (answer.onset, answer.let_go, answer.last):
        over = (np.maximum(state.peel_pa, 0) / 40e6) ** 2 + (state.shear_pa / 30e6) ** 2
        assert over.max() < 1 + 1e-6
    assert answer.far_field_error < 1e-6 and answer.equilibrium_error < 1e-8
    assert answer.loads[0] == 0.0 and answer.end_movements_m[0] == 0.0 and len(answer.loads) == len(answer.path.points) + 1
    # up to the onset the end moves in proportion to the load
    assert answer.end_movements_m[1] / answer.loads[1] == pytest.approx(answer.onset.end_movement_m / answer.onset.load, rel=1e-9)


def test_a_coarser_mesh_gives_the_same_loads(example):
    coarse = run_bond(stated()[0], fine_m=0.1 * MM)  # the bondline's thickness beside each edge, four times the usual
    assert len(coarse.built.model.weight) < 0.8 * len(example.built.model.weight)
    assert coarse.let_go.load == pytest.approx(example.let_go.load, rel=0.005)
    assert coarse.onset.load == pytest.approx(example.onset.load, rel=0.04)
    assert coarse.softening_m(coarse.let_go) == pytest.approx(example.softening_m(example.let_go), rel=0.05)


def test_the_report_is_in_the_files_units_and_says_what_the_load_is_not(example):
    report = bond_report(example, "mm-MPa")
    json.dumps(report)  # plain numbers and words only
    assert report["units"] == {"length": "mm", "stress": "MPa", "force": "N/mm", "energy": "N/mm", "stiffness": "MPa/mm"}
    assert report["law"]["shear_stiffness"] == pytest.approx(1e4) and report["law"]["peel_energy"] == pytest.approx(0.5)
    assert report["law"]["final_slip"] == pytest.approx(0.1333, rel=1e-3) and report["law"]["onset_slip"] == pytest.approx(0.003)
    assert report["model"]["pairs"] == len(example.built.model.weight) and report["model"]["bond_length"] == pytest.approx(62.1)
    assert report["onset"]["part"] == "Adhesive on the ledge of step 2" and report["onset"]["step"] == 2 and abs(report["onset"]["shear"]) == pytest.approx(30.0)
    assert report["let_go"]["load"] == pytest.approx(example.let_go.load / PER_MM) and report["let_go"]["parted_length"] == 0.0
    lines = report["let_go"]["lines"]
    assert [line["name"] for line in lines] == [stretch.name for stretch in example.built.stretches]
    assert sum(line["softening_length"] for line in lines) == pytest.approx(report["let_go"]["softening_length"])
    assert all(len(line["r"]) == len(line["shear"]) == len(line["peel"]) == len(line["damage"]) for line in lines)
    assert report["curve"]["load"][0] == 0.0 and max(report["curve"]["load"]) == pytest.approx(report["let_go"]["load"])
    assert report["ended"] == "let_go" and report["last"]["most_damaged"]["damage"] > 0.9
    line = headline(report)
    assert line.startswith("The bond first softens at 184") and "in this model it lets go at 13" in line
    assert line.endswith("Not the repair's strength: the plies are not checked for damage")
    inch = bond_report(example, "psi")
    assert inch["let_go"]["load"] == pytest.approx(report["let_go"]["load"] / 0.175126835, rel=1e-6) and inch["units"]["energy"] == "lb/in"
    with pytest.raises(BondRunError, match="units must be one of"):
        bond_report(example, "furlongs")


def test_a_path_that_ends_before_the_load_falls_says_so():
    built = build_bond_model(stated()[0], fine_m=0.1 * MM)
    path, seconds = follow_bond(built, steps=3)
    answer = bond_answer(built, path, seconds)
    assert answer.let_go is None and answer.ended == "steps" and answer.largest.load == path.peak.load
    line = headline(bond_report(answer, "mm-MPa"))
    assert "lets go" not in line.split(";")[0] and "the largest load reached is" in line and "the run's limit of steps came first" in line


@pytest.mark.parametrize("path, softens_at, lets_go", [(STRIP, 162.5, 602.5), (THROUGH, 47.7, 306.3)], ids=["external", "through"])
def test_the_other_kinds_of_repair_are_followed_too(path, softens_at, lets_go):
    """A strip patch bonded on top over a hole, whose bond parts first at the hole's edge, and a flush patch through every
    ply. The loads are this model's own, kept so that a change to it shows."""
    answer = run_bond(stated(path, **SOLVE, **BOND)[0])
    assert answer.ended == "let_go"
    assert answer.onset.load / PER_MM == pytest.approx(softens_at, rel=0.01) and answer.let_go.load / PER_MM == pytest.approx(lets_go, rel=0.01)
    assert answer.equilibrium_error < 1e-8


# ---------------------------------------------------------------- the command line


def test_the_command_follows_a_repair_file_and_keeps_the_report(tmp_path, capsys):
    source = tmp_path / "repair.json"
    source.write_text(json.dumps(table()), encoding="utf-8")
    assert main([str(source), "--fine", "0.1", "--out", str(tmp_path / "out")]) == 0
    printed = capsys.readouterr().out
    assert "Example stepped patch repair" in printed and "pairs along 62.1 mm of bond" in printed
    assert "in this model it lets go at 13" in printed and "Not the repair's strength" in printed
    assert "Adhesive on the ledge of step 2" in printed and "When the run stops" in printed
    report = json.loads((tmp_path / "out" / REPORT).read_text(encoding="utf-8"))
    assert report["headline"].startswith("The bond first softens at") and report["let_go"]["load"] == pytest.approx(1340.0, abs=10.0)


def test_the_command_refuses_a_repair_without_the_bonds_numbers(tmp_path, capsys):
    source = tmp_path / "repair.json"
    source.write_text(json.dumps(table(**{"adhesive.peel_energy": None})), encoding="utf-8")
    assert main([str(source)]) == 2
    assert capsys.readouterr().out.strip() == "refused: To follow the bond until it lets go the repair needs the bond's fracture energy in peel"
