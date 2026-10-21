"""Attempts: every try at a test keeps its own folder on the founder's machine, failed ones included (ADR-0039).

    .local/fea/<test>/attempts/attempt-NN_<date>/
      prompt.md     the request for this attempt, word for word
      notes.md      the engine commit, the spec digests, the settings, the key numbers, the error against the reference,
                    what went right or wrong, the next step, and the session transcript it belongs to
      run/          what our tools wrote: kernel/ (build_model.py), calculix/ (run_calculix.py),
                    team-in-calculix/ (convert_to_calculix.py on the team's deck)

A folder is never reused or overwritten: the next attempt gets the next number. The engine's code is not copied; the commit
in notes.md names it. CalculiX results (.frd) are large, so they are kept only in the latest run of each kind: when a later
attempt has a run of the same kind, the earlier .frd files are deleted (`prune_results`). They can be rebuilt from the
recorded commit. The case page's attempt log (`fea/models/<test>/README.md`) has one row per folder.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import date
from pathlib import Path

from . import paths

ATTEMPT = re.compile(r"^attempt-(?P<number>\d{2})_(?P<date>\d{4}-\d{2}-\d{2})$")
RUN_KINDS = ("kernel", "calculix", "team-in-calculix")
NOTES_SECTIONS = ("Material and settings", "Key numbers", "Error against the reference", "What went right or wrong", "Next step")


class AttemptError(ValueError):
    pass


def attempt_number(folder: Path) -> int:
    match = ATTEMPT.match(folder.name)
    if match is None:
        raise AttemptError(f"{folder.name} is not an attempt folder (attempt-NN_YYYY-MM-DD)")
    return int(match["number"])


def attempts(test: str) -> list[Path]:
    """The test's attempt folders, oldest first; anything else in attempts/ is refused by name."""
    root = paths.local_test(test) / "attempts"
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


def git_commit() -> str:
    """The repository's commit, short, with '+ local changes' when tracked files differ from it; 'unknown' without git."""
    try:
        run = lambda *args: subprocess.run(["git", "-C", str(paths.ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
        commit = run("rev-parse", "--short", "HEAD")
        return commit + (" + local changes" if run("status", "--porcelain", "--untracked-files=no") else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def notes_text(test: str, number: int, day: str, commit: str, specs: list[Path]) -> str:
    """The notes.md an attempt starts with: what is known when it starts, and the sections to fill."""
    lines = [f"# {test}, attempt {number:02d}, {day}", "",
             f"- Engine commit: {commit}",
             *[f"- Spec: `{spec.relative_to(paths.ROOT).as_posix()}`, sha256 {hashlib.sha256(spec.read_bytes()).hexdigest()[:16]}" for spec in specs],
             "- Request: `prompt.md`",
             "- Session transcript: not exported yet. At the end of the session run `/export`, save it as `.local/sessions/<date>-<topic>.md` and name it here.",
             "- Runs: `run/kernel`, `run/calculix`, `run/team-in-calculix` (only those this attempt made)", ""]
    for section in NOTES_SECTIONS:
        lines += [f"## {section}", "", ""]
    lines += ["When done: add this attempt's row to the attempt log of `fea/models/" + test + "/README.md` and run `fea/tools/case_pages.py`.", ""]
    return "\n".join(lines)


def prune_results(test: str) -> list[Path]:
    """Delete the .frd files of every run that a later attempt has a run of the same kind for; return what was deleted."""
    deleted = []
    found = attempts(test)
    for kind in RUN_KINDS:
        with_kind = [a for a in found if (a / "run" / kind).is_dir() and any((a / "run" / kind).iterdir())]
        for earlier in with_kind[:-1]:
            for result in sorted((earlier / "run" / kind).glob("*.frd")):
                result.unlink()
                deleted.append(result)
    return deleted


def start_attempt(test: str, prompt: str, day: str | None = None) -> tuple[Path, list[Path]]:
    """Create the next attempt folder with prompt.md, notes.md and run/; prune earlier results first. Returns the folder and the
    deleted .frd files."""
    if not (paths.MODELS / test).is_dir():
        raise AttemptError(f"no model folder fea/models/{test}; the tests are {sorted(d.name for d in paths.MODELS.iterdir() if d.is_dir())}")
    if not prompt.strip():
        raise AttemptError("the request is empty: give it word for word with --prompt or --prompt-file")
    deleted = prune_results(test)
    day = day or date.today().isoformat()
    previous = attempts(test)
    number = attempt_number(previous[-1]) + 1 if previous else 1
    folder = paths.local_test(test) / "attempts" / f"attempt-{number:02d}_{day}"
    folder.mkdir(parents=True)  # never exists: the number is new
    (folder / "run").mkdir()
    (folder / "prompt.md").write_text(prompt.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    specs = sorted((paths.MODELS / test).glob("*.toml"))
    (folder / "notes.md").write_text(notes_text(test, number, day, git_commit(), specs), encoding="utf-8", newline="\n")
    return folder, deleted
