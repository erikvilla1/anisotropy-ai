"""Run CalculiX on a deck and read what it printed (ADR-0030).

`find_ccx` locates the solver (an explicit path, then `ANISOTROPY_CCX`, then `ccx` on PATH); `run_calculix` runs
it in a working folder and collects the `.dat`, `.frd` and `.sta` outputs, warnings and errors; `parse_dat` turns
the `.dat` text into blocks of numbers keyed by what CalculiX printed, with the header kept verbatim so nothing
is lost. The `.dat` wording was read from a real run (CalculiX 2.22, 2026-10-15); the parser tolerates the
small variations the manual's examples show.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ENV_VARIABLE = "ANISOTROPY_CCX"


class CalculixError(RuntimeError):
    """CalculiX could not be run, reported an error, or produced no readable output."""


def find_ccx(ccx: str | Path | None = None) -> Path | None:
    """The solver executable: the argument, then ANISOTROPY_CCX, then `ccx` or `ccx_dynamic` on PATH; None when absent."""
    for candidate in (ccx, os.environ.get(ENV_VARIABLE)):
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path
            raise CalculixError(f"CalculiX executable not found at {path} (from {'the argument' if candidate == ccx else ENV_VARIABLE})")
    for name in ("ccx", "ccx_dynamic", "ccx_static"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


@dataclass(frozen=True)
class CalculixResult:
    deck_path: Path
    workdir: Path
    ccx: Path
    version: str | None
    returncode: int
    stdout: str
    elapsed_s: float
    dat_text: str
    frd_path: Path | None
    sta_text: str | None
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


def ccx_version(ccx: Path) -> str | None:
    """The version line `ccx -v` prints, such as "2.22"."""
    try:
        done = subprocess.run([str(ccx), "-v"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"Version\s+([\d.]+)", done.stdout + done.stderr)
    return match.group(1) if match else None


def run_calculix(deck_path: Path | str, ccx: str | Path | None = None, workdir: Path | str | None = None,
                 timeout_s: float = 600.0, threads: int = 1) -> CalculixResult:
    """Copy the deck into the working folder as <job>.inp, run `ccx -i <job>` there, and collect the outputs."""
    solver = find_ccx(ccx)
    if solver is None:
        raise CalculixError(f"CalculiX not found: pass ccx=, set {ENV_VARIABLE}, or put ccx on PATH (docs/installation-fea-tools.md)")
    deck_path = Path(deck_path)
    workdir = Path(workdir) if workdir is not None else deck_path.parent
    workdir.mkdir(parents=True, exist_ok=True)
    job = deck_path.stem
    target = workdir / f"{job}.inp"
    if target.resolve() != deck_path.resolve():
        shutil.copyfile(deck_path, target)
    env = {**os.environ, "OMP_NUM_THREADS": str(threads)}
    start = time.perf_counter()
    try:
        done = subprocess.run([str(solver), "-i", job], cwd=workdir, capture_output=True, text=True, timeout=timeout_s, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise CalculixError(f"CalculiX did not finish {job} within {timeout_s:g} s") from exc
    elapsed = time.perf_counter() - start
    stdout = done.stdout + done.stderr
    warnings = tuple(_paragraphs(stdout, "*WARNING"))
    errors = tuple(_paragraphs(stdout, "*ERROR"))
    dat = workdir / f"{job}.dat"
    sta = workdir / f"{job}.sta"
    frd = workdir / f"{job}.frd"
    result = CalculixResult(
        deck_path=deck_path, workdir=workdir, ccx=solver, version=ccx_version(solver), returncode=done.returncode, stdout=stdout,
        elapsed_s=elapsed, dat_text=dat.read_text(encoding="utf-8", errors="replace") if dat.exists() else "",
        frd_path=frd if frd.exists() else None, sta_text=sta.read_text(encoding="utf-8", errors="replace") if sta.exists() else None,
        warnings=warnings, errors=errors,
    )
    if errors or done.returncode != 0:
        detail = "\n".join(errors) if errors else stdout[-2000:]
        raise CalculixError(f"CalculiX failed on {job} (exit {done.returncode}):\n{detail}")
    if not result.dat_text.strip():
        raise CalculixError(f"CalculiX wrote no .dat for {job}; the deck has no *NODE PRINT or *EL PRINT request")
    return result


def _paragraphs(text: str, marker: str) -> list[str]:
    found = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            block = [line.strip()]
            for following in lines[i + 1:i + 6]:
                if not following.strip() or following.lstrip().startswith("*"):
                    break
                block.append(following.strip())
            found.append(" ".join(block))
    return found


# --- the .dat file --------------------------------------------------------------------------------

HEADER = re.compile(r"^\s*(?P<name>[a-z][a-z .]*?)\s*\((?P<cols>[^)]*)\)\s*(?:for\s+(?:surface\s+)?set\s+(?P<set>\S+)\s+and\s+time\s+(?P<time>[-+0-9.Ee]+))?\s*$", re.I)
NUMBER = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([Ee][-+]?\d+)?$")


@dataclass(frozen=True)
class DatBlock:
    quantity: str  # "displacements", "forces", "total force", "stresses", "strains", "coordinates" or the header's own words
    components: tuple[str, ...]
    set_name: str
    time: float
    ids: np.ndarray  # (rows, 1) node labels, (rows, 2) element label and integration point, or (0, 0) for a totals line
    values: np.ndarray  # (rows, k)
    header: str
    tags: tuple[str, ...]  # trailing non-numeric tokens per row, such as a shell or orientation tag

    def row(self, *key: int) -> np.ndarray:
        """The values of one node (`row(label)`) or one integration point (`row(element, point)`)."""
        matches = np.flatnonzero(np.all(self.ids == np.array(key), axis=1))
        if matches.size != 1:
            raise KeyError(f"{self.quantity} for set {self.set_name}: {key} appears {matches.size} times")
        return self.values[int(matches[0])]


@dataclass(frozen=True)
class DatResults:
    blocks: tuple[DatBlock, ...]

    def find(self, quantity: str, set_name: str, time: float | None = None) -> DatBlock:
        hits = [b for b in self.blocks if b.quantity == quantity and b.set_name.upper() == set_name.upper() and (time is None or b.time == time)]
        if not hits:
            raise KeyError(f"no '{quantity}' block for set {set_name!r} in the .dat; blocks: "
                           + ", ".join(f"{b.quantity}[{b.set_name}]" for b in self.blocks))
        return hits[-1]

    def displacements(self, set_name: str, time: float | None = None) -> DatBlock:
        return self.find("displacements", set_name, time)

    def forces(self, set_name: str, time: float | None = None) -> DatBlock:
        return self.find("forces", set_name, time)

    def total_force(self, set_name: str, time: float | None = None) -> np.ndarray:
        return self.find("total force", set_name, time).values[0]

    def stresses(self, set_name: str, time: float | None = None) -> DatBlock:
        return self.find("stresses", set_name, time)

    def strains(self, set_name: str, time: float | None = None) -> DatBlock:
        return self.find("strains", set_name, time)

    def coordinates(self, set_name: str, time: float | None = None) -> DatBlock:
        return self.find("global coordinates", set_name, time)


def parse_dat(text: str) -> DatResults:
    """Every printed block: header, then numeric rows until a blank line. Malformed rows are refused by line number."""
    lines = text.splitlines()
    blocks: list[DatBlock] = []
    i = 0
    while i < len(lines):
        match = HEADER.match(lines[i])
        if not match or not lines[i].strip() or "S T E P" in lines[i] or "INCREMENT" in lines[i]:
            i += 1
            continue
        header = lines[i].strip()
        name = re.sub(r"\s+", " ", match["name"].strip().lower())
        components = tuple(c.strip() for c in match["cols"].split(",") if c.strip())
        set_name = match["set"] or ""
        time_value = float(match["time"]) if match["time"] else 0.0
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        ids, values, tags = [], [], []
        id_count = 2 if components[:2] == ("elem", "integ.pnt.") else (0 if name.startswith("total") else 1)
        while i < len(lines) and lines[i].strip():
            tokens = lines[i].split()
            numeric = [t for t in tokens if NUMBER.match(t)]
            trailing = tokens[len(numeric):]
            if len(numeric) != len(tokens) - len(trailing) or any(not NUMBER.match(t) for t in tokens[:len(numeric)]):
                raise CalculixError(f".dat line {i + 1}: cannot read {lines[i].strip()!r} under {header!r}")
            if len(numeric) < id_count + 1:
                raise CalculixError(f".dat line {i + 1}: too few numbers in {lines[i].strip()!r} under {header!r}")
            ids.append([int(float(t)) for t in numeric[:id_count]])
            values.append([float(t) for t in numeric[id_count:]])
            tags.append(" ".join(trailing))
            i += 1
        width = max((len(v) for v in values), default=0)
        if any(len(v) != width for v in values):
            raise CalculixError(f"ragged rows under {header!r}")
        blocks.append(DatBlock(quantity=name, components=components, set_name=set_name, time=time_value,
                               ids=np.asarray(ids, dtype=int).reshape(len(values), id_count), values=np.asarray(values, dtype=float).reshape(len(values), width),
                               header=header, tags=tuple(tags)))
    if not blocks:
        raise CalculixError("the .dat holds no printed block")
    return DatResults(blocks=tuple(blocks))
