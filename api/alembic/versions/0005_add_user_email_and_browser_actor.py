"""Add the signed-in email to the run records and the actor `browser` (ADR-0026 amendment 1, ADR-0056).

Behind Cloudflare Access the API knows who sent a request: the email Access verified. It goes in a new nullable column,
`user_email`; locally, with Access off, it stays empty and nothing changes. The hosted tier's clients may send the actor
`browser`, so the list of known actors in the check constraint grows by one; no row changes. The downgrade refuses while a row
carries an email or the new actor, because rows are never rewritten (ADR-0026) and dropping the column would lose what they say.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

OLD_ACTORS = ("founder-terminal", "calculator", "founder-agent", "assistant", "test", "studio")
NEW_ACTORS = (*OLD_ACTORS, "browser")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _recreate(actors: tuple[str, ...]) -> None:
    op.drop_constraint("runs_actor_known", "runs", type_="check")
    op.create_check_constraint("runs_actor_known", "runs", f"actor IN ({_sql_list(actors)})")


def upgrade() -> None:
    op.add_column("runs", sa.Column("user_email", sa.String(320)))  # the longest address RFC 5321 allows
    _recreate(NEW_ACTORS)


def downgrade() -> None:
    held = op.get_bind().execute(text("SELECT count(*) FROM runs WHERE user_email IS NOT NULL OR actor = 'browser'")).scalar()
    if held:
        raise RuntimeError(f"{held} run(s) carry a signed-in email or the actor browser; rows are never rewritten, so this migration cannot be undone")
    _recreate(OLD_ACTORS)
    op.drop_column("runs", "user_email")
