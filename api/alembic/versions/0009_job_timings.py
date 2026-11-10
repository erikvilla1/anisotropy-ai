"""Where a hosted job's time goes (ADR-0056 amendment 6).

The first two-user session (2026-11-08) took 90 to 140 s per job where the same job takes 13 to 26 s on one machine, and the row said
only when the job was queued, last heard from and finished. The row gains `claimed_at`, when a solver took the queued job up, and
`timings`, the seconds of each of the tool's stages (the setup check, the input, ... the outputs) and of the solver's own phases around
the tool (restore_s, lock_wait_s, gate_s, upload_s), written at every heartbeat and at the end.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("claimed_at", sa.DateTime(timezone=True)))
    op.add_column("jobs", sa.Column("timings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade() -> None:
    op.drop_column("jobs", "timings")
    op.drop_column("jobs", "claimed_at")
