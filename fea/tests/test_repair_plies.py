"""A repair carried until its plies and its bond cannot hold the load (ADR-0141): the element a crack can soften in, what
the run refuses, the answer's own check, and the same run with the plies kept whole, which must give ADR-0140's loads."""

from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path

import numpy as np
import pytest
from anisotropy_engine.repair.repair_file import repair_from_dict
from anisotropy_engine.repair.solid import ply_compliance
from anisotropy_fea.bond_solver import BondModel
from anisotropy_fea.ply_damage import Held, Holder, PlyDamage, largest_load
from anisotropy_fea.repair_bond import build_bond_model, run_bond
from anisotropy_fea.repair_plies import (
    MESH_STEP,
    OUTPUT_KEY,
    SHORTEN,
    STAGES,
    BondRunError,
    build_plies_model,
    headline,
    longest_element,
    main,
    plies_report,
    run_plies,
    what_failed,
)

EXTERNAL = Path(__file__).parents[2] / "engine" / "examples" / "example-external-patch-repair.toml"

# A small repair of round numbers, so that the whole run takes seconds. The fracture energies are large on purpose: a
# crack softens only in an element short enough for it (`longest_element`), and large energies allow long elements.
SMALL = {
    "title": "A small repair for the tests",
    "units": "mm-MPa",
    "parent": {
        "library": "im7-8552",
        "layup": [0, 90, 90, 0],
        "nu23": 0.45,
        "fibre_tension_energy": 400.0,
        "fibre_compression_energy": 400.0,
        "matrix_tension_energy": 3.0,
        "matrix_shear_energy": 8.0,
    },
    "damage": {"diameter": 8.0},
    "steps": {"count": 2, "length": 5.0},
    "adhesive": {"shear_modulus": 1000.0, "thickness": 0.1, "shear_strength": 30.0, "poisson": 0.35, "peel_strength": 40.0,
                 "peel_energy": 0.5, "shear_energy": 2.0},
    "panel": {"length": 80.0, "width": 60.0},
}


def small(**changes) -> dict:
    case = copy.deepcopy(SMALL)
    for table, values in changes.items():
        case[table] = {**case[table], **values} if isinstance(values, dict) else values
    return case


@pytest.fixture(scope="module")
def answer():
    repair, _ = repair_from_dict(SMALL)
    return run_plies(repair)


def test_the_longest_element_is_the_smallest_bound_of_the_four_cracks() -> None:
    """A crack softens over a band as wide as the element, and its fracture energy must be above the energy the ply holds
    when it reaches its strength, so the element is bounded by 2 G E / X^2 for each crack."""
    repair, _ = repair_from_dict(SMALL)
    lamina = repair.parent_material.lamina
    energies = repair.parent_material.energies
    bounds = {
        "fibre tension": 2 * energies.fibre_tension * lamina.E1 / lamina.strengths.F1t**2,
        "fibre compression": 2 * energies.fibre_compression * lamina.E1 / lamina.strengths.F1c**2,
        "matrix tension": 2 * energies.matrix_tension * lamina.E2 / lamina.strengths.F2t**2,
        "matrix shear": 2 * energies.matrix_shear * lamina.G12 / lamina.strengths.F6**2,
    }
    assert longest_element(repair) == pytest.approx(min(bounds.values()), rel=1e-12)
    assert min(bounds, key=bounds.get) == "matrix shear"  # here the crack slid along the fibres needs the shortest element


def test_the_run_shortens_its_elements_to_what_a_crack_can_soften_in() -> None:
    repair, _ = repair_from_dict(SMALL)
    allowed = SHORTEN * longest_element(repair)
    built = build_plies_model(repair, element_size_m=10 * allowed)
    assert built.element_size_m == pytest.approx(allowed, rel=1e-12)
    asked = 0.5 * allowed
    assert build_plies_model(repair, element_size_m=asked).element_size_m == pytest.approx(asked, rel=1e-12)


def test_a_repair_without_the_plies_fracture_energies_is_refused_with_the_list() -> None:
    case = small()
    for key in ("fibre_tension_energy", "fibre_compression_energy", "matrix_tension_energy", "matrix_shear_energy"):
        case["parent"].pop(key)
    repair, _ = repair_from_dict(case)
    with pytest.raises(BondRunError, match="fracture energies, all of fibre_tension_energy"):
        build_plies_model(repair)


def test_a_repair_without_the_bonds_fracture_energies_is_refused_too(tmp_path) -> None:
    case = small(adhesive={**SMALL["adhesive"]})
    case["adhesive"].pop("shear_energy")
    path = tmp_path / "repair.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    assert main([str(path)]) == 2


def test_a_panel_too_short_round_its_repair_is_refused_before_any_load_is_raised() -> None:
    """The elastic slice is held to ADR-0140's far-field check first, so a short panel costs one solve, not the run."""
    repair, _ = repair_from_dict(small(panel={"length": 34.0}))
    with pytest.raises(BondRunError, match="the panel is too short around the repair for this model; give a longer panel"):
        run_plies(repair)


def test_a_refusal_states_its_numbers_in_the_files_units() -> None:
    repair, _ = repair_from_dict(small(adhesive={"shear_energy": 0.04}))
    with pytest.raises(BondRunError, match="it must be above 0.045 N/mm"):
        build_plies_model(repair, units="mm-MPa")


def test_the_answer_holds_a_load_it_does_not_hold_and_what_failed(answer) -> None:
    assert answer.onset > 0
    assert answer.held.load > answer.onset
    assert answer.not_held > answer.held.load
    assert answer.spread == pytest.approx((answer.not_held - answer.held.load) / answer.held.load, rel=1e-12)
    assert answer.spread < 0.01
    assert answer.equilibrium_error < 1e-3  # the plies' forces add up to the load at every station
    assert any("bond" in line or "ply" in line for line in what_failed(answer))
    assert [one.load for one in answer.levels] == sorted(one.load for one in answer.levels)


def test_the_report_is_in_the_files_units_and_says_what_a_crack_can_soften_in(answer) -> None:
    report = plies_report(answer, "mm-MPa")
    assert report["units"]["system"] == "mm-MPa" and report["units"]["length"] == "mm" and report["units"]["stress"] == "MPa"
    assert report["model"]["element_size"] <= report["model"]["longest_element"]
    assert report["load"]["held"] == pytest.approx(answer.held.load / 1e3, rel=1e-12)  # N/m to N/mm
    assert report["onset"]["load"] == pytest.approx(answer.onset / 1e3, rel=1e-12)
    assert "carries" in headline(report) and "not" in headline(report)
    assert report["levels"][0]["load"] == pytest.approx(answer.onset / 1e3, rel=2e-3)


def test_the_run_prints_its_answer_and_keeps_the_report(tmp_path, capsys) -> None:
    path = tmp_path / "repair.json"
    path.write_text(json.dumps(SMALL), encoding="utf-8")
    assert main([str(path), "--out", str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert "A small repair for the tests" in printed
    assert "What had failed at" in printed
    report = json.loads((tmp_path / "repair-plies.json").read_text(encoding="utf-8"))
    assert report["headline"].startswith("The slice carries")


def test_what_failed_is_given_as_numbers_too_and_its_words_in_the_files_units(answer) -> None:
    """The page writes its own words from the numbers (ADR-0141 amendment 1); the command's words are in the file's length."""
    report = plies_report(answer, "mm-MPa")
    at = report["at_held"]
    assert at["elements"] == report["model"]["elements"] and at["bond"]["length"] == pytest.approx(report["model"]["bond_length"], rel=1e-12)
    assert at["bond"]["softening"] + at["bond"]["parted"] <= at["bond"]["length"] * (1 + 1e-12)
    assert {row["crack"] for row in at["plies"]} <= {"fibre_tension", "fibre_compression", "matrix"}
    for row in at["plies"]:
        assert 0 <= row["through"] <= row["elements"] <= at["elements"]
        assert row["worst"]["kind"] in ("parent", "patch", "cover") and 0 <= row["worst"]["r"] <= SMALL["panel"]["length"] / 2
    assert report["ended"] == "closed" and report["onset"]["crack"] in ("bond", "fibre", "matrix")
    inch = plies_report(answer, "psi")
    assert all(" mm" not in line for line in inch["failed"]) and any(" in " in line for line in inch["failed"])
    assert inch["at_held"]["bond"]["length"] == pytest.approx(at["bond"]["length"] / 25.4, rel=1e-9)
    line = headline(report)
    assert f"carries {report['load']['held']:.4g} N/mm in this model and not {report['load']['not_held']:.4g}" in line
    assert "per mm" not in line and "strength" not in line


def test_a_hold_whose_time_has_come_says_time_and_finds_nothing() -> None:
    """`Holder.hold` given a time already past ends after one solve, not held, and says "time": no finding about the load."""
    import time

    built = build_plies_model(repair_from_dict(small())[0])
    holder = Holder(built.model)
    late = holder.hold(holder.onset_load * 0.5, holder.begin(), 50, time.perf_counter() - 1.0)
    assert (late.held, late.why, late.solves) == (False, "time", 1)
    assert holder.hold(holder.onset_load * 0.5, holder.begin(), 50, time.perf_counter() + 3600.0).held


def test_a_run_out_of_its_time_answers_with_the_largest_load_it_held(answer, monkeypatch) -> None:
    """ADR-0141 amendment 1. The load being tried when the time comes is dropped. Before any load the slice does not hold was
    found, the answer is a load it holds and no more; after, the bracket as far as it was closed. Before the first softening
    was held there is nothing to answer, and the run is refused."""
    import anisotropy_fea.repair_plies as module

    def timed(limit: int):
        class Timed(Holder):
            calls = 0

            def hold(self, load, damage, solves=200, until=None):
                Timed.calls += 1
                if Timed.calls > limit:
                    return Held(load, False, damage, self.unit, 0.0, 1, "time")
                return super().hold(load, damage, solves, until)
        return Timed

    repair = repair_from_dict(small())[0]
    monkeypatch.setattr(module, "Holder", timed(2))
    early = run_plies(repair, seconds=3600.0)
    assert early.ended == "time" and early.not_held is None and early.spread is None and len(early.levels) == 2
    assert early.onset == pytest.approx(answer.onset, rel=1e-12) and answer.onset < early.held.load < answer.held.load
    report = plies_report(early, "mm-MPa")
    assert report["load"]["not_held"] is None and report["ended"] == "time"
    assert headline(report).startswith(f"The slice carries at least {report['load']['held']:.4g} N/mm in this model: the run's time came before")

    raised = sum(1 for one, after in zip(answer.levels, answer.levels[1:]) if after.load == pytest.approx(one.load * 1.15, rel=1e-9))
    monkeypatch.setattr(module, "Holder", timed(raised + 3))  # the first softening, every rise held, the one not held, one more
    later = run_plies(repair, seconds=3600.0)
    assert later.ended == "time" and later.not_held is not None and later.held.load <= answer.held.load < later.not_held
    assert later.spread > answer.spread
    assert "the run's time came before the two were brought nearer" in headline(plies_report(later, "mm-MPa"))

    monkeypatch.setattr(module, "Holder", timed(0))
    with pytest.raises(BondRunError, match="The run's time came before the slice had been carried to its first softening"):
        run_plies(repair, seconds=3600.0)


def test_a_slice_larger_than_the_run_takes_is_refused_with_what_makes_it_large() -> None:
    repair = repair_from_dict(small())[0]
    elements = len(build_plies_model(repair).model.elements)
    assert len(build_plies_model(repair, most_elements=elements).model.elements) == elements
    with pytest.raises(BondRunError, match=rf"The slice would have {elements:,} elements, and this run takes at most {elements - 1:,}\. For a crack "
                                           r"to soften in them its elements are [0-9.]+ mm long at most, over half the panel's length: shorten the panel"):
        build_plies_model(repair, units="mm-MPa", most_elements=elements - 1)
    with pytest.raises(BondRunError, match=r"The slice would have more than [0-9,]+ elements, and this run takes at most 20\."):
        build_plies_model(repair_from_dict(small(panel={"length": 80000.0, "width": 60.0}))[0], most_elements=20)


def test_as_a_job_the_run_writes_its_stage_and_its_outcome(tmp_path) -> None:
    """ADR-0141 amendment 1: with --result and --progress the command is a job, as a wing's check is (ADR-0119)."""
    path, result, progress = tmp_path / "repair.json", tmp_path / "outcome.json", tmp_path / "progress.json"
    path.write_text(json.dumps(SMALL), encoding="utf-8")
    assert main([str(path), "--out", str(tmp_path / "model"), "--result", str(result), "--progress", str(progress), "--seconds", "600", "--most"]) == 0
    outcome, last = json.loads(result.read_text(encoding="utf-8")), json.loads(progress.read_text(encoding="utf-8"))
    assert outcome["status"] == "done" and outcome["message"].startswith("The slice carries") and outcome["result"] == outcome["message"]
    report = json.loads(Path(outcome["outputs"][OUTPUT_KEY]).read_text(encoding="utf-8"))
    assert report["headline"] == outcome["message"] and report["ended"] == "closed"
    assert last == {"stage": None, "done": list(STAGES), "stages": list(STAGES), "outputs": {}, "coupon": None, "attempt": None}
    # a mesh one step finer, as the page's second run asks
    assert main([str(path), "--out", str(tmp_path / "finer"), "--finer", "1"]) == 0
    finer = json.loads((tmp_path / "finer" / "repair-plies.json").read_text(encoding="utf-8"))
    assert finer["model"]["element_size"] == pytest.approx(MESH_STEP * report["model"]["element_size"], rel=1e-9)
    assert finer["load"]["held"] == pytest.approx(report["load"]["held"], rel=0.05)
    # a repair the run refuses ends the job refused, in the run's words
    path.write_text(json.dumps(small(panel={"length": 34.0})), encoding="utf-8")
    assert main([str(path), "--out", str(tmp_path / "short"), "--result", str(result), "--progress", str(progress)]) == 2
    refused = json.loads(result.read_text(encoding="utf-8"))
    assert refused["status"] == "refused" and "the panel is too short around the repair" in refused["message"] and refused["outputs"] == {}


def test_with_the_plies_kept_whole_the_bonds_own_load_lies_in_the_bracket() -> None:
    """The strongest check of the new method. The example of a patch bonded on top over a hole, where the bond is the only
    way across the hole, so the load at which it lets go is the load the slice can no longer hold. Its own slice and bond,
    on the mesh ADR-0140's run uses, with the plies unable to damage: the load that record's path method gives must lie
    between the load this method holds and the load it does not, although the two share nothing past onset (ADR-0141,
    item 9d).

    On the flush example the two do not meet, and should not: a flush repair leaves four plies running under the patch, so
    once the bond has parted the slice still carries, and ADR-0140's load there is the peak of a path, not a collapse.
    """
    repair, _ = repair_from_dict(tomllib.loads(EXTERNAL.read_text(encoding="utf-8")))
    bond = run_bond(repair)
    built = build_bond_model(repair)
    # the same solids, stated as plies that cannot damage: their stiffness is the bond model's own and the width strain is
    # the plies' own, so this is ADR-0140's model solved the new way
    materials = [repair.parent_material if built.mesh.regions[index].kind == "parent" else repair.patch_material
                 for index in built.mesh.region]
    compliance = np.array([ply_compliance(material.lamina, material.through) for material in materials])
    angles = np.array([built.mesh.regions[index].angle_deg for index in built.mesh.region], dtype=float)
    plies = PlyDamage(compliance, angles, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                      np.zeros(len(built.model.elements), dtype=bool), built.far.strain_width)
    whole = BondModel(built.model.nodes, built.model.elements, built.model.stiffness, built.model.under, built.model.over,
                      built.model.weight, built.model.law, built.model.fixed, built.end_load, plies=plies)
    held, failed, holder = largest_load(whole, within=0.004)
    assert holder.onset_load == pytest.approx(bond.onset.load, rel=1e-6)
    assert bond.let_go is not None
    assert held[-1].load <= bond.let_go.load <= failed.load


def test_the_example_repair_carries_less_once_its_plies_may_damage(answer) -> None:
    """What slice 7 is for. For the small repair above the plies decide: the load it carries is below the load at which
    its bond alone would let go."""
    repair, _ = repair_from_dict(SMALL)
    bond = run_bond(repair, element_size_m=answer.built.element_size_m, fine_m=answer.built.built.fine_m)
    assert answer.held.load < bond.largest.load
    assert any("cracked along the fibres" in line for line in what_failed(answer))
