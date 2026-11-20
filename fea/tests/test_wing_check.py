"""A wing's finite element check as a job runs it (ADR-0119): the tool's progress, outcome and report, the report's numbers against
the hand calculation's own report and the model's, and its units. One coarse solve serves every test; the tests that solve skip
with a reason when Gmsh or CalculiX is missing."""

import json
import tomllib
from pathlib import Path

import pytest

from anisotropy_engine.units import FOOT, INCH, LBF, POUND_MASS
from anisotropy_engine.wing import analyze_wing, wing_from_dict
from anisotropy_engine.wing.wing_file import SPEED_UNITS, wing_report
from anisotropy_fea.calculix import find_ccx
from anisotropy_fea.mesher import gmsh_available
from anisotropy_fea.wing_check import OUTPUT_KEY, REPORT, STAGES, Unchecked, check_report, main, solve_check

EXAMPLE = Path(__file__).parents[2] / "engine" / "examples" / "example-wing.toml"
COARSE_MM = 60.0  # as test_wing_model.py: coarse enough for every change's test run
needs_both = pytest.mark.skipif(gmsh_available() is None or find_ccx() is None,
                                reason="Gmsh and CalculiX are both needed: from fea/ run `uv sync --extra mesh`, and put ccx on PATH")


def example() -> dict:
    return tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """The tool run as a job runs it, on the example's description written as JSON."""
    if gmsh_available() is None or find_ccx() is None:
        pytest.skip("Gmsh and CalculiX are both needed")
    folder = tmp_path_factory.mktemp("wing-check")
    (folder / "wing.json").write_text(json.dumps(example()), encoding="utf-8")
    status = main([str(folder / "wing.json"), "--out", str(folder / "out"), "--result", str(folder / "outcome.json"),
                   "--progress", str(folder / "progress.json"), "--mesh", str(COARSE_MM)])
    return status, folder


@pytest.fixture(scope="module")
def solved():
    if gmsh_available() is None or find_ccx() is None:
        pytest.skip("Gmsh and CalculiX are both needed")
    return solve_check(*wing_from_dict(example()), element_size_m=COARSE_MM * 1e-3)


@needs_both
def test_the_tool_ends_done_with_its_report_and_every_stage_behind_it(run):
    status, folder = run
    outcome = json.loads((folder / "outcome.json").read_text(encoding="utf-8"))
    progress = json.loads((folder / "progress.json").read_text(encoding="utf-8"))
    assert status == 0 and outcome["status"] == "done" and outcome["coupon"] is None and outcome["attempt"] is None
    assert outcome["outputs"] == {OUTPUT_KEY: str((folder / "out" / REPORT).resolve())}
    assert progress["stage"] is None and progress["done"] == list(STAGES) and progress["stages"] == list(STAGES)
    assert set(progress["timings"]) == {f"{stage}_s" for stage in STAGES}
    report = json.loads((folder / "out" / REPORT).read_text(encoding="utf-8"))
    assert outcome["message"].startswith(f"Lowest margin outboard of the root {report['lowest']['margin_ultimate']:+.3f} by the finite element model")


@needs_both
def test_the_hand_columns_are_the_hand_calculations_own_report(solved):
    report = check_report(solved, "SI", "m/s")
    hand = wing_report(analyze_wing(*wing_from_dict(example())), "SI", "m/s")
    assert [(row["number"], row["altitude"]) for row in report["cases"]] == [(c["number"], c["altitude"]) for c in hand["cases"]]
    for row, case in zip(report["cases"], hand["cases"]):
        assert row["tip_deflection"]["hand"] == pytest.approx(case["tip_deflection"], rel=1e-12)
        assert row["tip_twist"]["hand"] == pytest.approx(case["tip_twist"], rel=1e-12)
        root = min(case["checks"][name]["margin_ultimate"] for name in ("skin plies", "spar plies"))
        assert row["root"]["hand"] == pytest.approx(root, rel=1e-12), "the hand calculation's root is its plies' lowest margin"
        assert row["skin"]["hand"] >= case["checks"]["skin plies"]["margin_ultimate"] - 1e-12, "outboard of the root zone, never lower than anywhere"
    assert report["beam"]["shear_center"]["hand"] == pytest.approx(hand["design"]["shear_center"], rel=1e-12)
    assert report["beam"]["torsion_stiffness"]["hand"] == pytest.approx(hand["design"]["torsion_stiffness"], rel=1e-12)


@needs_both
def test_the_lowest_margins_are_the_lowest_of_the_cases_columns(solved):
    report = check_report(solved, "SI", "m/s")
    fe = min(min(v for v in (row["skin"]["fe"], row["spar"]["fe"], row["rib"], row["core"]) if v is not None) for row in report["cases"])
    hand = min(min(row["skin"]["hand"], row["spar"]["hand"]) for row in report["cases"])
    assert report["lowest"]["margin_ultimate"] == pytest.approx(fe, rel=1e-12)
    assert report["lowest_hand"]["margin_ultimate"] == pytest.approx(hand, rel=1e-12)
    assert report["lowest_root"]["margin_ultimate"] == pytest.approx(min(row["root"]["fe"] for row in report["cases"]), rel=1e-12)
    assert report["lowest"]["station"] >= report["root_zone"] * 0.5, "read outboard of the root zone (an element's centre past its edge)"


@needs_both
def test_the_model_agrees_with_the_hand_calculation_on_the_example(solved):
    """ADR-0117's comparison at the coarse mesh: the box of the model and the hand calculation's thin-walled cell are one wing."""
    report = check_report(solved, "SI", "m/s")
    for row in report["cases"]:
        hand, fe = row["tip_deflection"]["hand"], row["tip_deflection"]["fe"]
        assert abs(fe - hand) <= 0.05 * abs(hand) + 0.5, f"case {row['number']}: tip {fe:.1f} mm against {hand:.1f} mm"
    assert abs(report["lowest"]["margin_ultimate"] - report["lowest_hand"]["margin_ultimate"]) < 0.05
    assert report["beam"]["first_bending_frequency"]["fe"] == pytest.approx(report["beam"]["first_bending_frequency"]["hand"], rel=0.05)
    assert report["flutter"]["altitudes"] and all(a["times_required"] > 1 for a in report["flutter"]["altitudes"])
    assert {b["part"] for b in report["buckling"]} <= {"Upper skin", "Lower skin", "Front spar", "Rear spar"} and report["buckling"]


@needs_both
def test_the_report_is_in_the_files_units_and_its_margins_have_none(solved):
    si, us = check_report(solved, "SI", "m/s"), check_report(solved, "US", "kt")
    assert si["units"]["deflection"] == "mm" and us["units"]["deflection"] == "in" and us["units"]["mass_per_length"] == "lb/in"
    assert us["lowest"] == {**si["lowest"], "altitude": si["lowest"]["altitude"] / FOOT, "station": pytest.approx(si["lowest"]["station"] / INCH),
                            "chord": pytest.approx(si["lowest"]["chord"] / INCH)}
    one, other = si["cases"][5], us["cases"][5]
    assert other["tip_deflection"]["fe"] == pytest.approx(one["tip_deflection"]["fe"] * 1e-3 / INCH)
    assert other["skin"] == one["skin"] and other["tip_twist"] == one["tip_twist"]
    assert us["beam"]["torsion_stiffness"]["fe"] == pytest.approx(si["beam"]["torsion_stiffness"]["fe"] / (LBF * INCH**2))
    assert us["beam"]["mass_per_length"] == pytest.approx(si["beam"]["mass_per_length"] / (POUND_MASS / INCH))
    assert us["model"]["element_size"] == pytest.approx(COARSE_MM * 1e-3 / INCH)
    assert us["divergence_speed"]["fe"] == pytest.approx(si["divergence_speed"]["fe"] / SPEED_UNITS["kt"])
    assert us["flutter"]["required"] == pytest.approx(si["flutter"]["required"] / SPEED_UNITS["kt"])
    with pytest.raises(Unchecked, match="units must be one of"):
        check_report(solved, "imperial", "kt")


def test_a_description_the_engine_refuses_ends_refused_with_its_reason(tmp_path):
    (tmp_path / "wing.json").write_text(json.dumps({**example(), "units": "imperial"}), encoding="utf-8")
    status = main([str(tmp_path / "wing.json"), "--out", str(tmp_path / "out"), "--result", str(tmp_path / "outcome.json"),
                   "--progress", str(tmp_path / "progress.json")])
    outcome = json.loads((tmp_path / "outcome.json").read_text(encoding="utf-8"))
    assert status == 2 and outcome["status"] == "refused" and outcome["message"].startswith("units must be one of") and outcome["outputs"] == {}
    assert json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))["done"] == []


def test_a_wing_with_no_case_to_run_is_refused_before_any_model_is_built(tmp_path):
    data = example()
    data["envelope"]["speeds"] = {}  # every speed left out: every case waits for one
    wing, envelope = wing_from_dict(data)
    assert not analyze_wing(wing, envelope).cases
    with pytest.raises(Unchecked, match="No flight case can be checked"):
        solve_check(wing, envelope)


def test_a_wing_the_model_cannot_describe_is_refused_in_the_models_words():
    data = example()
    data.pop("rib")  # ribs at every 0.5 m and no layup for them: the hand calculation works it, the model cannot
    with pytest.raises(Unchecked, match="The wing has ribs but no rib layup"):
        solve_check(*wing_from_dict(data))


@needs_both
def test_the_browser_tests_check_has_the_shape_the_tool_writes(solved):
    """tests/fixtures/wing/example-check.json is this tool's report of the example at 40 mm, which the page's tests play back."""
    fixture = json.loads((Path(__file__).parents[2] / "tests" / "fixtures" / "wing" / "example-check.json").read_text(encoding="utf-8"))

    def shape(value):
        if isinstance(value, dict):
            return {key: shape(item) for key, item in value.items()}
        if isinstance(value, list):
            return [shape(value[0])] if value else []
        return "value"
    assert shape(fixture) == shape(check_report(solved, "SI", "m/s"))
    assert fixture["wing"] == "Example straight wing" and fixture["model"]["element_size"] == 40.0 and len(fixture["cases"]) == 34
