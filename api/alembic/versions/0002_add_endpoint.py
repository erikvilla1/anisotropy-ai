"""Add the endpoint column: which route answered the run (ADR-0026).

Every row before this revision was written by POST /v1/cases/solve, the only recording endpoint
until now, so existing rows get that value through the column default; the default is then
dropped so new rows must say which route answered. Adding a column with a default is DDL and
does not fire the immutability trigger.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("endpoint", sa.String(80), nullable=False, server_default="/v1/cases/solve"))
    op.alter_column("runs", "endpoint", server_default=None)
    op.create_index("runs_endpoint_idx", "runs", ["endpoint"])


def downgrade() -> None:
    op.drop_index("runs_endpoint_idx", table_name="runs")
    op.drop_column("runs", "endpoint")
