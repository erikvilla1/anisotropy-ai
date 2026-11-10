"""The job queue (ADR-0056 stage 3, amendment 3; ADR-0050 amendment 3).

With the queue on, the API's container no longer runs a coupon job: it files the input in the object store, writes the row
`queued` and hands the job to the queue, and a solver container of its own takes it up. The row gains what that container needs and
what tells a live job from a lost one:

- `queued`, a state before `running`;
- `source`, the coupon's name or the object key of the input as sent, and `options`, the tool's options;
- `heartbeat_at`, rewritten every few seconds by the container running the job, so a job whose container is gone is seen and
  stopped;
- `peak_memory_bytes`, the container's peak memory when the job ended, read from its cgroup: one job per container, so it is the
  job's own (the API process included);
- one running job per coupon, by a unique index on `coupon` over the running rows: two containers never number attempts of one
  coupon at once.

The downgrade refuses while a row is `queued` (the old state check would not hold it).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

OLD_STATES = ("running", "done", "stopped", "refused")
STATES = ("queued", *OLD_STATES)


def _states(states: tuple[str, ...]) -> str:
    return "state IN (" + ", ".join(f"'{state}'" for state in states) + ")"


def upgrade() -> None:
    op.drop_constraint("jobs_state_known", "jobs", type_="check")
    op.create_check_constraint("jobs_state_known", "jobs", _states(STATES))
    op.add_column("jobs", sa.Column("source", sa.Text))
    op.add_column("jobs", sa.Column("options", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column("jobs", sa.Column("peak_memory_bytes", sa.BigInteger))
    op.create_index("jobs_one_running_job_per_coupon", "jobs", ["coupon"], unique=True, postgresql_where=sa.text("state = 'running'"))


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM jobs WHERE state = 'queued'")).scalar()
    if count:
        raise RuntimeError(f"the jobs table holds {count} queued job(s); the old state check cannot hold them, so this migration is not undone over them")
    op.drop_index("jobs_one_running_job_per_coupon", table_name="jobs")
    op.drop_column("jobs", "peak_memory_bytes")
    op.drop_column("jobs", "heartbeat_at")
    op.drop_column("jobs", "options")
    op.drop_column("jobs", "source")
    op.drop_constraint("jobs_state_known", "jobs", type_="check")
    op.create_check_constraint("jobs_state_known", "jobs", _states(OLD_STATES))
