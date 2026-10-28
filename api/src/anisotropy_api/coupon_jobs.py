"""Coupon jobs: a coupon taken from its input form to its package in the background, by the command the founder types (ADR-0050).
Nothing here computes a result.

A job runs `fea/tools/run_coupon.py` in the fea project's environment (`uv run --project fea`), keeps its console output for the
status and reads its outcome from the JSON file the tool writes (`--result`). One job runs at a time: runs share a coupon's
folders and its attempt numbers. A job's status lives in this process; when it ends, its receipt is one run record (ADR-0026).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FEA = REPO / "fea"
RUNNER = FEA / "tools" / "run_coupon.py"
STATES = ("running", "done", "stopped", "refused")
LOG_TAIL = 40  # lines of the job's console a status shows


class JobRefused(RuntimeError):
    """No job can start on this machine; the message says what is missing."""


class JobBusy(RuntimeError):
    """A job is running; one runs at a time."""

    def __init__(self, job_id: uuid.UUID):
        super().__init__(f"coupon job {job_id} is running; one runs at a time, so wait for it to end")
        self.job_id = job_id


class RecordingFailed(RuntimeError):
    """The job ended but its run record could not be written."""


def runner_command() -> list[str] | None:
    """`uv run --project fea python fea/tools/run_coupon.py`, or None when uv is not on PATH."""
    uv = shutil.which("uv")
    return None if uv is None else [uv, "run", "--project", str(FEA), "python", str(RUNNER)]


def repository_path(text: str) -> Path:
    """A path the tool reported: from the repository root, or absolute when it lies elsewhere."""
    path = Path(text)
    return path if path.is_absolute() else REPO / path


@dataclass
class Job:
    id: uuid.UUID
    actor: str
    inputs: dict  # as the run record keeps them: the form's name and SHA-256, or the coupon; and the options
    folder: Path  # the job's own folder: the form as sent, the console log, the outcome
    started_at: dt.datetime
    state: str = "running"
    finished_at: dt.datetime | None = None
    outcome: dict | None = None
    run_id: uuid.UUID | None = None

    @property
    def log(self) -> Path:
        return self.folder / "console.log"

    def log_tail(self) -> list[str]:
        if not self.log.is_file():
            return []
        return self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_TAIL:]


Recorder = Callable[[Job, str, dict], "uuid.UUID | None"]  # writes the receipt of an ended job; None when recording is off


class CouponJobs:
    """The coupon jobs of this API process, at most one running. `command` is the tool's command line without its arguments."""

    def __init__(self, command: list[str] | None, recorder: Recorder, root: Path | None = None):
        self.command, self.recorder, self.root = command, recorder, root
        self.jobs: dict[uuid.UUID, Job] = {}
        self.lock = threading.Lock()

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.jobs.get(job_id)

    def start(self, actor: str, inputs: dict, options: list[str], *, form: tuple[str, bytes] | None = None,
              coupon: str | None = None) -> Job:
        """Start a job from a filled-in form (its file name and bytes) or a coupon's name; refused while another runs."""
        if self.command is None:
            raise JobRefused("uv is not on PATH; a coupon job runs fea/tools/run_coupon.py through `uv run --project fea`")
        if (form is None) == (coupon is None):
            raise ValueError("a job starts from a form or a coupon, not both and not neither")
        with self.lock:
            busy = next((job for job in self.jobs.values() if job.state == "running"), None)
            if busy is not None:
                raise JobBusy(busy.id)
            if self.root is None:
                self.root = Path(tempfile.mkdtemp(prefix="anisotropy-coupon-jobs-"))
            job_id = uuid.uuid4()
            job = Job(job_id, actor, inputs, self.root / str(job_id), dt.datetime.now(dt.timezone.utc))
            job.folder.mkdir(parents=True)
            source = coupon
            if form is not None:
                (job.folder / form[0]).write_bytes(form[1])
                source = str(job.folder / form[0])
            self.jobs[job.id] = job
        args = [*self.command, source, *options, "--result", str(job.folder / "outcome.json")]
        threading.Thread(target=self._run, args=(job, args), name=f"coupon-job-{job.id}", daemon=True).start()
        return job

    def _run(self, job: Job, args: list[str]) -> None:
        result = job.folder / "outcome.json"
        try:
            with job.log.open("wb") as log:
                done = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, cwd=FEA,
                                      env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=False)
            outcome = json.loads(result.read_text(encoding="utf-8")) if result.is_file() else {
                "status": "stopped", "message": f"{Path(self.command[-1]).name} exited with code {done.returncode} and wrote no outcome; "
                                                "the end of its console says why", "coupon": None, "attempt": None, "outputs": {}}
        except (OSError, json.JSONDecodeError) as exc:
            outcome = {"status": "stopped", "message": f"the job could not run: {exc}", "coupon": None, "attempt": None, "outputs": {}}
        state = outcome["status"] if outcome.get("status") in STATES[1:] else "stopped"
        try:
            run_id = self.recorder(job, state, outcome)
        except RecordingFailed as exc:  # no result without its receipt (ADR-0026)
            state, run_id = "stopped", None
            outcome = {**outcome, "message": f"the job ended ({outcome.get('message')}) but its run record could not be written: {exc}; "
                                             "its result is withheld", "outputs": {}}
        with self.lock:
            job.outcome, job.run_id, job.finished_at = outcome, run_id, dt.datetime.now(dt.timezone.utc)
            job.state = state

    def package_archive(self, job: Job) -> Path:
        """The finished job's package folder as a zip in the job's folder, made once."""
        package = repository_path(job.outcome["outputs"]["package"])
        if not package.is_dir():
            raise FileNotFoundError(f"the package folder {job.outcome['outputs']['package']} is no longer there")
        archive = job.folder / f"{package.name}.zip"
        if not archive.is_file():
            shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=package.parent, base_dir=package.name)
        return archive
