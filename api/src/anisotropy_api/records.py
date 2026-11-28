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
from decimal import Decimal
from pathlib import Path

from contextlib import contextmanager

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, Engine, Float, ForeignKey, Integer, Numeric, String, Text, Uuid, create_engine, delete, func,
                        inspect, select, text, update)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .model_costs import FEATURES, ModelCall

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
    # Where a job's time goes (ADR-0056 amendment 6, migration 0009): when its solver took it up, and the seconds of each of the tool's
    # stages and of the solver's own phases (restore_s, lock_wait_s, gate_s, upload_s).
    claimed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    timings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # The answer in a few values, as the run's tool picked it from the summary our engine wrote (ADR-0109, migration 0012): what the list
    # of past analyses shows. None for a job that did not end done, one before the migration, or a result without a criterion.
    answer: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (CheckConstraint(f"state IN ({_sql_list(JOB_STATES)})", name="jobs_state_known"),)


PROJECT_KINDS = ("fea", "laminate", "wing")  # a wing since migration 0014 (ADR-0122)


class ProjectRow(Base):
    """A workspace project (ADR-0062 part 6, migration 0007): the rows of a coupon test, the draft of a laminate problem or a wing's
    description (ADR-0122, migration 0014), as the page states them, under a name the engineer gives. `content` is the page's own object; the fea package judges a coupon's rows at check
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


VERSION_MAKERS = ("you", "assistant")


class ModelVersionRow(Base):
    """A version of a project's model (ADR-0143, migration 0016; the versions of ADR-0113 kept by the server instead of the browser): the
    setup after one settled change, who made it (the engineer, or the assistant from a message of theirs) and why, what it changed in
    lines, and the run made from it with its answer as the page printed it. Numbered from 1 within the project; going back is a new
    version, so no earlier one is rewritten except to note the run made from it. `digest` tells a change from none (`setup_key`)."""

    __tablename__ = "model_versions"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    n: Mapped[int] = mapped_column(Integer, primary_key=True)
    made_by: Mapped[str] = mapped_column(String(12), nullable=False)
    why: Mapped[str | None] = mapped_column(Text)
    changes: Mapped[list] = mapped_column(JSONB, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (CheckConstraint(f"made_by IN ({_sql_list(VERSION_MAKERS)})", name="model_versions_maker_known"),
                      CheckConstraint("n >= 1", name="model_versions_n_positive"))


# A plan's states (ADR-0144, migration 0017), as `planner.STATES` names them; and those of a request that asked no model, which are not
# counted against the day's planned requests. What a plan plans on, as `planner.KINDS` names them: a repair is no kept project.
PLAN_STATES = ("proposed", "question", "refused", "unavailable", "capped", "approved", "running", "done", "stopped")
PLANS_UNCOUNTED = ("capped", "unavailable")
PLAN_KINDS = ("coupon", "plate", "wing", "repair")


class AgentPlanRow(Base):
    """A plan of the workspace's planner (ADR-0144, migration 0017): one engineer's sentence read into typed tool steps, with who asked,
    what it plans on (`kind`), its state, its steps as they run (each with its own state and note), the setup it was worked out on
    (`base`, the digest of the content or of the repair's description), the question asked back or why there is no plan, the words not
    read, who wrote it, and the job and version its approval made. A coupon's, a plate's or a wing's goes with its project and is the
    project owner's (`owns_project`); a repair's names no project, since the page holds the repair, and is its asker's (`owns_plan`)."""

    __tablename__ = "agent_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    user_email: Mapped[str | None] = mapped_column(String(320))
    actor: Mapped[str] = mapped_column(String(40), nullable=False)
    ask: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    steps: Mapped[list] = mapped_column(JSONB, nullable=False)
    base: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str | None] = mapped_column(Text)
    unread: Mapped[list] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    writer: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))
    job_id: Mapped[str | None] = mapped_column(String(64))
    version_n: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (CheckConstraint(f"state IN ({_sql_list(PLAN_STATES)})", name="agent_plans_state_known"),
                      CheckConstraint(f"kind IN ({_sql_list(PLAN_KINDS)})", name="agent_plans_kind_known"),
                      CheckConstraint("(kind = 'repair') = (project_id IS NULL)", name="agent_plans_project_by_kind"))


UPLOAD_VERDICTS = ("agrees", "differs", "incomplete", "refused")


class UploadTokenRow(Base):
    """What the connector sends with (ADR-0094 part 6, migration 0010): the SHA-256 of a token its owner created, never the token, the
    token's last characters to tell one from another, and when it was last used and cancelled. The owner is a project's: the signed-in
    email behind Cloudflare Access, or the actor locally. A cancelled token keeps its row, so the uploads it sent still name it."""

    __tablename__ = "upload_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    actor: Mapped[str] = mapped_column(String(40), nullable=False)
    user_email: Mapped[str | None] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    hint: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class PairingCodeRow(Base):
    """A one-time code that connects a user's machine to their account (ADR-0094 amendment 1, migration 0011). The signed-in page
    asks for one and hands it to the machine in a link; the machine swaps it, once and within minutes, for an upload token of its
    own. Only the code's SHA-256 is kept. `used_at` is when it was swapped and `token_id` the token it became."""

    __tablename__ = "pairing_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    actor: Mapped[str] = mapped_column(String(40), nullable=False)
    user_email: Mapped[str | None] = mapped_column(String(320))
    code_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("upload_tokens.id"))


class UploadRow(Base):
    """A bundle sent from a user's own Abaqus (ADR-0094 part 6, migration 0010): private, its owner's alone. The bundle itself is in the
    object store under `object_key`; the row keeps its SHA-256 and size, what the check found (`facts`, `in_scope`), the token it came
    with when the connector sent it, and, once it was put beside a run of ours, that job, the verdict and the comparison as
    `fea/tools/abaqus_upload.py compare` wrote it. `not_compared` says why no comparison was made. `may_train` is false unless its owner
    ticked the box. The row is deleted with the bundle when the owner asks."""

    __tablename__ = "abaqus_uploads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    actor: Mapped[str] = mapped_column(String(40), nullable=False)
    user_email: Mapped[str | None] = mapped_column(String(320))
    token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("upload_tokens.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    units: Mapped[str] = mapped_column(String(20), nullable=False)
    job: Mapped[str | None] = mapped_column(Text)
    coupon: Mapped[str | None] = mapped_column(Text)
    in_scope: Mapped[bool] = mapped_column(Boolean, nullable=False)
    facts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    may_train: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("jobs.id"))
    verdict: Mapped[str | None] = mapped_column(String(12))
    comparison: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    compared_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    not_compared: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(f"verdict IS NULL OR verdict IN ({_sql_list(UPLOAD_VERDICTS)})", name="abaqus_uploads_verdict_known"),
        CheckConstraint("(verdict IS NULL) = (comparison IS NULL)", name="abaqus_uploads_verdict_has_comparison"),
    )


class ModelCallRow(Base):
    """One call to the language model and what it cost (ADR-0120, migration 0013): when, who asked, for what, which model answered,
    the tokens it was billed for by kind, and the cost at the list's prices on the day. Read it through the views
    `model_costs_by_person`, `model_costs_by_feature` and `model_costs_by_day`, or `python -m anisotropy_api.cost_report`.
    Rows are only added; the run a row names may be cleared (ADR-0026 amendment 2), and the row stays with that link empty."""

    __tablename__ = "model_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    called_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="When the model answered")
    user_email: Mapped[str | None] = mapped_column(String(320), comment="Who asked: the signed-in email; empty when nobody was signed in")
    actor: Mapped[str] = mapped_column(String(40), nullable=False, comment="Which client sent the request: studio, browser, assistant ...")
    feature: Mapped[str] = mapped_column(String(40), nullable=False, comment="What the call was for, such as explain_result")
    model: Mapped[str] = mapped_column(String(80), nullable=False, comment="The model that answered")
    effort: Mapped[str | None] = mapped_column(String(10), comment="The effort the call asked for")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, comment="Tokens read, billed at the input price")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False,
                                               comment="Tokens written, billed at the output price; the hidden thinking is part of them")
    thinking_tokens: Mapped[int | None] = mapped_column(Integer, comment="The part of output_tokens that was hidden thinking, as the API reports it")
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), comment="Tokens read from the prompt cache")
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), comment="Tokens written to the prompt cache")
    answer_characters: Mapped[int] = mapped_column(Integer, nullable=False, comment="Length of the answer we received, in characters")
    stop_reason: Mapped[str | None] = mapped_column(String(20), comment="How the call ended: end_turn, max_tokens, refusal")
    seconds: Mapped[float] = mapped_column(Float, nullable=False, comment="How long the call took")
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), comment="US dollars at the list prices of prices_as_of; empty when not priced")
    prices_as_of: Mapped[str | None] = mapped_column(String(10), comment="The date of the price list the cost was taken from")
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"),
                                                     comment="The run record of the request the call answered")
    attempts: Mapped[list | None] = mapped_column(JSONB(none_as_null=True), comment="Each attempt's tokens when there was more than one")

    __table_args__ = (
        CheckConstraint(f"feature IN ({_sql_list(FEATURES)})", name="model_calls_feature_known"),
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0 AND cache_read_tokens >= 0 AND cache_write_tokens >= 0 "
                        "AND answer_characters >= 0", name="model_calls_counts_not_negative"),
        CheckConstraint("thinking_tokens IS NULL OR thinking_tokens BETWEEN 0 AND output_tokens", name="model_calls_thinking_within_output"),
        {"comment": "One row per call to the language model: who asked, for what, the tokens billed and the cost (ADR-0120)"},
    )


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
            for table in (Run.__tablename__, JobRow.__tablename__, ProjectRow.__tablename__, UploadTokenRow.__tablename__, UploadRow.__tablename__,
                          ModelCallRow.__tablename__):
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


def model_calls_since(engine: Engine, user_email: str, since: dt.datetime) -> int:
    """How many calls to the model the signed-in person's requests made at or after `since` (ADR-0120), whatever the client, for the
    day's cap (ADR-0139)."""
    statement = (select(func.count()).select_from(ModelCallRow)
                 .where(ModelCallRow.called_at >= since, ModelCallRow.user_email == user_email))
    with Session(engine) as session:
        return session.scalar(statement) or 0


def record_model_calls(engine: Engine, calls: list[ModelCall], *, actor: str, user_email: str | None, run_id: uuid.UUID | None) -> int:
    """One row per call (ADR-0120), in one transaction; returns how many. A database failure raises; the caller decides."""
    if not calls:
        return 0
    with Session(engine) as session:
        session.add_all(ModelCallRow(called_at=c.answered_at, user_email=user_email, actor=actor, feature=c.feature, model=c.model, effort=c.effort,
                                     input_tokens=c.input_tokens, output_tokens=c.output_tokens, thinking_tokens=c.thinking_tokens,
                                     cache_read_tokens=c.cache_read_tokens, cache_write_tokens=c.cache_write_tokens,
                                     answer_characters=c.answer_characters, stop_reason=c.stop_reason, seconds=c.seconds, cost_usd=c.cost_usd,
                                     prices_as_of=c.prices_as_of, run_id=run_id, attempts=list(c.attempts) if c.attempts else None)
                        for c in calls)
        session.commit()
    return len(calls)


EVERYONE = "*"  # in place of an owner's email: no narrowing by owner (the local API, which has no sign-in; ADR-0104)


def _owned(statement, column, user_email: str | None):
    """The statement narrowed to the rows of one owner (ADR-0104): the signed-in email that made them, None for the rows made with no
    one signed in, EVERYONE for no narrowing."""
    if user_email == EVERYONE:
        return statement
    return statement.where(column.is_(None) if user_email is None else column == user_email)


def fetch_run(engine: Engine, run_id: uuid.UUID) -> Run | None:
    with Session(engine) as session:
        return session.get(Run, run_id)


def list_runs(engine: Engine, *, actor: str | None = None, endpoint: str | None = None, status: str | None = None,
              since: dt.datetime | None = None, until: dt.datetime | None = None, limit: int = 50, user_email: str | None = EVERYONE) -> list[Run]:
    """The newest runs first, narrowed by the given filters; `since` is inclusive, `until` exclusive; `user_email` keeps one owner's."""
    statement = _owned(select(Run).order_by(Run.created_at.desc(), Run.id).limit(limit), Run.user_email, user_email)
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


def list_jobs(engine: Engine, limit: int = 50, user_email: str | None = EVERYONE) -> list[JobRow]:
    """The newest jobs first; `user_email` keeps one owner's (ADR-0104)."""
    with Session(engine) as session:
        return list(session.scalars(_owned(select(JobRow).order_by(JobRow.started_at.desc(), JobRow.id).limit(limit), JobRow.user_email, user_email)))


def coupon_owners(engine: Engine) -> set[tuple[str, str | None]]:
    """Each coupon a job has named, with each owner whose job named it (the signed-in email, None for none)."""
    with Session(engine) as session:
        return {(coupon, email) for coupon, email in session.execute(select(JobRow.coupon, JobRow.user_email).where(JobRow.coupon.is_not(None)).distinct())}


def coupons_of(owners: set[tuple[str, str | None]], user_email: str | None) -> set[str]:
    """The names of the coupons that owner's jobs have run and no one else's have (ADR-0104): what the list of coupons shows them
    and what they may reopen. A coupon's folder holds the rows of whoever ran it last, so a name two people have run is offered to
    neither."""
    by_coupon: dict[str, set[str | None]] = {}
    for coupon, email in owners:
        by_coupon.setdefault(coupon, set()).add(email)
    return {coupon for coupon, emails in by_coupon.items() if emails == {user_email}}


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


def add_version(engine: Engine, project_id: uuid.UUID, *, made_by: str, why: str | None, changes: list[str], content: dict, digest: str,
                now: dt.datetime) -> tuple[ModelVersionRow, bool]:
    """A new version of a project's model, numbered after its last (True); the last one again (False) when the setup is the same. The
    project's row is locked while the number is chosen, so two changes at once never take one number."""
    with Session(engine, expire_on_commit=False) as session:
        session.execute(select(ProjectRow.id).where(ProjectRow.id == project_id).with_for_update())
        last = session.scalars(select(ModelVersionRow).where(ModelVersionRow.project_id == project_id).order_by(ModelVersionRow.n.desc()).limit(1)).first()
        if last is not None and last.digest == digest:
            return last, False
        row = ModelVersionRow(project_id=project_id, n=(last.n if last else 0) + 1, made_by=made_by, why=why, changes=list(changes),
                              content=content, digest=digest, created_at=now)
        session.add(row)
        session.commit()
        return row, True


def list_versions(engine: Engine, project_id: uuid.UUID, limit: int = 50) -> list[ModelVersionRow]:
    """A project's last versions, the oldest of them first."""
    with Session(engine, expire_on_commit=False) as session:
        rows = list(session.scalars(select(ModelVersionRow).where(ModelVersionRow.project_id == project_id)
                                    .order_by(ModelVersionRow.n.desc()).limit(limit)))
    return rows[::-1]


def mark_version_run(engine: Engine, project_id: uuid.UUID, n: int, *, job_id: str, result: dict | None) -> ModelVersionRow | None:
    """The run made from a version, and its answer once read; None when the project has no such version."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(ModelVersionRow, (project_id, n))
        if row is None:
            return None
        row.job_id, row.result = job_id, result
        session.commit()
        return row


def _apply_setup_in(session: Session, project_id: uuid.UUID, *, base: str, digest_of, content: dict, made_by: str, why: str | None,
                    changes: list[str], version_digest: str, now: dt.datetime) -> tuple[ProjectRow, ModelVersionRow] | None:
    """`apply_setup` inside a transaction the caller holds, so a plan's approval is one with it (ADR-0144)."""
    row = session.scalars(select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()).first()
    if row is None or digest_of(dict(row.content)) != base:
        return None
    row.content, row.updated_at = content, now
    last = session.scalars(select(ModelVersionRow).where(ModelVersionRow.project_id == project_id).order_by(ModelVersionRow.n.desc()).limit(1)).first()
    version = ModelVersionRow(project_id=project_id, n=(last.n if last else 0) + 1, made_by=made_by, why=why, changes=list(changes),
                              content=content, digest=version_digest, created_at=now)
    session.add(version)
    return row, version


def apply_setup(engine: Engine, project_id: uuid.UUID, *, base: str, digest_of, content: dict, made_by: str, why: str | None,
                changes: list[str], version_digest: str, now: dt.datetime) -> tuple[ProjectRow, ModelVersionRow] | None:
    """A project's content replaced by a changed setup and kept as a new version, in one transaction, only while the content is still
    the one the change was worked out on (`digest_of(content) == base`); None when it has changed since."""
    with Session(engine, expire_on_commit=False) as session:
        kept = _apply_setup_in(session, project_id, base=base, digest_of=digest_of, content=content, made_by=made_by, why=why,
                               changes=changes, version_digest=version_digest, now=now)
        if kept is None:
            return None
        session.commit()
        return kept


# -------------------------------------------------------------------------------- the workspace's plans (ADR-0144)

def add_plan(engine: Engine, **fields) -> AgentPlanRow:
    """A plan as the planner made it, or a request that came to none (`question`, `refused`, `unavailable`, `capped`)."""
    with Session(engine, expire_on_commit=False) as session:
        row = AgentPlanRow(**fields)
        session.add(row)
        session.commit()
        return row


def fetch_plan(engine: Engine, project_id: uuid.UUID, plan_id: uuid.UUID) -> AgentPlanRow | None:
    """A plan of a project, by its id; None when there is none or it is another project's. Whose a plan is, is its project's
    (`owns_project`), which the caller checks first."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(AgentPlanRow, plan_id)
        return row if row is not None and row.project_id == project_id else None


def owns_plan(row: AgentPlanRow, actor: str, user_email: str | None) -> bool:
    """Whose a repair's plan is, with no project to ask: the signed-in email behind Access; locally, with no email, the actor that asked."""
    if user_email is not None:
        return row.user_email == user_email
    return row.user_email is None and row.actor == actor


def fetch_repair_plan(engine: Engine, plan_id: uuid.UUID) -> AgentPlanRow | None:
    """A repair's plan by its id; None when there is none or the plan is a project's. Whose it is (`owns_plan`) is the caller's to check."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(AgentPlanRow, plan_id)
        return row if row is not None and row.kind == "repair" and row.project_id is None else None


def update_plan(engine: Engine, plan_id: uuid.UUID, **fields) -> AgentPlanRow:
    """A few columns of a plan moved: its state and steps as its approval runs them, its job."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(AgentPlanRow, plan_id)
        if row is None:
            raise LookupError(f"no row for plan {plan_id}")
        for name, value in fields.items():
            setattr(row, name, value)
        session.commit()
        return row


def edit_plan(engine: Engine, plan_id: uuid.UUID, edit, now: dt.datetime) -> AgentPlanRow | None:
    """A plan's steps and state changed by `edit(steps, job_id) -> state` with its row locked, so two reports at once never lose one;
    `job_id` is the job the row names as it then stands, or None. Whatever `edit` raises leaves the row as it was, and so do a
    state of None and an edit that leaves the steps and the state as they were: nothing is written then, the row's time of change
    neither. None when there is no such plan."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.scalars(select(AgentPlanRow).where(AgentPlanRow.id == plan_id).with_for_update()).first()
        if row is None:
            return None
        steps = json.loads(json.dumps(row.steps))
        state = edit(steps, row.job_id)
        if state is not None and (steps != row.steps or state != row.state):  # an edit that changes nothing writes nothing
            row.steps, row.state, row.updated_at = steps, state, now
        session.commit()
        return row


def settle_plan_runs(engine: Engine, settle, now: dt.datetime, *, kinds: tuple[str, ...], ended: tuple[str, ...],
                     job_id: uuid.UUID | str | None = None, state: str | None = None, since: dt.datetime | None = None,
                     lost_before: dt.datetime | None = None) -> int:
    """The run of every plan of `kinds` whose job has ended, settled from the job's own outcome with the plan's row locked (ADR-0144
    amendment 2): `settle(steps, job_state) -> state` is given each plan whose run is still `running` and whose job is in one of the
    `ended` states, and the steps it changed are written back with the state it answers (None changes nothing). With `job_id`, the
    plans of that job alone, and with `state` the job's state as its own process knows it (a job kept in no table). Without one,
    every such plan approved at or after `since` whose job ended at or after it: a sweep is for an end that was missed, not for the
    plans kept before the server settled runs, which it does not read; and among them every plan whose job has no record at all,
    once it was approved before `lost_before`, given to `settle` with a state of None (an approval writes the job's id a moment
    before it starts the job). How many were settled. A row another request holds is left for the next look when every plan is
    swept, and waited for when one job is named. What `settle` raises for one plan is said on the console with the plan's id, that
    row is left as it was, and the others are settled all the same."""
    statement = select(AgentPlanRow).where(AgentPlanRow.kind.in_(kinds), AgentPlanRow.state.in_(("running", "done", "stopped")),
                                           AgentPlanRow.job_id.is_not(None), AgentPlanRow.steps.contains([{"tool": "run", "state": "running"}]))
    if job_id is not None:
        statement = statement.where(AgentPlanRow.job_id == str(job_id))
    elif since is not None:  # a job ends within hours of its plan's approval, so an older plan is none of a sweep's: it is not read
        statement = statement.where(AgentPlanRow.approved_at >= since)
    settled = 0
    with Session(engine) as session:
        for row in session.scalars(statement.with_for_update(skip_locked=job_id is None)):
            job_state = state
            if job_state is None:
                try:
                    job = session.get(JobRow, uuid.UUID(row.job_id))
                except ValueError:
                    continue
                job_state = None if job is None else job.state
                if job is not None and since is not None and (job.finished_at is None or job.finished_at < since):
                    continue
                if job is None and (lost_before is None or row.approved_at is None or row.approved_at >= lost_before):
                    continue  # no record of its job, and its approval may still be about to start it
            if job_state is not None and job_state not in ended:
                continue
            try:
                steps = json.loads(json.dumps(row.steps))
                after = settle(steps, job_state)
            except Exception as exc:  # noqa: BLE001  one plan that cannot be settled (steps kept in another shape) is said and left
                print(f"plan {row.id}: its run was not settled: {exc.__class__.__name__}: {str(exc).splitlines()[0] if str(exc) else ''}", flush=True)
                continue
            if after is not None:
                row.steps, row.state, row.updated_at = steps, after, now
                settled += 1
        session.commit()
    return settled


def plans_since(engine: Engine, user_email: str, since: dt.datetime) -> int:
    """How many planned requests the signed-in person made at or after `since`, whatever the project or the client (ADR-0144): each one
    that asked the model, kept as a plan or not, and none that asked none (`PLANS_UNCOUNTED`)."""
    statement = (select(func.count()).select_from(AgentPlanRow)
                 .where(AgentPlanRow.user_email == user_email, AgentPlanRow.created_at >= since, AgentPlanRow.state.not_in(PLANS_UNCOUNTED)))
    with Session(engine) as session:
        return session.scalar(statement) or 0


class PlanTaken(Exception):
    """A plan's approval refused: it is no plan to approve any more (approved already, or never proposed), or the project changed since
    it was made. The message says which, in the words the page shows."""


STALE_PLAN = "The model changed since this plan was made. Ask again for a new plan."


def approve_plan(engine: Engine, plan_id: uuid.UUID, project_id: uuid.UUID, *, base: str, digest_of, content: dict | None, why: str,
                 changes: list[str], version_digest: str | None, steps: list, now: dt.datetime,
                 versioned: bool = True) -> tuple[AgentPlanRow, ProjectRow, ModelVersionRow | None]:
    """A plan approved in one transaction (ADR-0144): its row locked and still `proposed`, the project still on the setup the plan was
    worked out on (`base`), the changed setup (`content`) kept with a new version by the assistant with the ask as why, and the plan
    `approved` with its steps and the version's number. A plan with no change keeps no version, and neither does a wing's
    (`versioned` false): a wing's versions are kept in the browser (ADR-0122), so its content alone is replaced. PlanTaken when it is no
    plan to approve or the project changed since; nothing is written then."""
    with Session(engine, expire_on_commit=False) as session:
        plan = session.scalars(select(AgentPlanRow).where(AgentPlanRow.id == plan_id, AgentPlanRow.project_id == project_id)
                               .with_for_update()).first()
        if plan is None or plan.state != "proposed":
            raise PlanTaken("This plan was approved already, or it is not a plan to approve. Ask again for a new one.")
        if plan.base != base:
            raise PlanTaken(STALE_PLAN)
        version = None
        if content is not None and not versioned:
            project = session.scalars(select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()).first()
            if project is None or digest_of(dict(project.content)) != base:
                raise PlanTaken(STALE_PLAN)
            project.content, project.updated_at = content, now
        elif content is not None:
            kept = _apply_setup_in(session, project_id, base=base, digest_of=digest_of, content=content, made_by="assistant", why=why,
                                   changes=changes, version_digest=version_digest or "", now=now)
            if kept is None:
                raise PlanTaken(STALE_PLAN)
            project, version = kept
        else:
            project = session.scalars(select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()).first()
            if project is None or digest_of(dict(project.content)) != base:
                raise PlanTaken(STALE_PLAN)
        plan.state, plan.steps, plan.approved_at, plan.updated_at = "approved", steps, now, now
        plan.version_n = None if version is None else version.n
        session.commit()
        return plan, project, version


STALE_REPAIR = "The repair changed since this plan was made. Ask again for a new plan."


def approve_repair_plan(engine: Engine, plan_id: uuid.UUID, *, base: str, steps: list, now: dt.datetime) -> AgentPlanRow:
    """A repair's plan approved, once: its row locked, still `proposed` and worked out on the description the approval carries
    (`base`, its digest), and set `approved` with its steps. There is no project to change: the page holds the repair, and the approval
    answers the description the plan makes of it. PlanTaken when it is no plan to approve, or the description is another; nothing is
    written then."""
    with Session(engine, expire_on_commit=False) as session:
        plan = session.scalars(select(AgentPlanRow).where(AgentPlanRow.id == plan_id, AgentPlanRow.kind == "repair").with_for_update()).first()
        if plan is None or plan.state != "proposed":
            raise PlanTaken("This plan was approved already, or it is not a plan to approve. Ask again for a new one.")
        if plan.base != base:
            raise PlanTaken(STALE_REPAIR)
        plan.state, plan.steps, plan.approved_at, plan.updated_at = "approved", steps, now, now
        session.commit()
        return plan


def fetch_version(engine: Engine, project_id: uuid.UUID, n: int | None) -> ModelVersionRow | None:
    """One version of a project's model by its number; None for none."""
    if n is None:
        return None
    with Session(engine, expire_on_commit=False) as session:
        return session.get(ModelVersionRow, (project_id, n))


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


# ------------------------------------------------------------------------------- the uploads from Abaqus (ADR-0094 part 6, step 5)

def _by_owner(statement, row, user_email: str | None, actor: str):
    """A project's rule for any owned table: the signed-in email behind Access; locally, with no email, the actor."""
    return statement.where(row.user_email == user_email) if user_email is not None else statement.where(row.user_email.is_(None), row.actor == actor)


def insert_upload_token(engine: Engine, *, token_id: uuid.UUID, actor: str, user_email: str | None, name: str, token_sha256: str, hint: str,
                        now: dt.datetime) -> UploadTokenRow:
    with Session(engine, expire_on_commit=False) as session:
        row = UploadTokenRow(id=token_id, actor=actor, user_email=user_email, name=name, token_sha256=token_sha256, hint=hint, created_at=now)
        session.add(row)
        session.commit()
        return row


def list_upload_tokens(engine: Engine, *, actor: str, user_email: str | None) -> list[UploadTokenRow]:
    """The requester's tokens, newest first, the cancelled ones among them."""
    statement = _by_owner(select(UploadTokenRow).order_by(UploadTokenRow.created_at.desc(), UploadTokenRow.id), UploadTokenRow, user_email, actor)
    with Session(engine, expire_on_commit=False) as session:
        return list(session.scalars(statement))


def insert_pairing_code(engine: Engine, *, code_id: uuid.UUID, actor: str, user_email: str | None, code_sha256: str, now: dt.datetime,
                        expires_at: dt.datetime) -> PairingCodeRow:
    """A new code for the requester. Their earlier codes that were never swapped end now, so one code stands at a time."""
    with Session(engine, expire_on_commit=False) as session:
        session.execute(_by_owner(update(PairingCodeRow).where(PairingCodeRow.used_at.is_(None), PairingCodeRow.expires_at > now), PairingCodeRow,
                                  user_email, actor).values(expires_at=now))
        row = PairingCodeRow(id=code_id, actor=actor, user_email=user_email, code_sha256=code_sha256, created_at=now, expires_at=expires_at)
        session.add(row)
        session.commit()
        return row


def fetch_pairing_code(engine: Engine, code_sha256: str, now: dt.datetime) -> PairingCodeRow | None:
    """The code with that digest when it could still be swapped, unchanged; None otherwise."""
    with Session(engine, expire_on_commit=False) as session:
        return session.scalars(select(PairingCodeRow).where(PairingCodeRow.code_sha256 == code_sha256, PairingCodeRow.used_at.is_(None),
                                                            PairingCodeRow.expires_at > now)).first()


def claim_pairing_code(engine: Engine, code_sha256: str, now: dt.datetime) -> PairingCodeRow | None:
    """The code with that digest when it was never swapped and has not ended, marked as swapped now; None otherwise. The update names
    the unused row, so of two requests with one code one gets it."""
    with Session(engine, expire_on_commit=False) as session:
        claimed = session.execute(update(PairingCodeRow).where(PairingCodeRow.code_sha256 == code_sha256, PairingCodeRow.used_at.is_(None),
                                                               PairingCodeRow.expires_at > now).values(used_at=now).returning(PairingCodeRow.id)).first()
        session.commit()
        return None if claimed is None else session.get(PairingCodeRow, claimed[0])


def name_pairing_token(engine: Engine, code_id: uuid.UUID, token_id: uuid.UUID) -> None:
    """Write down which token a swapped code became."""
    with Session(engine) as session:
        session.execute(update(PairingCodeRow).where(PairingCodeRow.id == code_id).values(token_id=token_id))
        session.commit()


def live_upload_tokens(engine: Engine, *, actor: str, user_email: str | None) -> int:
    """How many of the requester's tokens are not cancelled."""
    statement = _by_owner(select(func.count()).select_from(UploadTokenRow).where(UploadTokenRow.revoked_at.is_(None)), UploadTokenRow, user_email, actor)
    with Session(engine) as session:
        return session.scalar(statement)


def revoke_upload_token(engine: Engine, token_id: uuid.UUID, *, actor: str, user_email: str | None, now: dt.datetime) -> UploadTokenRow | None:
    """The requester's token, cancelled (once: a second call leaves the first time); None when there is none of theirs by that id."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(UploadTokenRow, token_id)
        if row is None or not owns_project(row, actor, user_email):
            return None
        if row.revoked_at is None:
            row.revoked_at = now
            session.commit()
        return row


def use_upload_token(engine: Engine, token_sha256: str, now: dt.datetime) -> UploadTokenRow | None:
    """The token with that digest when it is not cancelled, marked as used now; None for an unknown or a cancelled one."""
    with Session(engine, expire_on_commit=False) as session:
        row = session.scalars(select(UploadTokenRow).where(UploadTokenRow.token_sha256 == token_sha256, UploadTokenRow.revoked_at.is_(None))).first()
        if row is None:
            return None
        row.last_used_at = now
        session.commit()
        return row


def insert_upload(engine: Engine, **fields) -> UploadRow:
    with Session(engine, expire_on_commit=False) as session:
        row = UploadRow(**fields)
        session.add(row)
        session.commit()
        return row


def fetch_upload(engine: Engine, upload_id: uuid.UUID) -> UploadRow | None:
    with Session(engine, expire_on_commit=False) as session:
        return session.get(UploadRow, upload_id)


def list_uploads(engine: Engine, *, actor: str, user_email: str | None, everyone: bool = False, limit: int = 50,
                 job_id: uuid.UUID | None = None) -> list[UploadRow]:
    """The requester's uploads, newest first; `everyone` lists every owner's, which is for a founder alone (ADR-0094 part 6). With
    `job_id`, only those that stand beside that run of ours."""
    statement = select(UploadRow).order_by(UploadRow.created_at.desc(), UploadRow.id).limit(limit)
    if not everyone:
        statement = _by_owner(statement, UploadRow, user_email, actor)
    if job_id is not None:
        statement = statement.where(UploadRow.job_id == job_id)
    with Session(engine, expire_on_commit=False) as session:
        return list(session.scalars(statement))


def count_uploads(engine: Engine, *, actor: str, user_email: str | None) -> int:
    with Session(engine) as session:
        return session.scalar(_by_owner(select(func.count()).select_from(UploadRow), UploadRow, user_email, actor))


def update_upload(engine: Engine, upload_id: uuid.UUID, **fields) -> UploadRow:
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(UploadRow, upload_id)
        if row is None:
            raise LookupError(f"no row for upload {upload_id}")
        for name, value in fields.items():
            setattr(row, name, value)
        session.commit()
        return row


def delete_upload(engine: Engine, upload_id: uuid.UUID) -> None:
    with Session(engine) as session:
        session.execute(delete(UploadRow).where(UploadRow.id == upload_id))
        session.commit()


def latest_done_job(engine: Engine, *, coupon: str, actor: str, user_email: str | None) -> JobRow | None:
    """The requester's newest job of that coupon that is done, or None: the run of ours an upload is put beside when none is named."""
    statement = _by_person(select(JobRow).where(JobRow.coupon == coupon, JobRow.state == "done").order_by(JobRow.started_at.desc(), JobRow.id).limit(1),
                           user_email, actor)
    with Session(engine, expire_on_commit=False) as session:
        return session.scalars(statement).first()


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
