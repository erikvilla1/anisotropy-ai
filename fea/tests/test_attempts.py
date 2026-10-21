"""Attempt folders (ADR-0039): numbered, never reused, each with its request and notes; results kept only in the latest run of
each kind. Run in a temporary folder standing in for .local/fea/."""

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.attempts import NOTES_SECTIONS, AttemptError, attempts, latest_attempt, start_attempt


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "LOCAL", tmp_path)
    return tmp_path


def result(folder, kind, name):
    run = folder / "run" / kind
    run.mkdir(parents=True, exist_ok=True)
    (run / name).write_text("results\n", encoding="utf-8")
    return run / name


def test_attempts_are_numbered_in_order_and_hold_the_request_and_the_notes(local):
    first, _ = start_attempt("tension-coupon", "make the coupon the team's way", day="2026-10-21")
    second, _ = start_attempt("tension-coupon", "again, with plane stress\n", day="2026-10-22")
    assert [f.name for f in attempts("tension-coupon")] == ["attempt-01_2026-10-21", "attempt-02_2026-10-22"]
    assert latest_attempt("tension-coupon") == second and latest_attempt("compression-coupon") is None
    assert (first / "prompt.md").read_text(encoding="utf-8") == "make the coupon the team's way\n"  # word for word
    notes = (second / "notes.md").read_text(encoding="utf-8")
    assert notes.startswith("# tension-coupon, attempt 02, 2026-10-22") and "- Engine commit: " in notes
    assert "`fea/models/tension-coupon/tension-coupon.toml`, sha256 " in notes and "`fea/models/tension-coupon/tension-coupon-nodal.toml`" in notes
    assert all(f"## {section}" in notes for section in NOTES_SECTIONS) and (second / "run").is_dir()


def test_results_are_kept_only_in_the_latest_run_of_each_kind(local):
    one, _ = start_attempt("tension-coupon", "first", day="2026-10-21")
    old_calculix, old_dat = result(one, "calculix", "x.frd"), result(one, "calculix", "x.dat")
    team_frd = result(one, "team-in-calculix", "t.frd")
    two, deleted = start_attempt("tension-coupon", "second", day="2026-10-21")
    assert deleted == []  # no later run of either kind yet
    new_calculix = result(two, "calculix", "y.frd")
    _, deleted = start_attempt("tension-coupon", "third", day="2026-10-21")
    assert deleted == [old_calculix] and not old_calculix.exists()
    assert old_dat.is_file() and team_frd.is_file() and new_calculix.is_file()  # the .dat stays; the team run is still the latest of its kind


def test_what_is_not_an_attempt_is_refused_by_name(local):
    with pytest.raises(AttemptError, match="no model folder fea/models/no-such-coupon"):
        start_attempt("no-such-coupon", "x")
    with pytest.raises(AttemptError, match="request is empty"):
        start_attempt("tension-coupon", "  \n")
    (local / "tension-coupon" / "attempts" / "scratch").mkdir(parents=True)
    with pytest.raises(AttemptError, match="scratch is not an attempt folder"):
        attempts("tension-coupon")
