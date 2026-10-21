"""The case pages and indexes (ADR-0039): their generated blocks are current, and their hand-written parts are complete."""

import tomllib

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.case_pages import CasePageError, local_index, model_folders, pages, read_case

TENSION = paths.MODELS / "tension-coupon"


@pytest.fixture(scope="module")
def wanted():
    return pages()


def test_every_generated_block_is_what_the_records_give_today(wanted):
    stale = [path.relative_to(paths.ROOT).as_posix() for path, text in wanted.items()
             if path.read_text(encoding="utf-8").replace("\r\n", "\n") != text]
    assert not stale, f"run `uv run python tools/case_pages.py` from fea/: {stale}"


def test_a_number_edited_by_hand_is_caught(wanted):
    readme = TENSION / "README.md"
    text = readme.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "| 105884 N | 105993 N | +0.10 % |" in text  # the reaction, CalculiX against our kernel, from the record
    assert text.replace("| 105993 N |", "| 105000 N |") != wanted[readme]


def test_every_case_page_has_a_case_line_and_a_numbered_attempt_log():
    for folder in model_folders():
        case = read_case(folder)
        assert case.category and case.attempts >= 1
        assert case.accepted.isdigit() and 1 <= int(case.accepted) <= case.attempts, f"{folder.name}: accepted attempt {case.accepted}"


@pytest.mark.parametrize("page, message", [
    ("# X\n\nNo case line.\n\n## Attempt log\n\n| 01 | a |\n", "no case line"),
    ("**Case.** Category: team test | Status: done | Accepted attempt: 01\n\n## Attempt log\n\n| 01 | a |\n", "is not one of"),
    ("**Case.** Category: team test | Status: verified | Accepted attempt: 01\n", "no '## Attempt log'"),
    ("**Case.** Category: team test | Status: verified | Accepted attempt: 01\n\n## Attempt log\n\nnone\n", "has no rows"),
    ("**Case.** Category: team test | Status: verified | Accepted attempt: 02\n\n## Attempt log\n\n| 01 | a |\n| 03 | b |\n", "numbered 01, 02"),
], ids=["case line", "status", "log", "rows", "numbering"])
def test_an_incomplete_case_page_is_refused_by_name(tmp_path, monkeypatch, page, message):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(page, encoding="utf-8")
    with pytest.raises(CasePageError, match=message):
        read_case(tmp_path)


def test_the_team_summary_holds_figures_only_and_is_not_a_record():
    summary = paths.team_summary(TENSION)
    data = tomllib.loads(summary.read_text(encoding="utf-8"))
    assert set(data) == {"coupon", "units", "built", "commit", "team", "equivalence", "agreement"}
    assert set(data["team"]) == {"deck", "deck_sha256", "solver", "run_date", "reports"}  # names and a digest, no values
    assert all(set(a) == {"band", "y", "quantity", "values", "agree", "within", "largest_difference"} for a in data["agreement"])
    assert data["coupon"] == "X840PW-UNT-L1" and data["equivalence"]["same"] == data["equivalence"]["items"] == 23
    assert summary not in paths.all_records()


def test_the_local_index_has_the_four_categories_with_or_without_the_local_folders():
    text = local_index()  # on CI there is no .local/: the attempt folders count 0 and homework says so
    assert all(f"## {category}" in text for category in ("Team tests", "Benchmarks", "Homework", "Projects"))
    assert all(f"**{name}**" in text for name in ("X840PW-UNT-L1", "X840PW-UNC-L1", "X840PW-OHT-L1"))
