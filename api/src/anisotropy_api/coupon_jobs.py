"""Coupon jobs: a coupon taken from its input form, its values or its folder to its package in the background, by the command the
founder types (ADR-0050); and the studio's questions to the fea package, one command each (ADR-0051). Nothing here computes a result.

A job runs `fea/tools/run_coupon.py` in the fea project's environment (`uv run --project fea`), keeps its console output for the
status, reads its progress from the JSON file the tool rewrites after every step (`--progress`) and its outcome from the JSON
file the tool writes at the end (`--result`). One job runs at a time: runs share a coupon's folders and its attempt numbers. A
job's status lives in this process; when it ends, its receipt is one run record (ADR-0026).

The studio's setup check, the list of coupons and a coupon's values run `fea/tools/studio_tool.py` the same way, and wait for it.
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
STUDIO = FEA / "tools" / "studio_tool.py"
STATES = ("running", "done", "stopped", "refused")
LOG_TAIL = 40  # lines of the job's console a status shows
CHECK_TIMEOUT_S = 120.0  # a check is one `uv run` start and a model build; a Gmsh mesh takes longest
PROGRESS = "progress.json"


class JobRefused(RuntimeError):
    """No job, or no check, can run on this machine; the message says what is missing."""


class JobBusy(RuntimeError):
    """A job is running; one runs at a time."""

    def __init__(self, job_id: uuid.UUID):
        super().__init__(f"coupon job {job_id} is running; one runs at a time, so wait for it to end")
        self.job_id = job_id


class RecordingFailed(RuntimeError):
    """The job ended but its run record could not be written."""


class CheckTimedOut(RuntimeError):
    """The studio tool did not answer in time."""


class UnknownCoupon(KeyError):
    """No coupon of that name on this machine."""


def runner_command() -> list[str] | None:
    """`uv run --project fea python fea/tools/run_coupon.py`, or None when uv is not on PATH."""
    uv = shutil.which("uv")
    return None if uv is None else [uv, "run", "--project", str(FEA), "python", str(RUNNER)]


def studio_command() -> list[str] | None:
    """`uv run --project fea python fea/tools/studio_tool.py`, or None when uv is not on PATH."""
    uv = shutil.which("uv")
    return None if uv is None else [uv, "run", "--project", str(FEA), "python", str(STUDIO)]


def repository_path(text: str) -> Path:
    """A path the tool reported: from the repository root, or absolute when it lies elsewhere."""
    path = Path(text)
    return path if path.is_absolute() else REPO / path


@dataclass
class Job:
    id: uuid.UUID
    actor: str
    inputs: dict  # as the run record keeps them: the input's name and SHA-256, or the coupon; and the options
    folder: Path  # the job's own folder: the input as sent, the console log, the progress, the outcome
    started_at: dt.datetime
    state: str = "running"
    finished_at: dt.datetime | None = None
    outcome: dict | None = None
    run_id: uuid.UUID | None = None
    user_email: str | None = None  # the signed-in email Cloudflare Access verified for the request that started it (ADR-0056)

    @property
    def log(self) -> Path:
        return self.folder / "console.log"

    def log_tail(self) -> list[str]:
        if not self.log.is_file():
            return []
        return self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_TAIL:]

    def progress(self) -> dict | None:
        """The stage and the files so far, as the tool last wrote them; None before the first step or when the file is half-written."""
        path = self.folder / PROGRESS
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


Recorder = Callable[[Job, str, dict], "uuid.UUID | None"]  # writes the receipt of an ended job; None when recording is off


class CouponJobs:
    """The coupon jobs of this API process, at most one running, and the studio tool. `command` and `studio` are the tools'
    command lines without their arguments."""

    def __init__(self, command: list[str] | None, recorder: Recorder, root: Path | None = None, studio: list[str] | None = None):
        self.command, self.recorder, self.root, self.studio = command, recorder, root, studio
        self.jobs: dict[uuid.UUID, Job] = {}
        self.lock = threading.Lock()

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.jobs.get(job_id)

    def listed(self) -> list[Job]:
        """Every job of this process, newest first."""
        with self.lock:
            return sorted(self.jobs.values(), key=lambda job: job.started_at, reverse=True)

    def _folder(self) -> Path:
        if self.root is None:
            self.root = Path(tempfile.mkdtemp(prefix="anisotropy-coupon-jobs-"))
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def start(self, actor: str, inputs: dict, options: list[str], *, form: tuple[str, bytes] | None = None, coupon: str | None = None,
              values: bytes | None = None, user_email: str | None = None) -> Job:
        """Start a job from a filled-in form (its file name and bytes), the values (the JSON file's bytes) or a coupon's name; refused
        while another runs. `user_email` is the signed-in email, when Access is in front of the API, kept for the job's receipt."""
        if self.command is None:
            raise JobRefused("uv is not on PATH; a coupon job runs fea/tools/run_coupon.py through `uv run --project fea`")
        if sum(x is not None for x in (form, coupon, values)) != 1:
            raise ValueError("a job starts from a form, the values or a coupon: one of the three")
        with self.lock:
            busy = next((job for job in self.jobs.values() if job.state == "running"), None)
            if busy is not None:
                raise JobBusy(busy.id)
            job_id = uuid.uuid4()
            job = Job(job_id, actor, inputs, self._folder() / str(job_id), dt.datetime.now(dt.timezone.utc), user_email=user_email)
            job.folder.mkdir(parents=True)
            source = coupon
            if form is not None:
                (job.folder / form[0]).write_bytes(form[1])
                source = str(job.folder / form[0])
            if values is not None:
                name = f"values-{job_id.hex[:8]}.json"
                (job.folder / name).write_bytes(values)
                source = str(job.folder / name)
            self.jobs[job.id] = job
        args = [*self.command, source, *options, "--result", str(job.folder / "outcome.json"), "--progress", str(job.folder / PROGRESS)]
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

    def output_file(self, job: Job, key: str) -> Path:
        """One of the job's files by its key, from the outcome once it is done or from the progress while it runs: `package` is the
        zip; every other key is the file the tool reported, which must lie under the repository or the job's folder."""
        with self.lock:
            outputs = dict((job.outcome or {}).get("outputs") or (job.progress() or {}).get("outputs") or {})
        if key not in outputs:
            raise KeyError(", ".join(sorted(outputs)) or "no file yet")
        if key == "package":
            return self.package_archive(job)
        path = repository_path(outputs[key]).resolve()
        if not (path.is_relative_to(REPO.resolve()) or path.is_relative_to(job.folder.resolve())):
            raise PermissionError(f"the file {outputs[key]} lies outside the repository and the job's folder")
        if not path.is_file():
            raise FileNotFoundError(f"the file {outputs[key]} is no longer there")
        return path

    # --- the studio tool -------------------------------------------------------------------------------------------------

    def _studio(self, args: list[str], timeout_s: float) -> subprocess.CompletedProcess:
        if self.studio is None:
            raise JobRefused("uv is not on PATH; the studio's questions run fea/tools/studio_tool.py through `uv run --project fea`")
        try:
            return subprocess.run([*self.studio, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=FEA,
                                  env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            raise CheckTimedOut(f"the studio tool did not answer in {timeout_s:g} s") from None
        except OSError as exc:
            raise JobRefused(f"the studio tool could not run: {exc}") from exc

    def check(self, values: bytes, timeout_s: float | None = None) -> dict:
        """The setup check of a values file (ADR-0051): the checklist, and the preview when the inputs build a model."""
        folder = Path(tempfile.mkdtemp(prefix="check-", dir=self._folder()))
        try:
            source = folder / "values.json"
            source.write_bytes(values)
            done = self._studio(["check", str(source), "--out", str(folder / "out")], timeout_s or CHECK_TIMEOUT_S)
            checklist_path = folder / "out" / "checklist.json"
            if done.returncode != 0 or not checklist_path.is_file():
                tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
                raise JobRefused("the studio tool failed: " + (" | ".join(tail) or f"exit code {done.returncode}"))
            checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
            preview_path = folder / "out" / "preview.json"
            preview = json.loads(preview_path.read_text(encoding="utf-8")) if preview_path.is_file() else None
            return {"checklist": checklist, "preview": preview}
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def list_coupons(self, timeout_s: float | None = None) -> list[dict]:
        """Every coupon on this machine, as the studio tool lists them."""
        done = self._studio(["coupons"], timeout_s or CHECK_TIMEOUT_S)
        if done.returncode != 0:
            raise JobRefused("the studio tool failed: " + (done.stderr.strip().splitlines() or ["no message"])[-1])
        return json.loads(done.stdout)

    def coupon_values(self, name: str, timeout_s: float | None = None) -> dict:
        """A coupon's rows as the values object; UnknownCoupon when there is no coupon of that name."""
        done = self._studio(["values", name], timeout_s or CHECK_TIMEOUT_S)
        if done.returncode != 0:
            message = (done.stderr.strip().splitlines() or ["no message"])[-1]
            if "no coupon of that name" in message:
                raise UnknownCoupon(message)
            raise JobRefused("the studio tool failed: " + message)
        return json.loads(done.stdout)
