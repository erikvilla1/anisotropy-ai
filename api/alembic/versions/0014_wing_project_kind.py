"""A wing is a project of its own kind (ADR-0122).

The wing workspace kept one wing in the browser alone (ADR-0118): cleared with the site's data, invisible from another machine, and
one at a time. A wing is now kept like a coupon or a laminate, in the projects table under the signed-in email, its description the
row's content. The kinds the check constraint knows grow by one; no row changes, the constraint is dropped and recreated with the new
list. The downgrade refuses while a wing project exists, because the old constraint would not admit it.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-20
"""

from alembic import op
from sqlalchemy import text

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

OLD_KINDS = ("fea", "laminate")
NEW_KINDS = (*OLD_KINDS, "wing")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _recreate(kinds: tuple[str, ...]) -> None:
    op.drop_constraint("projects_kind_known", "projects", type_="check")
    op.create_check_constraint("projects_kind_known", "projects", f"kind IN ({_sql_list(kinds)})")


def upgrade() -> None:
    _recreate(NEW_KINDS)


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM projects WHERE kind = 'wing'")).scalar()
    if count:
        raise RuntimeError(f"the projects table holds {count} wing project(s); the old constraint would not admit them, so this migration "
                           "is not undone over them")
    _recreate(OLD_KINDS)
