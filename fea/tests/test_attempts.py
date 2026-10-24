"""Attempt folders (ADR-0039): numbered as the case page's attempt log, never reused, holding only runs; results kept only in the
latest run of each kind. Run in a temporary folder standing in for .local/fea/, with the public stand-in as its one coupon
model (the team's coupons are local, ADR-0042)."""

import pytest

from public_coupon import DESIGNATION, PUBLIC_COUPON

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.attempts import AttemptError, attempts, kinds, latest_attempt, logged_attempts, start_attempt

CASE_PAGE = f"""# {DESIGNATION}, unnotched tension

**Case.** Category: team test | Status: verified | Accepted attempt: 03

## Attempt log

| # | Date | What was tried |
| --- | --- | --- |
| 01 | 2026-10-01 | first |
| 02 | 2026-10-02 | second |
| 03 | 2026-10-03 | third |
"""


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "LOCAL", tmp_path)
    monkeypatch.setattr(paths, "MODELS", tmp_path)
    folder = tmp_path / DESIGNATION
    folder.mkdir()
    (folder / f"{DESIGNATION}.toml").write_text(PUBLIC_COUPON, encoding="utf-8")
    (folder / "README.md").write_text(CASE_PAGE, encoding="utf-8")
    return tmp_path


def result(folder, kind, name):
    run = folder / "run" / kind
    run.mkdir(parents=True, exist_ok=True)
    (run / name).write_text("results\n", encoding="utf-8")
    return run / name


def test_a_new_attempt_takes_the_next_row_of_the_attempt_log_and_holds_only_run(local):
    assert logged_attempts(DESIGNATION) == 3  # the stand-in case page's log
    first, _ = start_attempt(DESIGNATION, day="2026-10-22")
    second, _ = start_attempt(DESIGNATION, day="2026-10-23")
    assert [f.name for f in attempts(DESIGNATION)] == ["attempt-04_2026-10-22", "attempt-05_2026-10-23"]
    assert latest_attempt(DESIGNATION) == second and latest_attempt("IM7-UNC-L1") is None
    assert [p.name for p in first.iterdir()] == ["run"] and kinds(first) == []


def test_results_are_kept_only_in_the_latest_run_of_each_kind(local):
    one, _ = start_attempt(DESIGNATION, day="2026-10-22")
    old_calculix, old_dat = result(one, "calculix", "x.frd"), result(one, "calculix", "x.dat")
    team_frd = result(one, "team-in-calculix", "t.frd")
    two, deleted = start_attempt(DESIGNATION, day="2026-10-22")
    assert deleted == [] and kinds(one) == ["calculix", "team-in-calculix"]  # no later run of either kind yet
    new_calculix = result(two, "calculix", "y.frd")
    _, deleted = start_attempt(DESIGNATION, day="2026-10-22")
    assert deleted == [old_calculix] and not old_calculix.exists()
    assert old_dat.is_file() and team_frd.is_file() and new_calculix.is_file()  # the .dat stays; the team run is still the latest of its kind


def test_what_is_not_an_attempt_is_refused_by_name(local):
    with pytest.raises(AttemptError, match="no coupon model .local/fea/no-such-coupon"):
        start_attempt("no-such-coupon")
    (local / DESIGNATION / paths.RUNS / "scratch").mkdir(parents=True)
    with pytest.raises(AttemptError, match="scratch is not an attempt folder"):
        attempts(DESIGNATION)
