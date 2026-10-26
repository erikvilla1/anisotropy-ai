"""Run Abaqus/Standard on a deck without the GUI, and export its fields as CAE-format reports (ADR-0045).

`find_abaqus` locates the command (an explicit path, then `ANISOTROPY_ABAQUS`, then `abaqus` on PATH, which on Windows is
`C:\\SIMULIA\\Commands\\abaqus.bat`); `run_abaqus` runs `abaqus job=<job> input=<job>.inp interactive ask_delete=OFF` in a working
folder and collects the `.odb`, `.dat`, `.sta` and `.msg`, warnings and errors; `extract_fields` runs `tools/abaqus_extract_fields.py`
under `abaqus python` on an ODB and returns the CSV files it wrote, which `abaqus_report.read_field_report` reads. The wording
of a failed run was read from Abaqus 2025 (2026-10-24): `***ERROR` paragraphs in the `.dat` and `.msg`, and the `.sta` ending
"THE ANALYSIS HAS NOT BEEN COMPLETED" instead of "THE ANALYSIS HAS COMPLETED SUCCESSFULLY".

Abaqus is an optional second reference beside CalculiX (ADR-0030): the install on the founder's machine is a UC San Diego
teaching licence, usable for the course and the team comparison, never for a customer deliverable, and every solve takes
tokens from a shared pool. Nothing in the pipeline needs it; the tests that do skip when it is absent.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .calculix import _paragraphs

ENV_VARIABLE = "ANISOTROPY_ABAQUS"
EXTRACT_SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "abaqus_extract_fields.py"
QUANTITIES = ("S11", "S22", "S12", "Mises")
COMPLETED = "THE ANALYSIS HAS COMPLETED SUCCESSFULLY"
NOT_COMPLETED = "THE ANALYSIS HAS NOT BEEN COMPLETED"


class AbaqusError(RuntimeError):
    """Abaqus could not be run, reported an error, or produced no ODB."""


def find_abaqus(abaqus: str | Path | None = None) -> Path | None:
    """The command: the argument, then ANISOTROPY_ABAQUS, then `abaqus` on PATH (the .bat on Windows); None when absent."""
    for candidate in (abaqus, os.environ.get(ENV_VARIABLE)):
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path
            raise AbaqusError(f"Abaqus command not found at {path} (from {'the argument' if candidate == abaqus else ENV_VARIABLE})")
    found = shutil.which("abaqus")
    return Path(found) if found else None


def abaqus_version(abaqus: Path) -> str | None:
    """The release `abaqus information=release` prints, such as "2025"."""
    try:
        done = subprocess.run([str(abaqus), "information=release"], capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"^Abaqus (\d{4}\S*)\s*$", done.stdout, re.M)
    return match.group(1) if match else None


@dataclass(frozen=True)
class AbaqusResult:
    deck_path: Path
    workdir: Path
    abaqus: Path
    version: str | None
    returncode: int
    stdout: str
    elapsed_s: float
    odb_path: Path
    dat_text: str
    sta_text: str
    msg_text: str
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


def analysis_problems(stdout: str, sta_text: str, msg_text: str, dat_text: str) -> list[str]:
    """Why a run failed, from what Abaqus wrote: error paragraphs, the status file's verdict, the log's last word."""
    problems = _paragraphs(msg_text, "***ERROR") + _paragraphs(dat_text, "***ERROR")
    if NOT_COMPLETED in sta_text:
        problems.append(NOT_COMPLETED.capitalize())
    elif COMPLETED not in sta_text:
        problems.append("the .sta does not say the analysis completed")
    if "exited with errors" in stdout or "exited with error" in stdout:
        problems.append(next((line.strip() for line in stdout.splitlines() if "exited with error" in line), "Abaqus exited with errors"))
    return list(dict.fromkeys(problems))


def run_abaqus(deck_path: Path | str, abaqus: str | Path | None = None, workdir: Path | str | None = None,
               timeout_s: float = 1800.0, cpus: int = 1) -> AbaqusResult:
    """Copy the deck into the working folder as <job>.inp, run Abaqus/Standard there in the foreground, and collect the outputs.

    A stale lock file (`<job>.lck`, left by a run that was killed) is refused rather than deleted: Abaqus may still be running."""
    command = find_abaqus(abaqus)
    if command is None:
        raise AbaqusError(f"Abaqus not found: pass abaqus=, set {ENV_VARIABLE}, or put abaqus on PATH (docs/installation-fea-tools.md)")
    deck_path = Path(deck_path)
    workdir = Path(workdir) if workdir is not None else deck_path.parent
    workdir.mkdir(parents=True, exist_ok=True)
    job = deck_path.stem
    lock = workdir / f"{job}.lck"
    if lock.exists():
        raise AbaqusError(f"{lock} exists: Abaqus is still running {job}, or a killed run left it; remove it by hand when no Abaqus is running")
    target = workdir / f"{job}.inp"
    if target.resolve() != deck_path.resolve():
        shutil.copyfile(deck_path, target)
    start = time.perf_counter()
    try:
        done = subprocess.run([str(command), f"job={job}", f"input={job}.inp", "interactive", "ask_delete=OFF", f"cpus={int(cpus)}"],
                              cwd=workdir, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AbaqusError(f"Abaqus did not finish {job} within {timeout_s:g} s; look for {lock} before running again") from exc
    elapsed = time.perf_counter() - start
    stdout = done.stdout + done.stderr

    def text_of(suffix: str) -> str:
        path = workdir / f"{job}{suffix}"
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    dat, sta, msg = text_of(".dat"), text_of(".sta"), text_of(".msg")
    warnings = tuple(_paragraphs(msg, "***WARNING") + _paragraphs(dat, "***WARNING"))
    errors = tuple(analysis_problems(stdout, sta, msg, dat))
    odb = workdir / f"{job}.odb"
    result = AbaqusResult(deck_path=deck_path, workdir=workdir, abaqus=command, version=abaqus_version(command), returncode=done.returncode,
                          stdout=stdout, elapsed_s=elapsed, odb_path=odb, dat_text=dat, sta_text=sta, msg_text=msg, warnings=warnings, errors=errors)
    if errors or done.returncode != 0 or not odb.exists():
        detail = "\n".join(errors) if errors else stdout[-2000:]
        raise AbaqusError(f"Abaqus failed on {job} (exit {done.returncode}):\n{detail}")
    return result


def extract_fields(odb_path: Path | str, out_dir: Path | str, quantities: tuple[str, ...] = QUANTITIES, step: str | None = None,
                   frame: int | None = None, instance: str | None = None, layer_point: str | None = None, abaqus: str | Path | None = None,
                   timeout_s: float = 600.0) -> dict[str, Path]:
    """Run the extraction script under `abaqus python` and return the files it wrote, keyed by quantity, plus `RF` (the reactions,
    when the ODB holds them) and `json` (the provenance). The script's refusals come back as AbaqusError."""
    command = find_abaqus(abaqus)
    if command is None:
        raise AbaqusError(f"Abaqus not found: pass abaqus=, set {ENV_VARIABLE}, or put abaqus on PATH (docs/installation-fea-tools.md)")
    if not EXTRACT_SCRIPT.is_file():
        raise AbaqusError(f"the extraction script is missing: {EXTRACT_SCRIPT}")
    odb_path, out_dir = Path(odb_path).resolve(), Path(out_dir).resolve()  # the script runs in out_dir: relative paths would not reach it
    if not odb_path.is_file():
        raise AbaqusError(f"no ODB at {odb_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    args = [str(command), "python", str(EXTRACT_SCRIPT), str(odb_path), "--out", str(out_dir), "--quantities", *quantities]
    for flag, value in (("--step", step), ("--frame", frame), ("--instance", instance), ("--layer-point", layer_point)):
        if value is not None:
            args += [flag, str(value)]
    try:
        done = subprocess.run(args, cwd=out_dir, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AbaqusError(f"the extraction of {odb_path.name} did not finish within {timeout_s:g} s") from exc
    output = done.stdout + done.stderr
    if done.returncode != 0:
        raise AbaqusError(f"extraction of {odb_path.name} failed (exit {done.returncode}):\n{output[-2000:]}")
    provenance = out_dir / f"{odb_path.stem}-extract.json"
    if not provenance.is_file():
        raise AbaqusError(f"the extraction wrote no {provenance.name}:\n{output[-2000:]}")
    files = {key: out_dir / entry["path"] for key, entry in json.loads(provenance.read_text(encoding="utf-8"))["files"].items()}
    missing = [key for key in quantities if key not in files or not files[key].is_file()]
    if missing:
        raise AbaqusError(f"the extraction wrote no file for {missing}:\n{output[-2000:]}")
    files["json"] = provenance
    return files


def read_provenance(path: Path | str) -> dict:
    """The `<job>-extract.json` the script writes: solver, creation time, step, frame, instance, files and their digests."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_reactions(path: Path | str) -> dict[tuple[str, int], tuple[float, float, float]]:
    """The `<job>-RF.csv` the script writes: (instance name, "" for an assembly node; node label) -> (RF1, RF2, RF3)."""
    import csv

    reactions: dict[tuple[str, int], tuple[float, float, float]] = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0][:5] != ["ODB Name", "Step", "Frame", "Part Instance Name", "Node Label"]:
        raise AbaqusError(f"{Path(path).name} is not a reactions file the extraction script writes")
    header = rows[0]
    for cells in rows[1:]:
        if not cells:
            continue
        row = dict(zip(header, cells))
        reactions[(row["Part Instance Name"], int(row["Node Label"]))] = (float(row["RF1"]), float(row["RF2"]), float(row["RF3"]))
    return reactions


def reactions_by_set(deck, reactions: dict[tuple[str, int], tuple[float, float, float]]) -> dict[str, list[float]]:
    """[RF1, RF2] summed over the nodes of every RF-* or Grip-* node set of the deck that carries a reaction. Abaqus names are not
    case-sensitive and the ODB spells an instance in capitals (`COUPON-1` for the deck's `Coupon-1`, read 2026-10-25), so the
    instance is matched without regard to case; before that, a grip on instance nodes found no reaction."""
    by_key = {(instance.upper(), label): rf for (instance, label), rf in reactions.items()}
    totals: dict[str, list[float]] = {}
    for name, keys in deck.nsets.items():
        if not name.startswith(("RF-", "Grip-")):
            continue
        total = [0.0, 0.0, 0.0]
        for instance, label in keys:
            rf = by_key.get(((instance or "").upper(), label))
            if rf is not None:
                total = [a + b for a, b in zip(total, rf)]
        if any(total):
            totals[name] = total[:2]
    return totals
