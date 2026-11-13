"""Our kernel's answer to every edit (ADR-0086): the studio sends the rows as they stand, and gets back the setup check and, when nothing
blocks, the kernel's solve with its answer (ADR-0085), labelled a preview: no mesh study, no CalculiX, no attempt, no document.

A cold `studio_tool.py live` spends about 2 s importing the fea package and 1.5 to 2 s starting Python and `uv`, and well under a second
solving a strip (docs/evaluations/fea/2026-11-10-live-solve.md). So the API keeps warm `studio_tool.py serve` workers, each holding the
package imported, and hands each request to a free one: one JSON line in, one JSON line out (`serve`'s protocol). A worker that does not
answer in time, or stops, is killed and replaced, and the request answered 504 or 503; when every worker is busy for longer than the wait,
429. With no workers configured (`ANISOTROPY_LIVE_WORKERS=0`) each request starts a fresh `studio_tool.py live`.

The API reads the files the tool wrote and passes them on as written (`raw`): the fields of a fine mesh run to megabytes, and parsing and
writing them again would cost more than the solve. The API depends on the engine alone; the fea package runs in its own processes (ADR-0051).
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .coupon_jobs import FEA

LIVE_TIMEOUT_S = 30.0  # a live solve answers in about a second; a fine Gmsh mesh in a few
LIVE_WAIT_S = 20.0  # how long a request waits for a free worker, which covers a worker's own start


class LiveTimedOut(Exception):
    """The tool did not answer in time: 504."""


class LiveBusy(Exception):
    """Every worker stayed busy for the whole wait: 429."""


class LiveRefused(Exception):
    """The tool could not answer (no `uv`, a worker that stopped, an error it reported): 503."""


@dataclass
class LiveAnswer:
    state: str
    checklist: dict
    summary: dict | None  # the solve's summary, for the run record; None when nothing was solved
    raw: dict[str, bytes]  # the files as the tool wrote them: checklist, preview, fields, explanation (those present)
    timings: dict[str, float]
    seconds: float  # at the API, from the request to the files read
    warm: bool  # answered by a warm worker


class _Worker:
    """One `studio_tool.py serve` process: its stdout read by a thread into a queue, so a wait can time out on any platform."""

    def __init__(self, command: list[str]):
        self.process = subprocess.Popen([*command, "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                        encoding="utf-8", errors="replace", cwd=FEA, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.ready = False

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)  # the worker stopped

    def wait_ready(self, timeout_s: float) -> None:
        line = self._line(timeout_s, "start")
        if not json.loads(line).get("ready"):
            raise LiveRefused(f"the live solver started with {line.strip()!r} instead of its ready line")
        self.ready = True

    def _line(self, timeout_s: float, doing: str) -> str:
        try:
            line = self.lines.get(timeout=timeout_s)
        except queue.Empty:
            raise LiveTimedOut(f"the live solver did not {doing} in {timeout_s:g} s") from None
        if line is None:
            raise LiveRefused(f"the live solver stopped (exit code {self.process.poll()})")
        return line

    def ask(self, request: dict, timeout_s: float) -> dict:
        assert self.process.stdin is not None
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
        except OSError as exc:
            raise LiveRefused(f"the live solver could not be asked: {exc}") from exc
        return json.loads(self._line(timeout_s, "answer"))

    def stop(self) -> None:
        try:
            self.process.kill()
        except OSError:
            pass


class LiveSolver:
    """The live solves of this process. `command` is the studio tool's (`uv run ... studio_tool.py`), None when `uv` is missing;
    `workers` warm processes, started in the background so the first request finds them warm, or 0 for a fresh process per request."""

    def __init__(self, command: list[str] | None, folder: Path, workers: int, timeout_s: float = LIVE_TIMEOUT_S, wait_s: float = LIVE_WAIT_S):
        self.command, self.folder, self.workers, self.timeout_s, self.wait_s = command, folder, workers, timeout_s, wait_s
        self.idle: queue.Queue[_Worker] = queue.Queue()
        self.stopped = False
        self.started = False
        self.lock = threading.Lock()

    def _start_one(self) -> None:
        """A new worker, warmed in a thread of its own; it joins the idle queue once it has said it is ready."""
        def warm() -> None:
            worker = _Worker(self.command)
            try:
                worker.wait_ready(max(self.timeout_s, 60.0))
            except (LiveTimedOut, LiveRefused, ValueError) as exc:
                print(f"live solver: a worker did not start: {exc}", flush=True)
                worker.stop()
                return
            if self.stopped:
                worker.stop()
            else:
                self.idle.put(worker)
        threading.Thread(target=warm, daemon=True).start()

    def close(self) -> None:
        self.stopped = True
        while True:
            try:
                self.idle.get_nowait().stop()
            except queue.Empty:
                return

    def solve(self, values: bytes) -> LiveAnswer:
        if self.command is None:
            raise LiveRefused("uv is not on PATH; the live solve runs fea/tools/studio_tool.py through `uv run --project fea`")
        started = time.perf_counter()
        self.folder.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="live-", dir=self.folder))
        try:
            source, out = folder / "values.json", folder / "out"
            source.write_bytes(values)
            warm = self.workers > 0
            if warm:
                self._ask_a_worker(source, out)
            else:
                self._run_once(source, out)
            return self._read(out, time.perf_counter() - started, warm)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def _start(self) -> None:
        """The workers, started on the first live request rather than with the API: a process that never solves live starts none."""
        with self.lock:
            if self.started:
                return
            self.started = True
        for _ in range(self.workers):
            self._start_one()

    def _ask_a_worker(self, source: Path, out: Path) -> None:
        self._start()
        try:
            worker = self.idle.get(timeout=self.wait_s)
        except queue.Empty:
            print(f"live solve refused: every live solver stayed busy for {self.wait_s:g} s", flush=True)  # the cause stays in the log
            raise LiveBusy("The preview is busy. Try again in a moment.") from None  # the page's words (ADR-0091 amendment 2)
        healthy = True
        try:
            answer = worker.ask({"values": str(source), "out": str(out)}, self.timeout_s)
        except (LiveTimedOut, LiveRefused):
            healthy = False
            raise
        except ValueError as exc:  # a line that is not JSON: the worker is not speaking the protocol
            healthy = False
            raise LiveRefused(f"the live solver answered something that is not JSON: {exc}") from exc
        finally:
            if healthy:
                self.idle.put(worker)
            else:
                worker.stop()
                self._start_one()
        if "error" in answer:
            raise LiveRefused(f"the live solver could not solve these rows: {answer['error']}")

    def _run_once(self, source: Path, out: Path) -> None:
        try:
            done = subprocess.run([*self.command, "live", str(source), "--out", str(out)], capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", cwd=FEA, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=self.timeout_s, check=False)
        except subprocess.TimeoutExpired:
            raise LiveTimedOut(f"the live solver did not answer in {self.timeout_s:g} s") from None
        except OSError as exc:
            raise LiveRefused(f"the live solver could not run: {exc}") from exc
        if done.returncode != 0:
            tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
            raise LiveRefused("the live solver failed: " + (" | ".join(tail) or f"exit code {done.returncode}"))

    @staticmethod
    def _read(out: Path, seconds: float, warm: bool) -> LiveAnswer:
        checklist_path = out / "checklist.json"
        if not checklist_path.is_file():
            raise LiveRefused("the live solver wrote no checklist")
        raw = {name: (out / f"{name}.json").read_bytes() for name in ("checklist", "preview", "fields", "explanation") if (out / f"{name}.json").is_file()}
        checklist = json.loads(raw["checklist"])
        summary = json.loads((out / "summary.json").read_bytes()) if (out / "summary.json").is_file() else None
        timings = json.loads((out / "timings.json").read_bytes()) if (out / "timings.json").is_file() else {}
        return LiveAnswer(state=checklist["state"], checklist=checklist, summary=summary, raw=raw, timings=timings, seconds=seconds, warm=warm)
