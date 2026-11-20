"""The stepped lap hand calculation (ADR-0130): every case in validation/repair_cases against the engine, its expected numbers
against the closed form worked without the engine in validation/closed_forms.py (ADR-0007, ADR-0042), and the properties
the model must have whatever the numbers."""

import importlib.util
import math
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.repair import (
    Adhesive, Step, double_lap_strength, elastic_limit_load, lap_from_dict, lap_report, long_overlap_strength, step_lap,
)
from anisotropy_engine.units import UNIT_SYSTEMS

ENGINE = Path(__file__).parents[1]
VALIDATION = ENGINE / "validation"
CASES = sorted((VALIDATION / "repair_cases").glob("*.toml"))
# Course examples and the team's own joints, with their answers, stay outside the repository (ADR-0042): same format, run when present.
LOCAL = sorted((ENGINE.parent / ".local" / "repair" / "cases").glob("*.toml"))
INPUTS = ("units", "adhesive", "steps", "applied")
FILM = Adhesive(shear_modulus_pa=800e6, thickness_m=0.15e-3, shear_strength_pa=35e6)


def closed_forms():
    spec = importlib.util.spec_from_file_location("closed_forms", VALIDATION / "closed_forms.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def flat(value) -> list[float]:
    return [float(v) for v in np.ravel(value)]


def answers(case: dict) -> dict:
    """What the engine says of a case, under the keys an `[expected]` table uses."""
    lap = lap_from_dict({key: case[key] for key in INPUTS})
    report = lap_report(lap, case["units"])
    report["peak_shear"] = report["peak_shear"]["value"]
    if "double_lap" in case:
        system = UNIT_SYSTEMS[case["units"]]
        joint = case["double_lap"]
        stiffness = lambda side: joint[f"{side}_modulus"] * system["modulus"][0] * joint[f"{side}_thickness"] * system["length"][0]  # noqa: E731
        report["double_lap_strength"] = double_lap_strength(stiffness("inner"), stiffness("outer"), lap.adhesive) / system["N"][0]
    return report


def uniform(length_m: float, pieces: int = 1) -> list[Step]:
    """A 1 mm patch of 48 GPa on a 2 mm laminate of 55 GPa, in equal pieces."""
    return [Step(length_m / pieces, 1.0e-3, 48e9, 2.0e-3, 55e9) for _ in range(pieces)]


def test_there_are_cases_and_each_has_its_closed_form():
    assert len(CASES) >= 2
    assert {path.stem for path in CASES} == set(closed_forms().LAP_CASES)


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_every_expected_value_is_the_closed_form(path):
    case = load(path)
    reference = closed_forms().LAP_CASES[path.stem](case)
    expected = {key: value for key, value in case["expected"].items() if key != "tolerance"}
    assert set(expected) == set(reference)
    for key, value in expected.items():
        assert flat(value) == pytest.approx(flat(reference[key]), rel=1e-9, abs=1e-12), f"{path.stem}: {key}"


@pytest.mark.parametrize("path", CASES + LOCAL, ids=[path.stem for path in CASES + LOCAL])
def test_the_engine_reproduces_the_case(path):
    case = load(path)
    for field in ("title", "source", "units"):
        assert field in case
    got = answers(case)
    tolerance = case["expected"]["tolerance"]
    count = 0
    for key, value in case["expected"].items():
        if key == "tolerance":
            continue
        assert flat(got[key]) == pytest.approx(flat(value), rel=tolerance, abs=1e-9), f"{path.stem}: {key}"
        count += len(flat(value))
    assert count >= (2 if path in LOCAL else 4)  # a private case states only what its source prints


def test_the_shear_stress_adds_up_to_the_load_and_is_the_slope_of_the_patch_force():
    steps = [Step(12e-3, 0.5e-3 * k, 48e9, 2.0e-3 - 0.5e-3 * k, 55e9) for k in (1, 2, 3)]
    lap = step_lap(steps, FILM, 300e3)
    x, tau, force = lap.distribution(4001)
    assert np.trapezoid(tau, x) == pytest.approx(300e3, rel=1e-6)  # the adhesive hands the whole load to the patch
    assert force[0] == 0 and force[-1] == pytest.approx(300e3, rel=1e-12)
    assert np.all(np.diff(x) >= 0) and x[-1] == pytest.approx(36e-3)
    for k, step in enumerate(steps):  # tau = dN/dx, by a central difference inside every step
        for at in (-0.3, 0.0, 0.42):
            here, h = at * step.length_m, 1e-7
            slope = (lap.outer_force(k, here + h) - lap.outer_force(k, here - h)) / (2 * h)
            assert lap.shear(k, here) == pytest.approx(slope, rel=1e-6)
    # the shear stress is continuous from one step to the next, which is the equation the boundary forces solve
    ends = lap.shear_at_ends
    assert ends[0, 1] == pytest.approx(ends[1, 0], rel=1e-12) and ends[1, 1] == pytest.approx(ends[2, 0], rel=1e-12)
    # and the largest one is at an end of a step, never inside
    value, k, end = lap.peak_shear
    assert abs(value) == pytest.approx(np.abs(tau).max(), rel=1e-12) and (k, end) == (2, "end")


def test_one_step_is_volkersens_solution_for_unlike_adherends():
    step, load_ = Step(25e-3, 1.6e-3, 70e9, 3.2e-3, 110e9), 250e3
    lap = step_lap([step], FILM, load_)
    so, si, c = step.outer_stiffness, step.inner_stiffness, step.length_m / 2
    lam = math.sqrt(FILM.shear_modulus_pa / FILM.thickness_m * (1 / so + 1 / si))
    for x in np.linspace(-c, c, 9):  # Volkersen (1938), x from the middle of the overlap
        tau = load_ * lam / 2 * (math.cosh(lam * x) / math.sinh(lam * c) + (si - so) / (si + so) * math.sinh(lam * x) / math.cosh(lam * c))
        assert lap.shear(0, x) == pytest.approx(tau, rel=1e-10)
    # the larger shear stress is at the end where the stiffer adherend stops and the softer one carries everything
    assert lap.peak_shear[2] == "end" and si > so


def test_cutting_a_uniform_step_in_pieces_changes_nothing():
    whole, pieces = step_lap(uniform(30e-3), FILM, 200e3), step_lap(uniform(30e-3, 5), FILM, 200e3)
    assert pieces.peak_shear[0] == pytest.approx(whole.peak_shear[0], rel=1e-10)
    for k in range(5):  # the patch force at every cut is the whole step's force there
        assert pieces.forces[k + 1] == pytest.approx(whole.outer_force(0, -15e-3 + 6e-3 * (k + 1)), rel=1e-9)
    assert elastic_limit_load(pieces) == pytest.approx(elastic_limit_load(whole), rel=1e-10)


def test_a_lap_between_matching_adherends_is_the_same_from_both_ends():
    steps = [Step(10e-3, 0.5e-3 * k, 55e9, 2.0e-3 - 0.5e-3 * k, 55e9) for k in (1, 2, 3)]  # the patch grows as the laminate thins
    ends = step_lap(steps, FILM, 100e3).shear_at_ends
    assert ends[::-1, ::-1] == pytest.approx(ends, rel=1e-10)


def test_the_answer_is_linear_in_the_load_and_a_push_reverses_it():
    steps = uniform(20e-3, 2)
    pull, more, push = (step_lap(steps, FILM, load_) for load_ in (100e3, 250e3, -100e3))
    assert more.shear_at_ends == pytest.approx(2.5 * pull.shear_at_ends, rel=1e-12)
    assert push.shear_at_ends == pytest.approx(-pull.shear_at_ends, rel=1e-12)
    assert push.adherend_stresses() == pytest.approx(-pull.adherend_stresses(), rel=1e-12)
    assert elastic_limit_load(pull) == pytest.approx(elastic_limit_load(more), rel=1e-12) == pytest.approx(elastic_limit_load(push), rel=1e-12)
    assert step_lap(steps, FILM, 0.0).shear_at_ends == pytest.approx(0.0, abs=0.0)


def test_a_long_step_neither_overflows_nor_loads_its_middle():
    lap = step_lap(uniform(2.0), FILM, 200e3)  # 2 m long: lambda times the length is in the hundreds
    lam = math.sqrt(FILM.shear_modulus_pa / FILM.thickness_m * (1 / (48e9 * 1e-3) + 1 / (55e9 * 2e-3)))
    assert lam * 2.0 > 500
    assert lap.shear(0, 0.0) == pytest.approx(0.0, abs=1e-6)
    assert lap.outer_force(0, 0.0) == pytest.approx(200e3 * 48e6 / (48e6 + 110e6), rel=1e-12)  # each adherend carries its share of stiffness
    assert math.isfinite(lap.peak_shear[0])
    # with the overlap long, the elastic limit is the closed form of a long overlap with no plastic strain
    assert elastic_limit_load(lap) == pytest.approx(long_overlap_strength(48e6, 110e6, FILM), rel=1e-12)


def test_a_stretching_adherend_is_most_stressed_where_its_force_turns():
    # a short stiff first step ahead of a soft thick one: the patch's force overshoots inside the first step
    lap = step_lap([Step(30e-3, 2.0e-3, 70e9, 1.0e-3, 70e9), Step(30e-3, 0.4e-3, 70e9, 1.0e-3, 70e9)], FILM, 100e3)
    assert lap.forces[1] < lap.forces[2]
    start, end = lap.shear_at_ends[0]
    assert start > 0 > end  # the shear stress changes sign in the first step
    x, _, force = lap.distribution(20001)
    inside = force[:20001].max()
    assert inside > lap.forces[1]
    assert lap.adherend_stresses()[0, 0] == pytest.approx(inside / 2.0e-3, rel=1e-7)


def test_a_ductile_adhesive_long_overlap_strength_is_hart_smiths_and_the_separatrix_of_the_yielding_bond():
    glue = Adhesive(shear_modulus_pa=600e6, thickness_m=0.2e-3, shear_strength_pa=30e6, plastic_strain=0.4)
    # balanced double lap (the inner adherend as stiff as the two outer ones together): 4 sqrt(eta W E t) of one outer adherend
    outer = 70e9 * 1.5e-3
    assert double_lap_strength(2 * outer, outer, glue) == pytest.approx(4 * math.sqrt(glue.thickness_m * glue.strain_energy * outer), rel=1e-12)
    assert glue.strain_energy == pytest.approx(30e6 * (0.05 / 2 + 0.4))
    # unlike adherends: the end where the softer adherend carries everything governs, and plastic strain raises the strength
    sa, sb = 70e9 * 1.0e-3, 70e9 * 3.0e-3
    strength = long_overlap_strength(sa, sb, glue)
    assert strength == pytest.approx(long_overlap_strength(sb, sa, glue), rel=1e-15)
    assert strength == pytest.approx(math.sqrt(2 * glue.thickness_m * glue.strain_energy * sa * (1 + sa / sb)), rel=1e-12)
    brittle = Adhesive(600e6, 0.2e-3, 30e6)
    assert strength / long_overlap_strength(sa, sb, brittle) == pytest.approx(math.sqrt(1 + 2 * 0.4 / 0.05), rel=1e-12)

    def outcome(load_: float) -> str:
        """March the yielding bond's equation inward from the governing end with the adhesive at its failure strain there:
        below the strength the strain stops falling before it reaches zero, above it the strain runs through zero."""
        k = (1 / sa + 1 / sb) / glue.thickness_m
        tau = lambda y: max(-30e6, min(30e6, 600e6 * y))  # noqa: E731
        y, v = glue.elastic_strain + glue.plastic_strain, -load_ / (glue.thickness_m * sa)
        h = 1 / (400 * math.sqrt(k * 600e6))
        for _ in range(40000):
            k1y, k1v = v, k * tau(y)
            k2y, k2v = v + h / 2 * k1v, k * tau(y + h / 2 * k1y)
            k3y, k3v = v + h / 2 * k2v, k * tau(y + h / 2 * k2y)
            k4y, k4v = v + h * k3v, k * tau(y + h * k3y)
            y, v = y + h / 6 * (k1y + 2 * k2y + 2 * k3y + k4y), v + h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
            if v >= 0:
                return "holds"
            if y <= 0:
                return "fails"
        return "undecided"

    assert outcome(0.999 * strength) == "holds" and outcome(1.001 * strength) == "fails"


def test_what_is_not_a_lap_is_refused_in_words():
    good = {"length_m": 10e-3, "outer_thickness_m": 1e-3, "outer_modulus_pa": 50e9, "inner_thickness_m": 2e-3, "inner_modulus_pa": 50e9}
    for key in good:
        for bad in (0.0, -1.0, math.nan, math.inf, True):
            with pytest.raises(ValueError, match="A step's"):
                Step(**{**good, key: bad})
    with pytest.raises(ValueError, match="shear modulus"):
        Adhesive(0.0, 0.1e-3)
    with pytest.raises(ValueError, match="plastic shear strain"):
        Adhesive(800e6, 0.1e-3, 30e6, -0.1)
    with pytest.raises(ValueError, match="at least one step"):
        step_lap([], FILM, 1.0)
    with pytest.raises(ValueError, match="finite"):
        step_lap(uniform(10e-3), FILM, math.nan)
    with pytest.raises(ValueError, match="no shear strength"):
        elastic_limit_load(step_lap(uniform(10e-3), Adhesive(800e6, 0.15e-3), 1e3))
    with pytest.raises(ValueError, match="No load"):
        elastic_limit_load(step_lap(uniform(10e-3), FILM, 0.0))
    case = load(CASES[0])
    stated = {key: case[key] for key in INPUTS}
    with pytest.raises(ValueError, match="units must be one of"):
        lap_from_dict({**stated, "units": "furlongs"})
    with pytest.raises(ValueError, match="does not read: colour"):
        lap_from_dict({**stated, "adhesive": {**stated["adhesive"], "colour": 1}})
    with pytest.raises(ValueError, match="Step 2 is missing: inner_modulus"):
        steps = [dict(row) for row in stated["steps"]]
        del steps[1]["inner_modulus"]
        lap_from_dict({**stated, "steps": steps})
    with pytest.raises(ValueError, match="at least one step"):
        lap_from_dict({**stated, "steps": []})
    with pytest.raises(ValueError, match="applied load is missing: load"):
        lap_from_dict({**stated, "applied": {}})


def test_the_report_is_in_the_units_asked_for():
    case = load(CASES[0])
    lap = lap_from_dict({key: case[key] for key in INPUTS})
    mm, us = lap_report(lap, "mm-MPa"), lap_report(lap, "psi")
    assert mm["units"] == {"force": "N/mm", "stress": "MPa", "length": "mm"} and us["units"]["stress"] == "psi"
    assert us["peak_shear"]["value"] == pytest.approx(mm["peak_shear"]["value"] * 1e6 / UNIT_SYSTEMS["psi"]["stress"][0])
    assert us["elastic_limit_load"] == pytest.approx(mm["elastic_limit_load"] * 1e3 / UNIT_SYSTEMS["psi"]["N"][0])
    assert mm["peak_shear"]["step"] == 3 and mm["peak_shear"]["end"] == "end"  # steps are counted from 1 for a reader
    assert us["lambda_length"] == pytest.approx(mm["lambda_length"])
