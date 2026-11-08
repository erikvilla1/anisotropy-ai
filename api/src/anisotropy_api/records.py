"""Run records: the table every solve is written to (ADR-0026). Nothing here computes a result.

A row is the receipt of one request: the inputs as received, the versions that answered, the
response or the rejection, and who asked. Rows are never updated or deleted; the database enforces
that with a trigger created by the first migration. A correction is a new row whose
`supersedes_run_id` names the old one.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import uuid
from collections.abc import Mapping
from pathlib import Path

from contextlib import contextmanager

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Engine, ForeignKey, String, Text, Uuid, create_engine, func, inspect, select, text, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Who triggered a run. Adding one is a migration, so a new consumer is a reviewed change.
# `founder-agent` is the founder's own tooling outside this repository, an outside client of the API (ADR-0028);
# `studio` is the website's coupon studio (ADR-0051, migration 0004); `browser` is for the hosted tier's clients (ADR-0056, migration 0005).
ACTORS = ("founder-terminal", "calculator", "founder-agent", "assistant", "test", "studio", "browser")
STATUSES = ("solved", "rejected")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    actor: Mapped[str] = mapped_column(String(40), nullable=False)
    # The route that answered, e.g. /v1/cases/solve; says how to read `inputs` and `response`.
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    # The request exactly as received: {"case": {...}} or {"toml": "..."}.
    # none_as_null: a Python None is SQL NULL, not the JSON value null, so the check constraints see it.
    inputs: Mapped[dict] = mapped_column(JSONB(none_as_null=True), nullable=False)
    inputs_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    api_version: Mapped[str] = mapped_column(String(40), nullable=False)
    git_commit: Mapped[str | None] = mapped_column(String(40))
    # The CaseResponse body as returned (results, criteria, material provenance, comparison, problems).
    response: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    # The 422 detail when the engine or the contract rejected the request.
    error: Mapped[str | None] = mapped_column(Text)
    supersedes_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("runs.id"))
    # Filled only when a language model drafted the inputs (planned assistant).
    llm_provider: Mapped[str | None] = mapped_column(String(40))
    llm_model_version: Mapped[str | None] = mapped_column(String(80))
    # The email Cloudflare Access verified for the request (ADR-0056, migration 0005); empty with Access off, and for a service token.
    user_email: Mapped[str | None] = mapped_column(String(320))

    __table_args__ = (
        CheckConstraint(f"actor IN ({_sql_list(ACTORS)})", name="runs_actor_known"),
        CheckConstraint(f"status IN ({_sql_list(STATUSES)})", name="runs_status_known"),
        CheckConstraint("(status = 'solved') = (response IS NOT NULL)", name="runs_solved_has_response"),
        CheckConstraint("(status = 'rejected') = (error IS NOT NULL)", name="runs_rejected_has_error"),
    )


JOB_STATES = ("queued", "running", "done", "stopped", "refused")  # queued since migration 0008 (the job queue)


class JobRow(Base):
    """A coupon job's status (ADR-0050 amendment 2, migration 0006): what GET /v1/coupon-jobs answers once the process that ran the
    job is gone. Unlike a run, a row changes: `running` when the job starts, then `done`, `stopped` or `refused` with what the tool
    reported, the files by key, where the store keeps them (`stored`) and the receipt's `run_id`. The receipt itself stays the
    immutable run record (ADR-0026). `process` names the API process that ran the job, so a new process can tell which running
    rows it never saw end."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    actor: Mapped[str] = mapped_column(String(40), nullable=False)
    user_email: Mapped[str | None] = mapped_column(String(320))
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    stage: Mapped[str | None] = mapped_column(Text)
    stages_done: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    stages: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    coupon: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    outputs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    stored: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("runs.id"))
    log_tail: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    process: Mapped[str] = mapped_column(String(36), nullable=False)
    # The project the job was started for (ADR-0062 part 6, migration 0007); None for a job started without one.
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"))
    # The job queue (ADR-0056 amendment 3, migration 0008): what a solver container needs to run a queued job (the coupon's name or
    # the input's object key, and the tool's options), the last sign of life of the container running it, and that container's peak
    # memory when the job ended.
    source: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    heartbeat_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    peak_memory_bytes: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (CheckConstraint(f"state IN ({_sql_list(JOB_STATES)})", name="jobs_state_known"),)


PROJECT_KINDS = ("fea", "laminate")


class ProjectRow(Base):
    """A workspace project (ADR-0062 part 6, migration 0007): the rows of a coupon test or the draft of a laminate problem, as the page
    states them, under a name the engineer gives. `content` is the page's own object; the fea package judges a coupon's rows at check
    time as always (ADR-0051), and the designation it derived is written back here with the check's run. The owner is the signed-in
    email behind Cloudflare Access (ADR-0056), or, locally, the actor. Rows here change; the runs stay the immutable receipts."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    actor: Mapped[str] = mapped_column(String(40), nullable=False)
    user_email: Mapped[str | None] = mapped_column(String(320))
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    form_version: Mapped[str | None] = mapped_column(String(20))
    units: Mapped[str | None] = mapped_column(String(20))
    designation: Mapped[str | None] = mapped_column(Text)
    last_check_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("runs.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (CheckConstraint(f"kind IN ({_sql_list(PROJECT_KINDS)})", name="projects_kind_known"),)


CONNECT_TIMEOUT_S = 5
# TCP keepalives and the user timeout, libpq's own parameters: a connection whose network went away under it (a container's can,
# ADR-0056 amendment 5) fails within about half a minute instead of waiting for an answer that never comes. A system without one of
# them ignores it.
KEEPALIVE = {"keepalives": 1, "keepalives_idle": 15, "keepalives_interval": 5, "keepalives_count": 3, "tcp_user_timeout": 30_000}


def connect(database_url: str) -> Engine:
    """A connection pool for the API process.

    `pool_pre_ping` drops connections the server closed; the connect timeout makes an unreachable
    server a startup error within seconds instead of a long wait; KEEPALIVE bounds a wait on a dead connection.
    """
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": CONNECT_TIMEOUT_S, **KEEPALIVE})


def check_ready(engine: Engine) -> None:
    """Fail at startup rather than at the first solve: the server answers and the runs table exists."""
    shown = make_url(engine.url).render_as_string(hide_password=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            for table in (Run.__tablename__, JobRow.__tablename__, ProjectRow.__tablename__):
                if not inspect(connection).has_table(table):
                    raise RuntimeError(
                        f"The database at {shown} has no '{table}' table. "
                        "Apply the migrations: cd api && uv run alembic upgrade head"
                    )
    except OperationalError as exc:
        raise RuntimeError(f"Cannot reach the run records database at {shown}: {exc}") from exc


def inputs_digest(inputs: dict) -> str:
    """SHA-256 of the request in canonical JSON, so identical requests share a digest."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


COMMIT_VARIABLE = "ANISOTROPY_GIT_COMMIT"  # the commit a container image was built from; there is no .git inside it (ADR-0056)
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def git_commit(environ: Mapping[str, str] | None = None, cwd: Path | None = None) -> str | None:
    """The repository commit the API runs from: the checkout's HEAD when the code sits in one, else the commit named by
    ANISOTROPY_GIT_COMMIT (the solver image sets it at build), else None (a plain install). A variable that is set but is not a
    40-digit commit is refused with its name (ADR-0003)."""
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd or Path(__file__).resolve().parent,
                              capture_output=True, text=True, timeout=5, check=False)
        found = done.stdout.strip() if done.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        found = ""
    if COMMIT.match(found):
        return found
    named = (os.environ if environ is None else environ).get(COMMIT_VARIABLE, "").strip().lower()
    if not named:
        return None
    if not COMMIT.match(named):
        raise RuntimeError(f"{COMMIT_VARIABLE} must be the 40-digit commit the image was built from, not {named!r}")
    return named


def record_run(engine: Engine, *, actor: str, endpoint: str, inputs: dict, engine_version: str, api_version: str,
               git_commit: str | None, response: dict | None = None, error: str | None = None,
               llm_provider: str | None = None, llm_model_version: str | None = None, user_email: str | None = None) -> uuid.UUID:
    """Insert one row and return its id. A database failure raises; the caller decides what that means. `llm_provider` and
    `llm_model_version` name the language model whose draft the response holds (ADR-0052); None when the template wrote it.
    `user_email` is the signed-in email Cloudflare Access verified (ADR-0056); None with Access off."""
    run = Run(actor=actor, endpoint=endpoint, status="solved" if error is None else "rejected", inputs=inputs,
              inputs_sha256=inputs_digest(inputs), engine_version=engine_version, api_version=api_version,
              git_commit=git_commit, response=response, error=error, llm_provider=llm_provider, llm_model_version=llm_model_version,
              user_email=user_email)
    with Session(engine) as session:
        session.add(run)
        session.commit()
        return run.id


def fetch_run(engine: Engine, run_id: uuid.UUID) -> Run | None:
    with Session(engine) as session:
        return session.get(Run, run_id)


def list_runs(engine: Engine, *, actor: str | None = None, endpoint: str | None = None, status: str | None = None,
              since: dt.datetime | None = None, until: dt.datetime | None = None, limit: int = 50) -> list[Run]:
    """The newest runs first, narrowed by the given filters; `since` is inclusive, `until` exclusive."""
    statement = select(Run).order_by(Run.created_at.desc(), Run.id).limit(limit)
    if actor is not None:
        statement = statement.where(Run.actor == actor)
    if endpoint is not None:
        statement = statement.where(Run.endpoint == endpoint)
    if status is not None:
        statement = statement.where(Run.status == status)
    if since is not None:
        statement = statement.where(Run.created_at >= since)
    if until is not None:
        statement = statement.where(Run.created_at < until)
    with Session(engine) as session:
        return list(session.scalars(statement))


# ------------------------------------------------------------------------------------------- the jobs table (ADR-0050 amendment 2)

def insert_job(engine: Engine, *, job_id: uuid.UUID, actor: str, user_email: str | None, inputs: dict, started_at: dt.datetime, process: str,
               project_id: uuid.UUID | None = None, state: str = "running", source: str | None = None, options: list[str] | None = None) -> None:
    """The row of a job that has just started, or, with the queue, just been queued with its `source` and `options` (migration 0008);
    `project_id` names the project it was started for, when one was (ADR-0062 part 6)."""
    with Session(engine) as session:
        session.add(JobRow(id=job_id, actor=actor, user_email=user_email, state=state, inputs=inputs, started_at=started_at, process=process,
                           stages_done=[], stages=[], outputs={}, stored={}, log_tail=[], project_id=project_id, source=source, options=list(options or [])))
        session.commit()


def update_job(engine: Engine, job_id: uuid.UUID, **fields) -> None:
    """The row as the job now stands: its state, stage, what it reported, where the store keeps the files, its receipt's id."""
    with Session(engine) as session:
        row = session.get(JobRow, job_id)
        if row is None:
            raise LookupError(f"no row for coupon job {job_id}")
        for name, value in fields.items():
            setattr(row, name, value)
        session.commit()


def fetch_job(engine: Engine, job_id: uuid.UUID) -> JobRow | None:
    with Session(engine) as session:
        return session.get(JobRow, job_id)


def list_jobs(engine: Engine, limit: int = 50) -> list[JobRow]:
    """The newest jobs first."""
    with Session(engine) as session:
        return list(session.scalars(select(JobRow).order_by(JobRow.started_at.desc(), JobRow.id).limit(limit)))


# ------------------------------------------------------------------------------------------- the projects table (ADR-0062 part 6)

class ProjectTaken(Exception):
    """The project exists and belongs to someone else: answered as if it did not exist, so no project is confirmed to a stranger."""


class KindChanged(Exception):
    """A project's kind never changes: a coupon project does not become a laminate one."""


def owns_project(row: ProjectRow, actor: str, user_email: str | None) -> bool:
    """Behind Access the owner is the signed-in email; locally, with no email, the actor that made it."""
    if user_email is not None:
        return row.user_email == user_email
    return row.user_email is None and row.actor == actor


def upsert_project(engine: Engine, *, project_id: uuid.UUID, kind: str, name: str, actor: str, user_email: str | None, content: dict,
                   form_version: str | None, units: str | None, now: dt.datetime) -> tuple[ProjectRow, bool]:
    """The project as the page states it now: created when new (True), replaced when it is the requester's own."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(ProjectRow, project_id)
        created = row is None
        if row is None:
            row = ProjectRow(id=project_id, kind=kind, actor=actor, user_email=user_email, created_at=now)
            session.add(row)
        elif not owns_project(row, actor, user_email):
            raise ProjectTaken(str(project_id))
        elif row.kind != kind:
            raise KindChanged(f"project {project_id} is a {row.kind} project; it does not become a {kind} one")
        row.name, row.content, row.form_version, row.units, row.updated_at = name, content, form_version, units, now
        session.commit()
        return row, created


def fetch_project(engine: Engine, project_id: uuid.UUID) -> ProjectRow | None:
    with Session(engine, expire_on_commit=False) as session:
        return session.get(ProjectRow, project_id)


def list_projects(engine: Engine, *, actor: str, user_email: str | None, limit: int = 50) -> list[ProjectRow]:
    """The requester's projects, the last changed first: by signed-in email behind Access, by actor locally."""
    statement = select(ProjectRow).order_by(ProjectRow.updated_at.desc(), ProjectRow.id).limit(limit)
    if user_email is not None:
        statement = statement.where(ProjectRow.user_email == user_email)
    else:
        statement = statement.where(ProjectRow.user_email.is_(None), ProjectRow.actor == actor)
    with Session(engine, expire_on_commit=False) as session:
        return list(session.scalars(statement))


def update_project(engine: Engine, project_id: uuid.UUID, **fields) -> ProjectRow:
    """A few columns of a project moved: its name, or the designation and the run of its last check."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(ProjectRow, project_id)
        if row is None:
            raise LookupError(f"no row for project {project_id}")
        for name, value in fields.items():
            setattr(row, name, value)
        session.commit()
        return row


def project_jobs(engine: Engine, project_id: uuid.UUID, limit: int = 50) -> list[JobRow]:
    """The jobs started for a project, newest first."""
    with Session(engine, expire_on_commit=False) as session:
        return list(session.scalars(select(JobRow).where(JobRow.project_id == project_id).order_by(JobRow.started_at.desc(), JobRow.id).limit(limit)))


# -------------------------------------------------------------------------------- the per-user limits (ADR-0056, stage 5)

def _by_person(statement, user_email: str | None, actor: str):
    """A person is the signed-in email when Access gave one; without it, the actor stands for the person (the local API, a service token)."""
    return statement.where(JobRow.user_email == user_email) if user_email is not None else statement.where(JobRow.user_email.is_(None), JobRow.actor == actor)


def running_job_of(engine: Engine, user_email: str | None, actor: str) -> JobRow | None:
    """The person's job still `running` or `queued`, in any process, or None (ADR-0056, the per-user limits)."""
    with Session(engine) as session:
        return session.scalars(_by_person(select(JobRow).where(JobRow.state.in_(("queued", "running"))), user_email, actor).limit(1)).first()


def jobs_started_since(engine: Engine, user_email: str | None, actor: str, since: dt.datetime) -> int:
    """How many jobs the person started at or after `since`, whatever became of them."""
    with Session(engine) as session:
        return session.scalar(_by_person(select(func.count()).select_from(JobRow).where(JobRow.started_at >= since), user_email, actor))


def stop_orphans(engine: Engine, reason: str) -> int:
    """Every row still `running` when a process starts belongs to a process that stopped before its job ended (one job at a time, one
    process at a time in the beta): it is marked `stopped` with the reason. Returns how many."""
    with Session(engine) as session:
        rows = list(session.scalars(select(JobRow).where(JobRow.state == "running")))
        now = dt.datetime.now(dt.timezone.utc)
        for row in rows:
            row.state, row.message, row.finished_at = "stopped", reason, now
        session.commit()
        return len(rows)


# ----------------------------------------------------------------------------------- the job queue (ADR-0056 amendment 3)

NAMING_LOCK = 0x616E69736F  # the advisory lock taken while a job names its coupon: "aniso" in ASCII, any fixed number would do


def claim_job(engine: Engine, job_id: uuid.UUID, process: str, now: dt.datetime) -> JobRow | None:
    """The queued job, now `running` in this process with its first heartbeat; None when the row is not queued (taken already, ended,
    or unknown), so a message delivered twice runs the job once."""
    with Session(engine, expire_on_commit=False) as session:
        claimed = session.execute(update(JobRow).where(JobRow.id == job_id, JobRow.state == "queued")
                                  .values(state="running", process=process, heartbeat_at=now, message=None).returning(JobRow.id)).first()
        session.commit()
        return None if claimed is None else session.get(JobRow, job_id)


def claim_coupon(engine: Engine, job_id: uuid.UUID, coupon: str) -> JobRow | None:
    """Name the running job's coupon on its row. None when that worked; the running job that holds the coupon when another does, which
    the unique index over the running rows refuses (migration 0008)."""
    try:
        with Session(engine) as session:
            session.execute(update(JobRow).where(JobRow.id == job_id).values(coupon=coupon))
            session.commit()
            return None
    except IntegrityError:
        with Session(engine, expire_on_commit=False) as session:
            return session.scalars(select(JobRow).where(JobRow.coupon == coupon, JobRow.state == "running", JobRow.id != job_id)).first()


@contextmanager
def naming_lock(engine: Engine):
    """One job at a time names its coupon (the designation's codes and the attempt's number are read from the coupons there are), held
    for one transaction by PostgreSQL's transaction-level advisory lock, which works through a transaction-mode pooler and is let go
    when the transaction ends, a lost connection included."""
    with engine.connect() as connection, connection.begin():
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": NAMING_LOCK})
        yield


def sweep_stale(engine: Engine, now: dt.datetime, *, silent_after: dt.timedelta, queued_after: dt.timedelta) -> int:
    """Stop the jobs nothing will finish: a running job whose container has sent no heartbeat for `silent_after` (the container is
    gone), and a job queued longer than `queued_after` (its message was lost or ran out of retries). Returns how many."""
    with Session(engine) as session:
        silent = session.execute(update(JobRow).where(JobRow.state == "running", JobRow.heartbeat_at.is_not(None), JobRow.heartbeat_at < now - silent_after)
                                 .values(state="stopped", finished_at=now, message=f"the solver running this job stopped answering for "
                                                                                   f"{silent_after.total_seconds():g} s, so it did not finish; start it again"))
        waiting = session.execute(update(JobRow).where(JobRow.state == "queued", JobRow.started_at < now - queued_after)
                                  .values(state="stopped", finished_at=now, message=f"no solver took this job up in {queued_after.total_seconds() / 60:g} minutes; "
                                                                                    "start it again"))
        session.commit()
        return silent.rowcount + waiting.rowcount


def queue_position(engine: Engine, job_id: uuid.UUID, queued_at: dt.datetime) -> int:
    """How many queued jobs were queued before this one."""
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(JobRow).where(JobRow.state == "queued", JobRow.started_at < queued_at, JobRow.id != job_id))
