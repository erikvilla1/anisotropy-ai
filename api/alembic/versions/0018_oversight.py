"""What the AI activity page reads that nothing kept until now (ADR-0145, step A).

Three gaps the oversight review found (docs/decisions/ADR-0145):

- A plan whose first answer the checks turned back and whose second passed kept only the second. `agent_plans.attempts` keeps each
  answer the checks turned back, with their reasons.
- A call to the model kept what it cost but nothing of what it was sent. `model_calls.sent_sha256` keeps the SHA-256 of its
  instructions, request and answer form: two calls with one fingerprint were sent the same words; the words themselves are not kept.
- Anthropic may answer a declined request with another model, and a row said which model answered but not whether that model had
  passed the assistant check (ADR-0121 amendment 8). `model_calls.checked` says so, as of the call; empty for the rows made before.
- A plan's calls were tied to it only through the run record's answer. `model_calls.plan_id` names the plan; it is emptied if the plan
  goes (with its project).

Nothing is rewritten: the new columns are empty on the rows made before. The downgrade drops them and what they hold.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_plans", sa.Column("attempts", JSONB, comment="Each answer of the model the checks turned back, with their reasons (ADR-0145)"))
    op.add_column("model_calls", sa.Column("sent_sha256", sa.String(64),
                                           comment="The fingerprint of the words sent: instructions, request, answer form (ADR-0145)"))
    op.add_column("model_calls", sa.Column("checked", sa.Boolean,
                                           comment="Whether the model that answered had passed the assistant check then (ADR-0145)"))
    op.add_column("model_calls", sa.Column("plan_id", sa.Uuid(as_uuid=True), sa.ForeignKey("agent_plans.id", ondelete="SET NULL"),
                                           comment="The plan the call was made for (ADR-0145)"))
    op.create_index("model_calls_plan", "model_calls", ["plan_id"])


def downgrade() -> None:
    op.drop_index("model_calls_plan", table_name="model_calls")
    op.drop_column("model_calls", "plan_id")
    op.drop_column("model_calls", "checked")
    op.drop_column("model_calls", "sent_sha256")
    op.drop_column("agent_plans", "attempts")
