"""Rename the actor `hermes` to `founder-agent` (ADR-0028).

Hermes is the founder's own tool and lives outside the repository, so the product's actor list
must not name it. Rows written under the old name are rewritten to the new one. This is the one
place the immutability trigger is suspended: for that single statement, inside this migration,
and re-enabled before it ends. The check constraint is dropped first (the new name is not in the
old list) and recreated with the new list.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

OLD_ACTORS = ("founder-terminal", "calculator", "hermes", "assistant", "test")
NEW_ACTORS = ("founder-terminal", "calculator", "founder-agent", "assistant", "test")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _rename(old: str, new: str, actors: tuple[str, ...]) -> None:
    op.drop_constraint("runs_actor_known", "runs", type_="check")
    op.execute("ALTER TABLE runs DISABLE TRIGGER runs_immutable")
    op.execute(f"UPDATE runs SET actor = '{new}' WHERE actor = '{old}'")
    op.execute("ALTER TABLE runs ENABLE TRIGGER runs_immutable")
    op.create_check_constraint("runs_actor_known", "runs", f"actor IN ({_sql_list(actors)})")


def upgrade() -> None:
    _rename("hermes", "founder-agent", NEW_ACTORS)


def downgrade() -> None:
    _rename("founder-agent", "hermes", OLD_ACTORS)
