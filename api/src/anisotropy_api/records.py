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

from sqlalchemy import CheckConstraint, DateTime, Engine, ForeignKey, String, Text, Uuid, create_engine, inspect, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
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


JOB_STATES = ("running", "done", "stopped", "refused")


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

    __table_args__ = (CheckConstraint(f"state IN ({_sql_list(JOB_STATES)})", name="jobs_state_known"),)


CONNECT_TIMEOUT_S = 5


def connect(database_url: str) -> Engine:
    """A connection pool for the API process.

    `pool_pre_ping` drops connections the server closed; the connect timeout makes an unreachable
    server a startup error within seconds instead of a long wait.
    """
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": CONNECT_TIMEOUT_S})


def check_ready(engine: Engine) -> None:
    """Fail at startup rather than at the first solve: the server answers and the runs table exists."""
    shown = make_url(engine.url).render_as_string(hide_password=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            for table in (Run.__tablename__, JobRow.__tablename__):
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

def insert_job(engine: Engine, *, job_id: uuid.UUID, actor: str, user_email: str | None, inputs: dict, started_at: dt.datetime, process: str) -> None:
    """The row of a job that has just started."""
    with Session(engine) as session:
        session.add(JobRow(id=job_id, actor=actor, user_email=user_email, state="running", inputs=inputs, started_at=started_at, process=process,
                           stages_done=[], stages=[], outputs={}, stored={}, log_tail=[]))
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
