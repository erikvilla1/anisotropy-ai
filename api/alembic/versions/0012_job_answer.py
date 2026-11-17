"""A job keeps its answer in a few values, for the list of past analyses (ADR-0109).

The list a person reads their past analyses from (GET /v1/coupon-jobs) said which coupon ran and when, and for the result only the
line that counts the values agreeing with the reference solver. Whether the coupon held, at what factor and which ply fails first was
in each run's fields file alone, megabytes to fetch per row. The row gains `answer`: what the run's tool picked from the summary our
engine wrote (`anisotropy_fea.fields.run_answer`): the basis, the criterion that governs, whether a ply fails at the applied loading,
the factor, and the ply with its angle and face. Null for a job that ended before this, one that did not end done, or a result
without a failure criterion.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("answer", JSONB))


def downgrade() -> None:
    op.drop_column("jobs", "answer")
