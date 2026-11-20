"""Every wing in validation/wing_cases against the engine, and its expected numbers against the closed form worked
without the engine in validation/closed_forms.py (ADR-0007, ADR-0042, ADR-0115)."""

import importlib.util
import tomllib
from pathlib import Path

import pytest

from anisotropy_engine.wing import analyze_wing, wing_from_dict, wing_report

VALIDATION = Path(__file__).parents[1] / "validation"
CASES = sorted((VALIDATION / "wing_cases").glob("*.toml"))
CHECKS = {"skin_plies": "skin plies", "spar_plies": "spar plies", "skin_buckling": "skin buckling"}


def closed_forms():
    spec = importlib.util.spec_from_file_location("closed_forms", VALIDATION / "closed_forms.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def expected_values(case: dict):
    """(where, key, value) for every expected number of a wing case."""
    for key, value in case["expected"]["design"].items():
        yield "design", key, value
    for number, values in case["expected"]["cases"].items():
        for key, value in values.items():
            yield number, key, value


def test_there_is_a_wing_case_and_each_has_its_closed_form():
    assert CASES
    assert {path.stem for path in CASES} == set(closed_forms().WING_CASES)


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_every_expected_value_is_the_closed_form(path):
    case = load(path)
    reference = closed_forms().WING_CASES[path.stem](case)
    count = 0
    for where, key, value in expected_values(case):
        want = reference["design"][key] if where == "design" else reference["cases"][where][key]
        assert value == pytest.approx(want, rel=1e-9), f"{path.stem}: {where} {key}"
        count += 1
    assert count >= 20


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_engine_reproduces_the_wing_case(path):
    case = load(path)
    for field in ("title", "source", "units"):
        assert field in case
    wing, envelope = wing_from_dict({key: value for key, value in case.items() if key not in ("stations", "expected")})
    report = wing_report(analyze_wing(wing, envelope, stations=case["stations"]), case["units"], case["envelope"]["speed_unit"])
    (altitude,) = case["envelope"]["altitudes"]
    by_number = {str(c["number"]): c for c in report["cases"] if c["altitude"] == altitude}
    problems = []
    for where, key, value in expected_values(case):
        if where == "design":
            got = report["design"][key]
        elif key in CHECKS:
            got = by_number[where]["checks"][CHECKS[key]]["strength_ratio"]
        else:
            got = by_number[where][key]
        if got != pytest.approx(value, rel=case["expected"]["tolerance"]):
            problems.append(f"{where} {key}: expected {value:.8g}, engine gives {got:.8g}")
    assert not problems, f"{case['title']}\nSource: {case['source']}\n" + "\n".join(problems)


def test_a_wrong_expected_value_would_be_caught():
    case = load(CASES[0])
    reference = closed_forms().WING_CASES[CASES[0].stem](case)
    assert case["expected"]["design"]["bending_stiffness"] * 1.001 != pytest.approx(reference["design"]["bending_stiffness"], rel=1e-9)
