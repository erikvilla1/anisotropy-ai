"""Add the actor `studio` (ADR-0051).

The website's coupon studio is a new client of the API: it checks setups, starts coupon jobs and reads their files. Every
request it sends is recorded under its own actor, so the list of known actors in the check constraint grows by one. No row
changes; the constraint is dropped and recreated with the new list. The downgrade refuses while a `studio` row exists, because
rows are never rewritten (ADR-0026) and the old constraint would not admit them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28
"""

from alembic import op
from sqlalchemy import text

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

OLD_ACTORS = ("founder-terminal", "calculator", "founder-agent", "assistant", "test")
NEW_ACTORS = (*OLD_ACTORS, "studio")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _recreate(actors: tuple[str, ...]) -> None:
    op.drop_constraint("runs_actor_known", "runs", type_="check")
    op.create_check_constraint("runs_actor_known", "runs", f"actor IN ({_sql_list(actors)})")


def upgrade() -> None:
    _recreate(NEW_ACTORS)


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM runs WHERE actor = 'studio'")).scalar()
    if count:
        raise RuntimeError(f"{count} run(s) were recorded by the studio; rows are never rewritten, so this migration cannot be undone")
    _recreate(OLD_ACTORS)
