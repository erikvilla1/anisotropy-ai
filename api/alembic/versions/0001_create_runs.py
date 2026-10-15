"""Create the runs table and make its rows immutable (ADR-0026).

Revision ID: 0001
Revises: none
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from anisotropy_api.records import STATUSES

# The list as it stood at this revision. Migration 0003 renames one entry; this file must keep
# creating what it created at the time, so it does not import the live ACTORS.
ACTORS = ("founder-terminal", "calculator", "hermes", "assistant", "test")

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("inputs", JSONB, nullable=False),
        sa.Column("inputs_sha256", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("api_version", sa.String(40), nullable=False),
        sa.Column("git_commit", sa.String(40)),
        sa.Column("response", JSONB),
        sa.Column("error", sa.Text),
        sa.Column("supersedes_run_id", sa.Uuid(as_uuid=True), sa.ForeignKey("runs.id")),
        sa.Column("llm_provider", sa.String(40)),
        sa.Column("llm_model_version", sa.String(80)),
        sa.CheckConstraint(f"actor IN ({_sql_list(ACTORS)})", name="runs_actor_known"),
        sa.CheckConstraint(f"status IN ({_sql_list(STATUSES)})", name="runs_status_known"),
        sa.CheckConstraint("(status = 'solved') = (response IS NOT NULL)", name="runs_solved_has_response"),
        sa.CheckConstraint("(status = 'rejected') = (error IS NOT NULL)", name="runs_rejected_has_error"),
    )
    op.create_index("runs_created_at_idx", "runs", ["created_at"])
    op.create_index("runs_actor_idx", "runs", ["actor"])
    # Rows are never edited or deleted. A correction is a new row that names the old one.
    op.execute(
        """
        CREATE FUNCTION runs_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'runs are never edited or deleted (ADR-0026); write a new run with supersedes_run_id';
        END
        $$;
        """
    )
    op.execute(
        "CREATE TRIGGER runs_immutable BEFORE UPDATE OR DELETE ON runs "
        "FOR EACH ROW EXECUTE FUNCTION runs_are_immutable();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER runs_immutable ON runs;")
    op.execute("DROP FUNCTION runs_are_immutable();")
    op.drop_index("runs_actor_idx", table_name="runs")
    op.drop_index("runs_created_at_idx", table_name="runs")
    op.drop_table("runs")
