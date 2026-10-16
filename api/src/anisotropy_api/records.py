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
import subprocess
import uuid
from pathlib import Path

from sqlalchemy import CheckConstraint, DateTime, Engine, ForeignKey, String, Text, Uuid, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Who triggered a run. Adding one is a migration, so a new consumer is a reviewed change.
# `founder-agent` is the founder's own tooling outside this repository, an outside client of the API (ADR-0028).
ACTORS = ("founder-terminal", "calculator", "founder-agent", "assistant", "test")
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

    __table_args__ = (
        CheckConstraint(f"actor IN ({_sql_list(ACTORS)})", name="runs_actor_known"),
        CheckConstraint(f"status IN ({_sql_list(STATUSES)})", name="runs_status_known"),
        CheckConstraint("(status = 'solved') = (response IS NOT NULL)", name="runs_solved_has_response"),
        CheckConstraint("(status = 'rejected') = (error IS NOT NULL)", name="runs_rejected_has_error"),
    )


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
            if not inspect(connection).has_table(Run.__tablename__):
                raise RuntimeError(
                    f"The database at {shown} has no '{Run.__tablename__}' table. "
                    "Apply the migrations: cd api && uv run alembic upgrade head"
                )
    except OperationalError as exc:
        raise RuntimeError(f"Cannot reach the run records database at {shown}: {exc}") from exc


def inputs_digest(inputs: dict) -> str:
    """SHA-256 of the request in canonical JSON, so identical requests share a digest."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def git_commit() -> str | None:
    """The repository commit the API runs from, or None when there is none (a plain install)."""
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
                              capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    commit = done.stdout.strip()
    return commit if done.returncode == 0 and len(commit) == 40 else None


def record_run(engine: Engine, *, actor: str, endpoint: str, inputs: dict, engine_version: str, api_version: str,
               git_commit: str | None, response: dict | None = None, error: str | None = None) -> uuid.UUID:
    """Insert one row and return its id. A database failure raises; the caller decides what that means."""
    run = Run(actor=actor, endpoint=endpoint, status="solved" if error is None else "rejected", inputs=inputs,
              inputs_sha256=inputs_digest(inputs), engine_version=engine_version, api_version=api_version,
              git_commit=git_commit, response=response, error=error)
    with Session(engine) as session:
        session.add(run)
        session.commit()
        return run.id


def fetch_run(engine: Engine, run_id: uuid.UUID) -> Run | None:
    with Session(engine) as session:
        return session.get(Run, run_id)
