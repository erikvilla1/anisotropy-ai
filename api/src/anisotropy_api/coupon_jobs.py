"""Coupon jobs: a coupon taken from its input form, its values or its folder to its package in the background, by the command the
founder types (ADR-0050); and the studio's questions to the fea package, one command each (ADR-0051). Nothing here computes a result.

A job runs `fea/tools/run_coupon.py` in the fea project's environment (`uv run --project fea`), keeps its console output for the
status, reads its progress from the JSON file the tool rewrites after every step (`--progress`) and its outcome from the JSON
file the tool writes at the end (`--result`). One job runs at a time: runs share a coupon's folders and its attempt numbers. A
job's status lives in this process; when it ends, its receipt is one run record (ADR-0026).

With the job queue (ADR-0056 stage 3, amendment 3) the work splits over containers, one role each (`ANISOTROPY_JOB_ROLE`):

- `queue`, the API's own container: a job is filed, not run. Its input goes to the object store, its row to the jobs table as
  `queued`, and the Worker hands it to the queue. Its status is read back from the row and its files from the store.
- `solver`, a container of the job's own that the queue's consumer starts: it claims the row, brings the coupons level with the
  store, and runs the tool with a gate (`--gate`). One job at a time names its coupon, under a database lock; at the gate the job
  claims its coupon on its row, where a unique index allows one running job per coupon, so two containers never number attempts
  of one coupon at once. A job whose coupon another job holds goes back to the queue. While it runs, and until its row's last
  write, a heartbeat writes its stage, its log and its sign of life to the row; a thread of its own files the files made so far in
  the store (ADR-0056 amendment 5).

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
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from .records import (claim_coupon, claim_job, fetch_job, insert_job, jobs_started_since, list_jobs, naming_lock, queue_position, running_job_of,
                      sweep_stale, update_job)
from .storage import ObjectStore, content_type, input_key, store_file, store_folder, store_job, sync

REPO = Path(__file__).resolve().parents[3]
FEA = REPO / "fea"
LOCAL_FEA = REPO / ".local" / "fea"  # where the tool keeps the coupons (fea/src/anisotropy_fea/paths.py)
RUNNER = FEA / "tools" / "run_coupon.py"
STUDIO = FEA / "tools" / "studio_tool.py"
STATES = ("running", "done", "stopped", "refused")  # what the tool and this process know; the jobs table adds `queued` (migration 0008)
LOG_TAIL = 40  # lines of the job's console a status shows
CHECK_TIMEOUT_S = 120.0  # a check is one `uv run` start and a model build; a Gmsh mesh takes longest
PROGRESS = "progress.json"
GATE = "gate"  # the file the tool waits for once it has named the coupon (--gate)
GATE_GO = "go"
# The job queue (ADR-0056 amendment 3). Every number here is a first choice to be revised from the hosted tier's measurements.
TICK_S = 0.1  # how often a solver looks at a job held at the gate
HEARTBEAT_S = 5.0  # how often a solver writes a running job's row (its sign of life, stage, log, where its files are) and files its running files
SILENT_AFTER = dt.timedelta(minutes=2)  # a running job whose solver has written nothing for this long has lost its container
QUEUED_AFTER = dt.timedelta(hours=1)  # a job queued this long was lost by the queue or ran out of retries
SWEEP_EVERY_S = 10.0  # a process looks for lost jobs at most this often, on the requests that read jobs
SYNC_EVERY_S = 30.0  # the API's container brings its coupons level with the store at most this often, for the list, values and check
LIVE_KEYS = ("checklist", "preview", "fields", "explanation", "kernel_summary", "record")  # the files a browser reads while the job still runs:
# the result's, which the tool reports before it draws and builds the package (ADR-0064)
# The container's peak memory, one job per solver container: cgroup v2's file, else cgroup v1's (a Docker host still on v1)
CGROUP_PEAKS = (Path("/sys/fs/cgroup/memory.peak"), Path("/sys/fs/cgroup/memory/memory.max_usage_in_bytes"))


class JobRefused(RuntimeError):
    """No job, or no check, can run on this machine; the message says what is missing."""


class JobLimited(RuntimeError):
    """The person has reached a per-user limit of the hosted tier (ADR-0056): a job of theirs still runs, or the day's cap is used up."""


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
    folder: Path | None  # the job's own folder: the input as sent, the console log, the progress, the outcome; None for a job read back from its row
    started_at: dt.datetime
    state: str = "running"
    finished_at: dt.datetime | None = None
    outcome: dict | None = None
    run_id: uuid.UUID | None = None
    user_email: str | None = None  # the signed-in email Cloudflare Access verified for the request that started it (ADR-0056)
    stored: dict[str, str] = field(default_factory=dict)  # output key -> where the object store keeps the file (ADR-0050 amendment 2)
    snapshot: dict | None = None  # a job of an earlier process: its row's stage, stages, outputs and log tail, in place of the files
    project_id: uuid.UUID | None = None  # the workspace project it was started for (ADR-0062 part 6)
    process: subprocess.Popen | None = field(default=None, repr=False, compare=False)  # a solver's running tool
    stop_reason: str | None = None  # why a solver stopped the tool, when it did (the per-job timeout)

    @property
    def log(self) -> Path | None:
        return None if self.folder is None else self.folder / "console.log"

    def log_tail(self) -> list[str]:
        if self.folder is None:
            return list((self.snapshot or {}).get("log_tail", []))
        if not self.log.is_file():
            return []
        return self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_TAIL:]

    def progress(self) -> dict | None:
        """The stage and the files so far, as the tool last wrote them; None before the first step or when the file is half-written.
        For a job read back from its row, what the row kept."""
        if self.folder is None:
            return self.snapshot
        path = self.folder / PROGRESS
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    @classmethod
    def from_row(cls, row) -> "Job":
        """A job as its row in the jobs table keeps it, for a job that another process ran (ADR-0050 amendment 2)."""
        outcome = None if row.state in ("queued", "running") else {"status": row.state, "message": row.message, "coupon": row.coupon,
                                                                   "attempt": row.attempt, "outputs": dict(row.outputs),
                                                                   "documents": "written" if "package" in row.outputs else None}
        # a running row's message is the result once its solver reported it (`_heartbeat`); the documents are still being made
        snapshot = {"stage": row.stage, "done": list(row.stages_done), "stages": list(row.stages), "outputs": dict(row.outputs), "coupon": row.coupon,
                    "attempt": row.attempt, "log_tail": list(row.log_tail), "message": row.message,
                    "result": row.message if row.state == "running" else None}
        return cls(row.id, row.actor, dict(row.inputs), None, row.started_at, state=row.state, finished_at=row.finished_at, outcome=outcome,
                   run_id=row.run_id, user_email=row.user_email, stored=dict(row.stored), snapshot=snapshot, project_id=getattr(row, "project_id", None))


Recorder = Callable[[Job, str, dict], "uuid.UUID | None"]  # writes the receipt of an ended job; None when recording is off


class CouponJobs:
    """The coupon jobs of this API process, at most one running, and the studio tool. `command` and `studio` are the tools'
    command lines without their arguments."""

    def __init__(self, command: list[str] | None, recorder: Recorder, root: Path | None = None, studio: list[str] | None = None,
                 store: ObjectStore | None = None, table: Engine | None = None, local_root: Path | None = None, per_day: int | None = None,
                 role: str | None = None):
        """`store` is the object store a done job's files go to and `table` the database holding the jobs table (ADR-0050 amendment
        2); None keeps the files on the local disk and the status in this process, as before. `local_root` is where the tool keeps
        the coupons, .local/fea/ by default. `per_day`, with the table, is the hosted tier's per-user limit: one running job per
        person and at most that many a day (ADR-0056); None means no such limit. `role` is the job queue's (ADR-0056 amendment 3):
        "queue" files jobs for the queue, "solver" runs the queued job it is given; None runs every job here."""
        self.command, self.recorder, self.root, self.studio = command, recorder, root, studio
        self.store, self.table, self.local_root = store, table, local_root or LOCAL_FEA
        if per_day is not None and table is None:
            raise ValueError("a per-user limit counts jobs in the jobs table, so it needs the table")
        if role not in (None, "queue", "solver"):
            raise ValueError(f"no job role {role!r}; 'queue', 'solver' or None")
        if role is not None and (store is None or table is None):
            raise ValueError(f"the {role} role passes jobs between containers through the jobs table and the object store, so it needs both")
        self.per_day, self.role = per_day, role
        self.synced_at: float | None = None
        self.swept_at: float | None = None
        self.process = str(uuid.uuid4())
        self.jobs: dict[uuid.UUID, Job] = {}
        self.lock = threading.Lock()

    def get(self, job_id: uuid.UUID) -> Job | None:
        """A job of this process, or of an earlier one from the jobs table."""
        job = self.jobs.get(job_id)
        if job is None and self.table is not None:
            self.sweep()
            row = fetch_job(self.table, job_id)
            job = None if row is None else Job.from_row(row)
            if row is not None and row.state == "queued" and not row.message:
                ahead = queue_position(self.table, row.id, row.started_at)
                job.snapshot["message"] = f"waiting for a free solver; {ahead} job(s) ahead of this one" if ahead else "waiting for a free solver"
        return job

    def sweep(self, force: bool = False) -> int:
        """With the job queue, stop the jobs nothing will finish (`records.sweep_stale`), at most every SWEEP_EVERY_S unless `force`;
        0 without the queue."""
        if self.role is None or (not force and self.swept_at is not None and time.monotonic() - self.swept_at < SWEEP_EVERY_S):
            return 0
        self.swept_at = time.monotonic()
        try:
            return sweep_stale(self.table, dt.datetime.now(dt.timezone.utc), silent_after=SILENT_AFTER, queued_after=QUEUED_AFTER)
        except SQLAlchemyError:
            return 0  # a sweep is housekeeping; the request it rides on goes on

    def refresh(self) -> None:
        """The API's container under the job queue: its coupons brought level with the store, at most every SYNC_EVERY_S, since the
        solvers write them; the list, a coupon's values and the setup check read them from this disk."""
        if self.role != "queue" or (self.synced_at is not None and time.monotonic() - self.synced_at < SYNC_EVERY_S):
            return
        try:
            sync(self.store, self.local_root)
        except Exception as exc:  # the store's own errors or the disk's: the disk as it is serves, a little behind
            print(f"the coupons could not be brought level with the store: {str(exc).splitlines()[0]}", flush=True)
        self.synced_at = time.monotonic()

    def listed(self) -> list[Job]:
        """Every job, newest first: this process's, and from the jobs table those of earlier processes."""
        self.sweep()
        with self.lock:
            jobs = dict(self.jobs)
        if self.table is not None:
            for row in list_jobs(self.table):
                jobs.setdefault(row.id, Job.from_row(row))
        return sorted(jobs.values(), key=lambda job: job.started_at, reverse=True)

    def _folder(self) -> Path:
        if self.root is None:
            self.root = Path(tempfile.mkdtemp(prefix="anisotropy-coupon-jobs-"))
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def start(self, actor: str, inputs: dict, options: list[str], *, form: tuple[str, bytes] | None = None, coupon: str | None = None,
              values: bytes | None = None, user_email: str | None = None, project_id: uuid.UUID | None = None) -> Job:
        """Start a job from a filled-in form (its file name and bytes), the values (the JSON file's bytes) or a coupon's name; refused
        while another runs. `user_email` is the signed-in email, when Access is in front of the API, kept for the job's receipt;
        `project_id` the workspace project the job is run for, already known to be the requester's (ADR-0062 part 6). With the job
        queue the job is filed, not run (`_enqueue`)."""
        if self.role == "solver":
            raise JobRefused("this container runs the queued jobs it is given; a job starts through the API's own container")
        if sum(x is not None for x in (form, coupon, values)) != 1:
            raise ValueError("a job starts from a form, the values or a coupon: one of the three")
        if self.role == "queue":
            return self._enqueue(actor, inputs, options, form=form, coupon=coupon, values=values, user_email=user_email, project_id=project_id)
        if self.command is None:
            raise JobRefused("uv is not on PATH; a coupon job runs fea/tools/run_coupon.py through `uv run --project fea`")
        if self.per_day is not None:
            self._within_limits(actor, user_email)
        with self.lock:
            busy = next((job for job in self.jobs.values() if job.state == "running"), None)
            if busy is not None:
                raise JobBusy(busy.id)
            job_id = uuid.uuid4()
            job = Job(job_id, actor, inputs, self._folder() / str(job_id), dt.datetime.now(dt.timezone.utc), user_email=user_email, project_id=project_id)
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
        if self.table is not None:  # the row before the work, so a process that stops mid-job leaves a row to mark stopped
            try:
                insert_job(self.table, job_id=job.id, actor=actor, user_email=user_email, inputs=inputs, started_at=job.started_at, process=self.process,
                           project_id=project_id)
            except SQLAlchemyError as exc:
                with self.lock:
                    del self.jobs[job.id]
                shutil.rmtree(job.folder, ignore_errors=True)
                raise JobRefused(f"the job could not be registered in the jobs table, so it was not started: {str(exc).splitlines()[0]}") from exc
        args = [*self.command, source, *options, "--result", str(job.folder / "outcome.json"), "--progress", str(job.folder / PROGRESS)]
        threading.Thread(target=self._run, args=(job, args), name=f"coupon-job-{job.id}", daemon=True).start()
        return job

    def _enqueue(self, actor: str, inputs: dict, options: list[str], *, form: tuple[str, bytes] | None, coupon: str | None, values: bytes | None,
                 user_email: str | None, project_id: uuid.UUID | None) -> Job:
        """The job queue's start (ADR-0056 amendment 3): the per-user limits, the input filed in the store, the row `queued` with the
        source and the options a solver needs. The Worker hands the job to the queue once the answer says so."""
        self.sweep()
        if self.per_day is not None:
            self._within_limits(actor, user_email)
        job_id, now = uuid.uuid4(), dt.datetime.now(dt.timezone.utc)
        source = coupon
        if coupon is None:
            name, data = form if form is not None else (f"values-{job_id.hex[:8]}.json", values)
            folder = self._folder() / str(job_id)
            folder.mkdir(parents=True)
            (folder / name).write_bytes(data)
            source = input_key(str(job_id), name)
            try:
                self.store.put(source, folder / name, content_type(folder / name))
            except Exception as exc:  # boto3's own errors or the disk's: either way the solver could not read the input
                raise JobRefused(f"the job's input could not be filed in storage, so it was not queued: {str(exc).splitlines()[0]}") from exc
            finally:
                shutil.rmtree(folder, ignore_errors=True)
        try:
            insert_job(self.table, job_id=job_id, actor=actor, user_email=user_email, inputs=inputs, started_at=now, process=self.process,
                       project_id=project_id, state="queued", source=source, options=options)
        except SQLAlchemyError as exc:
            raise JobRefused(f"the job could not be registered in the jobs table, so it was not queued: {str(exc).splitlines()[0]}") from exc
        return Job(job_id, actor, inputs, None, now, state="queued", user_email=user_email, project_id=project_id,
                   snapshot={"stage": None, "done": [], "stages": [], "outputs": {}, "coupon": None, "attempt": None, "log_tail": [],
                             "message": "waiting for a free solver"})

    def _within_limits(self, actor: str, user_email: str | None) -> None:
        """The hosted tier's per-user limits (ADR-0056), from the jobs table: one running job per person, and at most `per_day` jobs
        started since midnight UTC, whatever became of them. Refused with the reason the studio shows."""
        who = user_email or f"the actor {actor}"
        running = running_job_of(self.table, user_email, actor)
        if running is not None:
            raise JobLimited(f"a job of {who} is still {running.state} ({running.id}, started {running.started_at:%H:%M} UTC); one runs at a time per person, "
                             "so wait for it to end or open it")
        midnight = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        started = jobs_started_since(self.table, user_email, actor, midnight)
        if started >= self.per_day:
            raise JobLimited(f"{who} has started {started} job(s) today, the cap of {self.per_day} per person per day (UTC); the next one can start "
                             "tomorrow, or ask for a higher cap")

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
        self._finish(job, outcome)

    def _finish(self, job: Job, outcome: dict, before_row: Callable[[], None] | None = None, **row) -> None:
        """An ended job: its files to the store when there is one, its receipt, its status here and its row (with `row`'s extra columns).
        `before_row` runs right before the row's write: a solver ends its heartbeat there, and the write carries the last sign of life."""
        state = outcome["status"] if outcome.get("status") in STATES[1:] else "stopped"
        if state in ("done", "stopped") and self.store is not None and outcome.get("coupon") and outcome.get("attempt"):
            # the files outlive this container only in the store (ADR-0050 amendment 2); a stopped run's deck, console and status files too, so the
            # fault can be read later (ADR-0030 amendment 3)
            try:
                job.stored = self._store(job, outcome)
            except Exception as exc:  # boto3 raises its own families, the disk OSError: either way the files are not durable
                if state == "done":
                    state = "stopped"
                    outcome = {**outcome, "status": "stopped", "message": f"the job ended ({outcome.get('message')}) but its files could not be copied "
                                                                          f"to storage: {str(exc).splitlines()[0]}; its result is withheld", "outputs": {}}
                else:
                    print(f"coupon job {job.id}: the stopped run's files could not be copied to storage: {str(exc).splitlines()[0]}", flush=True)
        try:
            run_id = self.recorder(job, state, outcome)
        except RecordingFailed as exc:  # no result without its receipt (ADR-0026)
            state, run_id = "stopped", None
            outcome = {**outcome, "message": f"the job ended ({outcome.get('message')}) but its run record could not be written: {exc}; "
                                             "its result is withheld", "outputs": {}}
        finished_at = dt.datetime.now(dt.timezone.utc)
        if before_row is not None:
            before_row()
            row = {**row, "heartbeat_at": dt.datetime.now(dt.timezone.utc)}
        if self.table is not None:  # the row first, then this process's state: whoever sees the job ended here finds its row ended too
            progress = job.progress() or {}
            try:
                update_job(self.table, job.id, state=state, stage=progress.get("stage"), stages_done=list(progress.get("done", [])),
                           stages=list(progress.get("stages", [])), coupon=outcome.get("coupon"), attempt=outcome.get("attempt"), message=outcome.get("message"),
                           outputs=dict(outcome.get("outputs") or {}), stored=dict(job.stored), finished_at=finished_at, run_id=run_id, log_tail=job.log_tail(),
                           **row)
            except (SQLAlchemyError, LookupError) as exc:
                outcome = {**outcome, "message": f"{outcome.get('message')}; its row in the jobs table could not be updated: {str(exc).splitlines()[0]}"}
        with self.lock:
            job.outcome, job.run_id, job.finished_at = outcome, run_id, finished_at
            job.state = state

    def _store(self, job: Job, outcome: dict) -> dict[str, str]:
        """An ended job's files into the store: every reported file by key, the package zip when there is one, and the coupon's folder."""
        coupon, attempt = outcome["coupon"], Path(outcome["attempt"]).name
        outputs = {key: repository_path(path) for key, path in (outcome.get("outputs") or {}).items()}
        outputs = {key: path for key, path in outputs.items()  # the same rule as output_file: under the repository or the job's folder
                   if path.resolve().is_relative_to(REPO.resolve()) or path.resolve().is_relative_to(job.folder.resolve())}
        package = outputs.get("package")
        archive = self._archive(job, package) if package is not None and package.is_dir() else None
        stored = store_job(self.store, coupon, attempt, outputs, archive)
        folder = self.local_root / coupon
        if folder.is_dir():
            store_folder(self.store, folder, coupon)
        return stored

    def package_archive(self, job: Job) -> Path:
        """The finished job's package folder as a zip in the job's folder, made once."""
        package = repository_path(job.outcome["outputs"]["package"])
        if not package.is_dir():
            raise FileNotFoundError(f"the package folder {job.outcome['outputs']['package']} is no longer there")
        return self._archive(job, package)

    def _archive(self, job: Job, package: Path) -> Path:
        folder = job.folder if job.folder is not None else self._folder() / str(job.id)  # a job read back from its row has no folder yet
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / f"{package.name}.zip"
        if not archive.is_file():
            shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=package.parent, base_dir=package.name)
        return archive

    def output_url(self, job: Job, key: str) -> str | None:
        """A short-lived link to a job's file in the object store, or None when the file is served from the disk: no store, a job of
        this process still running, or a file the store does not hold (ADR-0050 amendment 2); an ended job's stored files, a stopped
        run's deck and console among them, come from the store. A job read back from its row has no
        disk here, so its files come from the store while it runs too: with the job queue its solver files them as they are made."""
        if self.store is None or key not in job.stored or (job.state not in ("done", "stopped") and job.folder is not None):
            return None
        return self.store.link(job.stored[key])

    def output_file(self, job: Job, key: str) -> Path:
        """One of the job's files by its key, from the outcome once it is done or from the progress while it runs: `package` is the
        zip; every other key is the file the tool reported, which must lie under the repository or the job's folder."""
        with self.lock:
            outputs = dict((job.outcome or {}).get("outputs") or (job.progress() or {}).get("outputs") or {})
        if key not in outputs:
            raise KeyError(", ".join(sorted(outputs)) or "no file yet")
        if job.folder is None and self.store is not None and key in job.stored and key != "package":  # read back from its row: from the store
            cached = self._folder() / str(job.id) / "stored" / key / Path(job.stored[key]).name
            if not cached.is_file():
                self.store.get(job.stored[key], cached)
            return cached
        if key == "package":
            return self.package_archive(job)
        path = repository_path(outputs[key]).resolve()
        if not (path.is_relative_to(REPO.resolve()) or (job.folder is not None and path.is_relative_to(job.folder.resolve()))):
            raise PermissionError(f"the file {outputs[key]} lies outside the repository and the job's folder")
        if not path.is_file():
            raise FileNotFoundError(f"the file {outputs[key]} is no longer there")
        return path

    # --- the solver (the job queue, ADR-0056 amendment 3) ------------------------------------------------------------------

    def take(self, job_id: uuid.UUID) -> Job | None:
        """A solver's start: the queued job claimed and run in the background. The job as it stands when this solver has it already
        (running or ended); None when its row is not queued (another solver took it, it ended, or there is none), so a message
        delivered twice runs the job once."""
        if self.role != "solver":
            raise JobRefused("this container does not run queued jobs; ANISOTROPY_JOB_ROLE=solver does")
        if self.command is None:
            raise JobRefused("uv is not on PATH; a coupon job runs fea/tools/run_coupon.py through `uv run --project fea`")
        with self.lock:
            job = self.jobs.get(job_id)
            if job is not None and job.state != "queued":
                return job
        row = claim_job(self.table, job_id, self.process, dt.datetime.now(dt.timezone.utc))
        if row is None:
            return None
        folder = self._folder() / str(job_id)
        shutil.rmtree(folder, ignore_errors=True)  # a job sent back to the queue and given to this container again starts afresh
        folder.mkdir(parents=True)
        job = Job(row.id, row.actor, dict(row.inputs), folder, row.started_at, user_email=row.user_email, project_id=row.project_id)
        with self.lock:
            self.jobs[job.id] = job
        threading.Thread(target=self._solve, args=(job, row.source, list(row.options)), name=f"coupon-solve-{job.id}", daemon=True).start()
        return job

    def stop(self, job_id: uuid.UUID, reason: str) -> Job | None:
        """A solver's running job stopped with the reason (the per-job timeout); its tool is killed and the job ends `stopped`."""
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None or job.state != "running":
                return job
            job.stop_reason = reason
            process = job.process
        if process is not None and process.poll() is None:
            process.kill()
        return job

    def _solve(self, job: Job, source: str, options: list[str]) -> None:
        """A solver's job: the heartbeat from here to the row's last write, the finish's uploads included, and the running job's files
        on a thread of their own (ADR-0056 amendment 5), so neither a slow bucket nor the end of the job silences the row."""
        beat = threading.Event()
        beating = threading.Thread(target=self._heartbeat, args=(job, beat), name=f"coupon-heartbeat-{job.id}", daemon=True)
        filing = threading.Thread(target=self._live_files, args=(job, beat), name=f"coupon-live-files-{job.id}", daemon=True)
        beating.start()
        filing.start()

        def last_beat() -> None:
            """The heartbeat's end, right before the row's last write, so no beat lands after it; the filing thread ends on its own."""
            beat.set()
            beating.join()

        try:
            try:
                outcome, requeued = self._solve_steps(job, source, options)
            except Exception as exc:  # the store, the database or the disk failed around the tool: the job ends with the reason
                if job.process is not None and job.process.poll() is None:
                    job.process.kill()
                outcome, requeued = {"status": "stopped", "message": f"the solver could not run the job: {str(exc).splitlines()[0]}", "coupon": None,
                                     "attempt": None, "outputs": {}}, None
            if requeued is not None:
                last_beat()
                self._requeue(job, requeued)
                return
            if job.stop_reason is not None:
                outcome = {**outcome, "status": "stopped", "message": job.stop_reason, "outputs": {}}
            self._finish(job, outcome, last_beat, peak_memory_bytes=peak_memory())
        finally:
            last_beat()  # whatever happened above, the threads end

    def _solve_steps(self, job: Job, source: str, options: list[str]) -> tuple[dict, str | None]:
        """Run the tool with the gate; returns the outcome, and the reason when the job goes back to the queue instead."""
        argument = source
        if "/" in source:  # an object key: the form or the values as sent, filed by the API's container
            argument = str(job.folder / Path(source).name)
            self.store.get(source, Path(argument))
        shutil.rmtree(self.local_root, ignore_errors=True)  # this container's coupons are the store's, nothing else
        sync(self.store, self.local_root)  # the bulk of it outside the lock; only what changes meanwhile is fetched under it
        result, gate = job.folder / "outcome.json", job.folder / GATE
        args = [*self.command, argument, *options, "--result", str(result), "--progress", str(job.folder / PROGRESS), "--gate", str(gate)]
        with job.log.open("wb") as log:
            with naming_lock(self.table):
                sync(self.store, self.local_root)
                process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=FEA, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                with self.lock:
                    job.process = process
                waiting = self._at_gate(job, process)
            if waiting is not None:
                process.wait()
                return {}, waiting
            process.wait()
        outcome = json.loads(result.read_text(encoding="utf-8")) if result.is_file() else {
            "status": "stopped", "message": f"{Path(self.command[-1]).name} exited with code {process.returncode} and wrote no outcome; the end of "
                                            "its console says why", "coupon": None, "attempt": None, "outputs": {}}
        return outcome, None

    def _at_gate(self, job: Job, process: subprocess.Popen) -> str | None:
        """Under the naming lock: wait until the tool holds at the gate with its coupon named, or ends first. Claim the coupon on the
        job's row; with it, file the coupon's folder in the store (its new specs and codes are then what the next job reads) and let
        the tool go on. When another running job holds the coupon, refuse the tool at the gate and return why the job waits."""
        while process.poll() is None:
            progress = job.progress() or {}
            coupon = progress.get("coupon")
            if progress.get("held") and coupon:
                holder = claim_coupon(self.table, job.id, coupon)
                if holder is not None and self.sweep(force=True):  # the holder's solver may be gone: its row is stopped, and the coupon free
                    holder = claim_coupon(self.table, job.id, coupon)
                if holder is not None:
                    reason = (f"waiting: another job ({holder.id}) is solving the coupon {coupon}; this one runs when it ends, so the two do not "
                              "number the same attempt")
                    open_gate(job.folder / GATE, reason)
                    return reason
                folder = self.local_root / coupon
                if folder.is_dir():
                    store_folder(self.store, folder, coupon)
                open_gate(job.folder / GATE, GATE_GO)
                return None
            time.sleep(TICK_S)
        return None

    @staticmethod
    def _servable(job: Job, path: Path) -> bool:
        """A file the tool reported that may be handed out: it exists, under the repository or the job's folder (as `output_file`)."""
        resolved = path.resolve()
        return path.is_file() and (resolved.is_relative_to(REPO.resolve()) or (job.folder is not None and resolved.is_relative_to(job.folder.resolve())))

    def _requeue(self, job: Job, reason: str) -> None:
        """Back to the queue: the row `queued` again with the reason, its coupon let go; the solver's timer sends the job to the queue again.
        The row first, then this process's state, so whoever sees the job `queued` here finds the row so too."""
        update_job(self.table, job.id, state="queued", coupon=None, attempt=None, stage=None, stages_done=[], stages=[], outputs={}, stored={},
                   message=reason, heartbeat_at=None, log_tail=job.log_tail())
        with self.lock:
            job.state, job.process = "queued", None

    def _heartbeat(self, job: Job, stop: threading.Event) -> None:
        """Every HEARTBEAT_S from the claim to the row's last write, the finish's uploads included: the row's sign of life, stage, files,
        log and where the store keeps the files so far. The write alone, nothing else, so that a slow bucket never delays the sign of
        life (`_live_files` uploads). A failed beat is tried again at the next; one that takes longer than a beat is reported on the
        console, since the sweep stops a job silent for SILENT_AFTER (ADR-0056 amendment 5)."""
        while not stop.wait(HEARTBEAT_S):
            started = time.monotonic()
            try:
                progress = job.progress() or {}
                with self.lock:
                    stored = dict(job.stored)
                update_job(self.table, job.id, heartbeat_at=dt.datetime.now(dt.timezone.utc), stage=progress.get("stage"),
                           stages_done=list(progress.get("done", [])), stages=list(progress.get("stages", [])), attempt=progress.get("attempt"),
                           outputs=dict(progress.get("outputs") or {}), stored=stored, log_tail=job.log_tail(), message=progress.get("result"))
            except Exception as exc:  # the database for a moment: the next beat tries again
                print(f"coupon job {job.id}: a heartbeat failed: {str(exc).splitlines()[0]}", flush=True)
            took = time.monotonic() - started
            if took > HEARTBEAT_S:
                print(f"coupon job {job.id}: a heartbeat took {took:.1f} s", flush=True)

    def _live_files(self, job: Job, stop: threading.Event) -> None:
        """Every HEARTBEAT_S while the job runs: the files a browser reads while it runs (LIVE_KEYS) into the store as the tool reports
        them, each once, apart from the heartbeat (ADR-0056 amendment 5). A failed upload is tried again at the next look."""
        while not stop.wait(HEARTBEAT_S):
            try:
                progress = job.progress() or {}
                coupon, attempt = progress.get("coupon"), progress.get("attempt")
                if not (coupon and attempt):
                    continue
                for key in LIVE_KEYS:
                    reported = (progress.get("outputs") or {}).get(key)
                    if reported and key not in job.stored and self._servable(job, repository_path(reported)):
                        object_key = store_file(self.store, coupon, Path(attempt).name, key, repository_path(reported))
                        with self.lock:
                            job.stored[key] = object_key
            except Exception as exc:  # the store for a moment: the next look tries again
                print(f"coupon job {job.id}: a running job's file could not be filed: {str(exc).splitlines()[0]}", flush=True)

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
        self.refresh()
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
        self.refresh()
        done = self._studio(["coupons"], timeout_s or CHECK_TIMEOUT_S)
        if done.returncode != 0:
            raise JobRefused("the studio tool failed: " + (done.stderr.strip().splitlines() or ["no message"])[-1])
        return json.loads(done.stdout)

    def coupon_values(self, name: str, timeout_s: float | None = None) -> dict:
        """A coupon's rows as the values object; UnknownCoupon when there is no coupon of that name."""
        self.refresh()
        done = self._studio(["values", name], timeout_s or CHECK_TIMEOUT_S)
        if done.returncode != 0:
            message = (done.stderr.strip().splitlines() or ["no message"])[-1]
            if "no coupon of that name" in message:
                raise UnknownCoupon(message)
            raise JobRefused("the studio tool failed: " + message)
        return json.loads(done.stdout)


def open_gate(gate: Path, word: str) -> None:
    """The word at the tool's gate, written whole: to a neighbour first, then moved into place, so the tool never reads half of it."""
    draft = gate.with_name(gate.name + ".draft")
    draft.write_text(word, encoding="utf-8")
    os.replace(draft, gate)


def peak_memory(paths: tuple[Path, ...] = CGROUP_PEAKS) -> int | None:
    """The container's peak memory in bytes from the first cgroup file that reads, or None where none does (a machine that is not a
    container)."""
    for path in paths:
        try:
            return int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            continue
    return None
