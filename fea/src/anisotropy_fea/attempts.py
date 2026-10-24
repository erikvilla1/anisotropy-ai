"""Attempts: the runs of every try at a test keep their own folder on the founder's machine (ADR-0039).

    .local/fea/<coupon>/our-runs/attempt-NN_<date>/run/
      kernel/              build_model.py
      calculix/            run_calculix.py
      team-in-calculix/    convert_to_calculix.py on the team's deck

The record of each try is its row in the case page's attempt log (`.local/fea/<coupon>/README.md`); NN is that row's number,
so a folder and its row always match. Only tries that ran something have a folder. A folder is never reused or overwritten.
CalculiX results (.frd) are large, so they are kept only in the latest run of each kind: when a later attempt has a run of
the same kind, the earlier .frd files are deleted (`prune_results`).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from . import paths

ATTEMPT = re.compile(r"^attempt-(?P<number>\d{2})_(?P<date>\d{4}-\d{2}-\d{2})$")
RUN_KINDS = ("kernel", "calculix", "team-in-calculix")


class AttemptError(ValueError):
    pass


def attempt_number(folder: Path) -> int:
    match = ATTEMPT.match(folder.name)
    if match is None:
        raise AttemptError(f"{folder.name} is not an attempt folder (attempt-NN_YYYY-MM-DD)")
    return int(match["number"])


def attempts(test: str) -> list[Path]:
    """The coupon's attempt folders in our-runs/, oldest first; anything else there is refused by name."""
    root = paths.local_test(test) / paths.RUNS
    if not root.is_dir():
        return []
    folders = [d for d in root.iterdir() if d.is_dir()]
    numbers = [attempt_number(d) for d in folders]
    if len(set(numbers)) != len(numbers):
        raise AttemptError(f"{root}: two attempt folders share a number")
    return sorted(folders, key=attempt_number)


def latest_attempt(test: str) -> Path | None:
    found = attempts(test)
    return found[-1] if found else None


def kinds(folder: Path) -> list[str]:
    """The kinds of run an attempt folder holds."""
    return [kind for kind in RUN_KINDS if (folder / "run" / kind).is_dir() and any((folder / "run" / kind).iterdir())]


def logged_attempts(test: str) -> int:
    """How many rows the case page's attempt log has; 0 when the test has no case page yet."""
    from .case_pages import CasePageError, read_case  # the case page is read lazily: case_pages reads attempt folders too

    try:
        return read_case(paths.MODELS / test).attempts
    except (CasePageError, FileNotFoundError):
        return 0


def prune_results(test: str) -> list[Path]:
    """Delete the .frd files of every run that a later attempt has a run of the same kind for; return what was deleted."""
    deleted = []
    found = attempts(test)
    for kind in RUN_KINDS:
        with_kind = [a for a in found if kind in kinds(a)]
        for earlier in with_kind[:-1]:
            for result in sorted((earlier / "run" / kind).glob("*.frd")):
                result.unlink()
                deleted.append(result)
    return deleted


def start_attempt(test: str, day: str | None = None) -> tuple[Path, list[Path]]:
    """Create the next attempt folder with run/, numbered after both the last folder and the attempt log; prune earlier
    results first. Returns the folder and the deleted .frd files."""
    if paths.MODELS / test not in paths.model_dirs():
        raise AttemptError(f"no coupon model .local/fea/{test}/{test}.toml; the coupons are {[d.name for d in paths.model_dirs()]}")
    deleted = prune_results(test)
    previous = attempts(test)
    number = max(attempt_number(previous[-1]) if previous else 0, logged_attempts(test)) + 1
    folder = paths.local_test(test) / paths.RUNS / f"attempt-{number:02d}_{day or date.today().isoformat()}"
    (folder / "run").mkdir(parents=True)  # never exists: the number is new
    return folder, deleted
