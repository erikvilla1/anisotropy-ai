"""The jobs table (ADR-0050 amendment 2, ADR-0056).

A coupon job's status lived in the API process and was gone when it stopped; a container stops and restarts without notice.
This table keeps every job's status: `running` when it starts, then `done`, `stopped` or `refused` with what the tool reported,
the files by key, where the object store keeps them (`stored`) and the receipt's `run_id`. Rows here change, unlike the run
records, which stay the immutable receipt (ADR-0026). `process` names the API process that ran the job, so a new process marks
`stopped` the rows a stopped process never saw end. The downgrade refuses while the table holds jobs: their statuses would be lost.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

STATES = ("running", "done", "stopped", "refused")


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("user_email", sa.String(320)),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("stage", sa.Text),
        sa.Column("stages_done", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("stages", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("coupon", sa.Text),
        sa.Column("attempt", sa.Text),
        sa.Column("message", sa.Text),
        sa.Column("inputs", JSONB, nullable=False),
        sa.Column("outputs", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("stored", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("run_id", sa.Uuid(as_uuid=True), sa.ForeignKey("runs.id")),
        sa.Column("log_tail", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("process", sa.String(36), nullable=False),
        sa.CheckConstraint("state IN (" + ", ".join(f"'{state}'" for state in STATES) + ")", name="jobs_state_known"),
    )
    op.create_index("jobs_started_at_idx", "jobs", ["started_at"])
    op.create_index("jobs_state_idx", "jobs", ["state"])


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM jobs")).scalar()
    if count:
        raise RuntimeError(f"the jobs table holds {count} job(s); their statuses would be lost, so this migration is not undone over them")
    op.drop_index("jobs_state_idx", table_name="jobs")
    op.drop_index("jobs_started_at_idx", table_name="jobs")
    op.drop_table("jobs")
