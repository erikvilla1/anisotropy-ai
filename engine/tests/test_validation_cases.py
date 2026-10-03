"""Runs every case in engine/validation/cases against the engine.

Each case states its inputs and the answers from an independent source (a textbook, an
answer key, later lab measurements). A case fails when the engine and the source disagree
by more than the case's tolerance. See engine/validation/README.md.
"""

from pathlib import Path

import pytest

from anisotropy_engine.cases import compare, disagreements, load_case

CASE_DIR = Path(__file__).parents[1] / "validation" / "cases"
CASES = sorted(path for path in CASE_DIR.glob("*.toml") if not path.name.startswith("_"))


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_engine_reproduces_the_case(path):
    case = load_case(path)
    for field in ("title", "source", "units"):
        assert field in case, f"{path.name} is missing {field}"
    problems = disagreements(case)
    assert not problems, f"{case['title']}\nSource: {case['source']}\n" + "\n".join(problems)


def test_a_wrong_expected_value_is_reported():
    # Guards the runner itself: a deliberately wrong answer must not pass.
    case = load_case(CASE_DIR / "daniel-ishai-problem-7-11.toml")
    case["expected"]["A11"] = 61.0
    assert disagreements(case) == ["A11: expected 61, engine gives 60.2447"]


def test_an_unknown_result_key_is_reported():
    case = load_case(CASE_DIR / "daniel-ishai-problem-7-11.toml")
    case["expected"]["A99"] = 1.0
    assert disagreements(case)[0].startswith("A99: not a result this case can produce")


def test_vector_results_are_compared_value_by_value():
    comparisons, problems = compare(load_case(CASE_DIR / "homework-lamina-20deg-plane-stress.toml"))
    assert not problems
    assert [c.key for c in comparisons[:3]] == ["strain_global[0]", "strain_global[1]", "strain_global[2]"]
    assert len(comparisons) == 9
    assert all(c.agrees for c in comparisons)


def test_a_case_with_two_applied_entries_is_rejected():
    case = load_case(CASE_DIR / "daniel-ishai-problem-7-11.toml")
    case["applied"]["stress"] = [1.0, 0, 0]
    with pytest.raises(ValueError, match="exactly one"):
        disagreements(case)
