"""Every finite element validation case is reproduced, and the runner itself reports what it should (ADR-0007, ADR-0029)."""

from pathlib import Path

import pytest

from anisotropy_fea.cases import compare, disagreements, load_case
from anisotropy_fea import paths  # where the files live (ADR-0036)

CASE_DIR = paths.CASES
CASES = sorted(path for path in CASE_DIR.glob("*.toml") if not path.name.startswith("_"))


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_the_kernel_reproduces_the_case(path):
    case = load_case(path)
    for field in ("title", "source", "units"):
        assert case[field], f"{path.name}: {field} is empty"
    problems = disagreements(case)
    assert not problems, f"{case['title']}\nsource: {case['source']}\n" + "\n".join(problems)


def test_there_are_cases():
    assert len(CASES) >= 5


def test_a_wrong_expected_value_is_reported():
    case = load_case(CASE_DIR / "patch-1x1-im7-engine-equality.toml")
    case["expected"]["strain"]["*"][1] = 0.02
    reported = disagreements(case)
    assert len(reported) == 1 and reported[0].startswith("strain[Coupon-1.1][1]: expected 0.02, kernel gives 0.008")


def test_a_zero_expected_value_uses_the_group_scale():
    case = load_case(CASE_DIR / "patch-1x1-im7-engine-equality.toml")
    comparisons, problems = compare(case)
    assert not problems
    (rf_top_x,) = [c for c in comparisons if c.key == "rf[Top][0]"]
    assert rf_top_x.expected == 0.0 and rf_top_x.allowed > 0 and rf_top_x.agrees


def test_an_unknown_name_is_reported_not_skipped():
    case = load_case(CASE_DIR / "patch-1x1-im7-engine-equality.toml")
    case["expected"]["u"]["Coupon-1.99"] = [0.0, 0.0]
    reported = disagreements(case)
    assert reported and "Coupon-1.99" in reported[0]


def test_an_unknown_group_or_a_wrong_shape_is_refused_at_load(tmp_path):
    text = (CASE_DIR / "patch-1x1-im7-engine-equality.toml").read_text(encoding="utf-8").replace("../decks", str(CASE_DIR.parent / "decks").replace("\\", "/"))
    bad_group = tmp_path / "bad-group.toml"
    bad_group.write_text(text + '\n[expected.stress]\n"*" = [0.0, 0.0, 0.0]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not a result group"):
        load_case(bad_group)
    bad_shape = tmp_path / "bad-shape.toml"
    bad_shape.write_text(text.replace('"Top" = [0.0, ', '"Top" = [0.0, 1.0, '), encoding="utf-8")
    with pytest.raises(ValueError, match="list of 2 numbers"):
        load_case(bad_shape)
    no_tolerance = tmp_path / "no-tolerance.toml"
    no_tolerance.write_text(text.replace("tolerance = 1e-9", "tolerance = 0"), encoding="utf-8")
    with pytest.raises(ValueError, match="positive `tolerance`"):
        load_case(no_tolerance)
