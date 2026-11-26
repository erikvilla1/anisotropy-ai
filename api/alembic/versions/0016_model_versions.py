"""Versions of a project's model, kept by the server (ADR-0143).

The versions of ADR-0113 lived in the browser that made them: lost with the site's data, unseen from another machine, and out of reach
of anything but the page. The workspace's tools (ADR-0143) change a model on the server, so its versions are kept there too: one row per
version of a project's setup, numbered from 1 within the project, with who made it (the engineer, or the assistant from a message of
theirs) and why, what it changed in lines, the setup itself, a digest that tells a change from none, and the run made from it with its
answer as the page printed it. A version goes with its project. The downgrade refuses while the table holds versions: they would be lost.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

MAKERS = ("you", "assistant")


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("n", sa.Integer, primary_key=True),
        sa.Column("made_by", sa.String(12), nullable=False),
        sa.Column("why", sa.Text),
        sa.Column("changes", JSONB, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(64)),
        sa.Column("result", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("made_by IN (" + ", ".join(f"'{m}'" for m in MAKERS) + ")", name="model_versions_maker_known"),
        sa.CheckConstraint("n >= 1", name="model_versions_n_positive"),
    )


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM model_versions")).scalar()
    if count:
        raise RuntimeError(f"the model_versions table holds {count} version(s); they would be lost, so this migration is not undone over them")
    op.drop_table("model_versions")
