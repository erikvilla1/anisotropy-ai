"""The case pages and indexes (ADR-0039): their generated blocks are current, and their hand-written parts are complete. The
coupon models and their pages are local (ADR-0042): on CI only the committed benchmarks index is checked; on the founder's
machine every case page and the team tests' index too."""

import re
import tomllib

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.case_pages import CasePageError, local_index, model_folders, pages, read_case

CHECKS_INDEX = paths.CHECKS / "README.md"
SUMMARIES = [paths.team_summary(d) for d in paths.model_dirs() if paths.team_summary(d).is_file()]


@pytest.fixture(scope="module")
def wanted():
    return pages()


def test_every_generated_block_is_what_the_records_give_today(wanted):
    assert CHECKS_INDEX in wanted  # the committed index is always written
    stale = [path.relative_to(paths.ROOT).as_posix() for path, text in wanted.items()
             if path.read_text(encoding="utf-8").replace("\r\n", "\n") != text]
    assert not stale, f"run `uv run python tools/case_pages.py` from fea/: {stale}"


def test_a_number_edited_by_hand_is_caught(wanted):
    text = CHECKS_INDEX.read_text(encoding="utf-8").replace("\r\n", "\n")
    count = re.search(r"\| (\d+) of (\d+) agree", text)  # a check record's count, CalculiX against our kernel, from the record
    assert count, "the benchmarks index lists no record"
    assert text.replace(count[0], f"| {int(count[1]) - 1} of {count[2]} agree", 1) != wanted[CHECKS_INDEX]


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


@pytest.mark.skipif(not SUMMARIES, reason="no team summary on this machine: the team's coupons are local (ADR-0042)")
def test_the_team_summary_holds_figures_only_and_is_not_a_record():
    for summary in SUMMARIES:
        data = tomllib.loads(summary.read_text(encoding="utf-8"))
        assert set(data) == {"coupon", "units", "built", "commit", "team", "equivalence", "agreement"}
        assert set(data["team"]) == {"deck", "deck_sha256", "solver", "run_date", "reports"}  # names and a digest, no values
        assert all(set(a) == {"band", "y", "quantity", "values", "agree", "within", "largest_difference"} for a in data["agreement"])
        assert data["coupon"] == summary.parent.parent.name and data["equivalence"]["same"] == data["equivalence"]["items"]
        assert summary not in paths.all_records()


def test_the_local_index_has_the_four_categories_with_or_without_the_local_folders():
    text = local_index()  # on CI there is no .local/: no team tests, the attempt folders count 0 and homework says so
    assert all(f"## {category}" in text for category in ("Team tests", "Benchmarks", "Homework", "Projects"))
    assert all(f"**{folder.name}**" in text for folder in model_folders())
