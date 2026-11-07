"""The projects table (ADR-0062, part 6).

A workspace project, the rows of a coupon test or the draft of a laminate problem under a name the engineer gives, lived in the
browser alone: cleared with the site's data, invisible from another machine. This table keeps every project as the page states it:
its kind, its name, its content as one JSON object, the form version and the unit system the content was stated in, the designation
the last setup check derived and that check's run, and who owns it: the signed-in email behind Cloudflare Access, or the actor
locally. The jobs table gains `project_id`, so a project lists its runs. Rows here change, unlike the run records (ADR-0026). The
downgrade refuses while the table holds projects: they would be lost.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

KINDS = ("fea", "laminate")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("name", sa.Text, nullable=False, server_default=""),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("user_email", sa.String(320)),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("form_version", sa.String(20)),
        sa.Column("units", sa.String(20)),
        sa.Column("designation", sa.Text),
        sa.Column("last_check_run_id", sa.Uuid(as_uuid=True), sa.ForeignKey("runs.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN (" + ", ".join(f"'{kind}'" for kind in KINDS) + ")", name="projects_kind_known"),
    )
    op.create_index("projects_owner_idx", "projects", ["user_email", "updated_at"])
    op.create_index("projects_actor_idx", "projects", ["actor", "updated_at"])
    op.add_column("jobs", sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id")))


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM projects")).scalar()
    if count:
        raise RuntimeError(f"the projects table holds {count} project(s); they would be lost, so this migration is not undone over them")
    op.drop_column("jobs", "project_id")
    op.drop_index("projects_actor_idx", table_name="projects")
    op.drop_index("projects_owner_idx", table_name="projects")
    op.drop_table("projects")
