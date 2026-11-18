"""The weekly check of the coupons on this machine (ADR-0114): each coupon re-solved by today's code, in a copy, and its new CalculiX
record set beside its last one.

    uv run --project fea --extra mesh python fea/tools/weekly_coupons.py [--from <coupons' folder>] [--work <folder>] [coupon ...]

The coupons are the team's and stay on this machine (ADR-0042): public CI never sees them, so this is where a change to the engine,
the mesher or a deck writer is seen to move one of their numbers. Each coupon's folder is copied to the work folder (its solver
outputs left behind) and run there by `run_coupon.py <coupon> --every-test --no-pdf`, with ANISOTROPY_COUPONS_ROOT naming the copy,
so the coupon's own attempts, case page and package are never touched. Every compared value of the new CalculiX record, ours and
CalculiX's, and the run's answer are then set beside those of the last weekly check, kept in `.local/weekly/snapshots/<coupon>.json`:
our engine's values on the last check's code against today's, row by row. A coupon's first check has no snapshot, so it is set
beside its last record, whose values our engine computes today on that record's deck (a record keeps CalculiX's values, not ours):
that first comparison shows what today's decks change, the later ones what the code changed since the week before. A coupon
whose decks were written again after its last record (the record is stale) has nothing to be set beside: its first check is
solved all the same, gives it its first snapshot and says the record is stale, and next week's is set beside that (ADR-0114
amendment 1). The coupon's own record is left as it is.

The report is `<work>/report.md`; it and the snapshots hold the team's numbers and stay local. Exit 0 when every coupon ran and
nothing moved, 1 when a coupon's numbers moved or its run failed, 2 when there is no coupon to check, 3 when CalculiX cannot be
found (ANISOTROPY_CCX or `ccx` on PATH), since every run would fail without it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.calculix import CalculixError, find_ccx
from anisotropy_fea.case_pages import calculix_record, reaction_difference, record_rows
from anisotropy_fea.compare import RecordError

TOOLS = Path(__file__).resolve().parent
SOLVER_OUTPUTS = ("*.frd", "*.odb", "*.sta", "*.msg", "*.cvg", "*.12d", "*.inp.bak")  # the old attempts' outputs, not needed to run again
MOVED = 1e-9  # our engine gives the same numbers to the last bit on the same inputs (ADR-0073); anything past rounding is a change


@dataclass
class Check:
    coupon: str
    against: str = "its last record"  # what today's numbers are set beside
    before: str = "no record"
    after: str = "no record"
    moved: list[str] = field(default_factory=list)  # one line per row whose value changed
    failed: str | None = None
    stale: str | None = None  # why the coupon's last record could not be read: its first check only takes a snapshot
    answer: str | None = None
    answer_before: str | None = None
    seconds: float = 0.0

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        if self.stale:
            return "first snapshot"
        changed = self.moved or self.before != self.after or (self.answer_before is not None and self.answer_before != self.answer)
        return "moved" if changed else "same"


@dataclass(frozen=True)
class Row:
    kernel: float
    reference: float
    agrees: bool


def summary(folder: Path):
    """The record's compared values by key and its one line, or None and "no record"."""
    record = calculix_record(folder)
    if not record.is_file():
        return None, "no record"
    _, rows, _ = record_rows(record)
    reaction = reaction_difference(rows)
    line = f"{sum(r.agrees for r in rows)} of {len(rows)} agree" + (f"; reaction {reaction}" if reaction else "")
    return {r.key: Row(r.kernel, r.reference, r.agrees) for r in rows}, line


def read_snapshot(path: Path):
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, {key: Row(*values) for key, values in data["rows"].items()}


def write_snapshot(path: Path, rows: dict, line: str, answer: str | None, commit: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"date": date.today().isoformat(), "commit": commit, "line": line, "answer": answer,
            "rows": {key: [r.kernel, r.reference, r.agrees] for key, r in sorted(rows.items())}}
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def relative(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-30)


def compare(before: dict, after: dict) -> list[str]:
    """Each row whose engine or CalculiX value moved, or that one record has and the other has not."""
    out = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old is None or new is None:
            out.append(f"{key}: {'new row' if old is None else 'row gone'}")
            continue
        for who, a, b in (("ours", old.kernel, new.kernel), ("CalculiX", old.reference, new.reference)):
            if relative(a, b) > MOVED:
                out.append(f"{key}: {who} {a:.6g} -> {b:.6g}")
        if old.agrees != new.agrees:
            out.append(f"{key}: {'now agrees' if new.agrees else 'no longer agrees'}")
    return out


def check(source: Path, work: Path, snapshots: Path, coupon: str, python: str, commit: str | None) -> Check:
    result = Check(coupon)
    copy = work / "coupons" / coupon
    shutil.copytree(source / coupon, copy, ignore=shutil.ignore_patterns(*SOLVER_OUTPUTS))
    last = read_snapshot(snapshots / f"{coupon}.json")
    if last is None:
        try:
            rows_before, result.before = summary(copy)
        except RecordError as exc:
            rows_before, result.before, result.stale = None, "record stale", str(exc)
            result.against = "nothing: its last record is older than its deck"
    else:
        rows_before, result.before = last[1], last[0]["line"]
        result.against, result.answer_before = f"the check of {last[0]['date']}", last[0].get("answer")
    outcome = work / f"{coupon}-outcome.json"
    env = {**os.environ, paths.COUPONS_ROOT: str((work / "coupons").resolve())}
    t0 = time.monotonic()
    done = subprocess.run([python, str(TOOLS / "run_coupon.py"), coupon, "--run-by", "weekly check", "--every-test", "--no-pdf",
                           "--result", str(outcome)], cwd=paths.FEA, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=3600, check=False)
    result.seconds = time.monotonic() - t0
    (work / f"{coupon}-run.log").write_text(done.stdout + done.stderr, encoding="utf-8")
    ended = json.loads(outcome.read_text(encoding="utf-8")) if outcome.is_file() else {}
    if done.returncode != 0 or ended.get("status") != "done":
        result.failed = ended.get("message") or f"run_coupon.py exited {done.returncode}; see {coupon}-run.log"
        return result
    answer = ended.get("answer") or {}
    if answer:
        result.answer = (f"{'fails' if answer.get('fails') else 'holds'} at {answer.get('factor')} x the load, "
                         f"{answer.get('criterion')}, ply {answer.get('ply')}")
    rows_after, result.after = summary(copy)
    if result.stale is None:
        result.moved = compare(rows_before or {}, rows_after or {})
    if rows_after is not None:
        write_snapshot(snapshots / f"{coupon}.json", rows_after, result.after, result.answer, commit)
    return result


def report(checks: list[Check], work: Path, commit: str | None) -> str:
    lines = [f"# Weekly check of the coupons, {date.today().isoformat()}", "",
             f"Code: {commit or 'this checkout'}. Each coupon re-solved in a copy under `{work}`; the coupons themselves are untouched.", "",
             "| Coupon | Status | Set beside | Then | Today | Answer then | Answer today | Minutes |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in checks:
        lines.append(f"| {c.coupon} | {c.status} | {c.against} | {c.before} | {c.failed or c.after} | {c.answer_before or ''} | "
                     f"{c.answer or ''} | {c.seconds / 60:.1f} |")
    for c in checks:
        if c.stale:
            lines += ["", f"## {c.coupon}: record stale", "", f"Its last record could not be read: {c.stale}. Today's numbers are its "
                      "first snapshot, and next week's check is set beside them. Running the coupon again in its own folder writes "
                      "it a new record."]
        if c.moved:
            lines += ["", f"## {c.coupon}: what moved", "", *[f"- {m}" for m in c.moved[:200]]]
            if len(c.moved) > 200:
                lines.append(f"- and {len(c.moved) - 200} more")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("coupons", nargs="*", help="the coupons to check; default every coupon in the coupons' folder")
    parser.add_argument("--from", dest="source", type=Path, default=paths.LOCAL, help="the coupons' folder (default .local/fea/)")
    parser.add_argument("--work", type=Path, default=None, help="where the copies and the report go (default .local/weekly/<date>/)")
    parser.add_argument("--snapshots", type=Path, default=paths.ROOT / ".local" / "weekly" / "snapshots",
                        help="where each coupon's values of the last check are kept (default .local/weekly/snapshots/)")
    parser.add_argument("--commit", default=None, help="the commit of the code that runs, for the report and the snapshots")
    args = parser.parse_args()
    source = args.source.resolve()
    found = sorted(d.name for d in source.iterdir() if d.is_dir() and (d / paths.OURS / f"{d.name}.toml").is_file()) if source.is_dir() else []
    coupons = args.coupons or found
    unknown = sorted(set(coupons) - set(found))
    if unknown:
        parser.error(f"no coupon {', '.join(unknown)} in {source}")
    if not coupons:
        print(f"no coupon in {source}")
        return 2
    try:
        ccx = find_ccx()
    except CalculixError as exc:
        ccx, why = None, str(exc)
    else:
        why = "no CalculiX: set ANISOTROPY_CCX to its executable or put ccx on PATH"
    if ccx is None:
        print(why)
        return 3
    work = (args.work or paths.ROOT / ".local" / "weekly" / date.today().isoformat()).resolve()
    if (work / "coupons").exists():
        parser.error(f"{work} has a check already; give another --work")
    work.mkdir(parents=True, exist_ok=True)
    checks = []
    for coupon in coupons:
        print(f"{coupon} ...", flush=True)
        try:
            checks.append(check(source, work, args.snapshots.resolve(), coupon, sys.executable, args.commit))
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            checks.append(Check(coupon, failed=f"{type(exc).__name__}: {exc}"))
        print(f"  {checks[-1].status}: {checks[-1].failed or checks[-1].after}", flush=True)
    (work / "report.md").write_text(report(checks, work, args.commit), encoding="utf-8")
    print(f"report: {work / 'report.md'}")
    return 0 if all(c.status in ("same", "first snapshot") for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
