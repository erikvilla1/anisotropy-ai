"""The workspace's plans (ADR-0144, build step 2).

One sentence of an engineer's is read by one call to the model into a plan of typed tool steps, which the server checks, the engineer
approves once, and the server then applies as a version, checks and runs. Each plan is one row: whose it is and what it was asked, its
state, its steps with each one's state and note as the page reports them, the setup it was worked out on (`base`), the question asked
back or why there is no plan, the words not read, who wrote it, and the run and version its approval made. A plan's `kind` says what
it plans on: a coupon or a plate (a kept `fea` project), a wing (a kept `wing` project) or a repair, which is no kept project: the page
holds its description, so a repair's plan names no project and is its asker's (build step 5). A plan goes with its project. The day's
planned requests of a person are counted from these rows, every kind together (ADR-0144, 30 a day by default).

Each call to the model the planner makes is a row of `model_calls` with the feature `plan_steps`, so that table's check of the features
it allows is replaced by one that names it too. The weekly view of the guards (0015, ADR-0139) counts a request past the day's planned
requests as capped, as it counts one past the day's calls. The downgrade puts the old check and view back and refuses while the table
holds plans, or while a call of the new feature is kept: either would be lost or refused.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-26
"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

# What a call is for, as `anisotropy_api.model_costs.FEATURES` names them on the day of this migration; BEFORE as 0013 named them.
BEFORE = ("explain_setup", "explain_result", "explain_laminate", "propose_changes", "read_question", "answer_question", "choose_tools")
FEATURES = (*BEFORE, "plan_steps")
# Why a plan was not made: the person's planned requests today reached the cap (`anisotropy_api.planner.PLAN_LIMIT_REASON` on the day of
# this migration); such a request asked no model.
PLAN_CAPPED = "the day's limit of planned requests for this sign-in is reached"
# A plan's states, as `anisotropy_api.planner.STATES` names them.
STATES = ("proposed", "question", "refused", "unavailable", "capped", "approved", "running", "done", "stopped")
# What a plan plans on, as `anisotropy_api.planner.KINDS` names them: a repair's plan alone has no project.
KINDS = ("coupon", "plate", "wing", "repair")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _features(values: tuple[str, ...]) -> None:
    op.drop_constraint("model_calls_feature_known", "model_calls", type_="check")
    op.create_check_constraint("model_calls_feature_known", "model_calls", f"feature IN ({_sql_list(values)})")


def _guards_view() -> tuple[str, str]:
    """0015's view of the guards as it made it, and the same view counting a request past the day's planned requests as capped."""
    path = Path(__file__).with_name("0015_assistant_guards.py")
    spec = importlib.util.spec_from_file_location("revision_0015", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old, new = (reason.replace("'", "''") for reason in (module.CAPPED, PLAN_CAPPED))
    capped = f"coalesce(response->>'reason' = '{old}', false) AS capped"
    assert module.GUARDS.count(capped) == 1, "0015's view no longer reads the cap's reason as this migration expects"
    both = f"coalesce(response->>'reason' IN ('{old}', '{new}'), false) AS capped"
    before = module.GUARDS.replace("CREATE VIEW", "CREATE OR REPLACE VIEW", 1)
    return before, before.replace(capped, both)


def upgrade() -> None:
    op.create_table(
        "agent_plans",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("user_email", sa.String(320)),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("ask", sa.Text, nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("steps", JSONB, nullable=False),
        sa.Column("base", sa.String(64), nullable=False),
        sa.Column("question", sa.Text),
        sa.Column("unread", JSONB, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("writer", sa.String(20), nullable=False),
        sa.Column("model", sa.String(80)),
        sa.Column("job_id", sa.String(64)),
        sa.Column("version_n", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"state IN ({_sql_list(STATES)})", name="agent_plans_state_known"),
        sa.CheckConstraint(f"kind IN ({_sql_list(KINDS)})", name="agent_plans_kind_known"),
        sa.CheckConstraint("(kind = 'repair') = (project_id IS NULL)", name="agent_plans_project_by_kind"),
    )
    op.create_index("agent_plans_project", "agent_plans", ["project_id", "created_at"])
    op.create_index("agent_plans_person_day", "agent_plans", ["user_email", "created_at"])
    _features(FEATURES)
    op.execute(_guards_view()[1])


def downgrade() -> None:
    connection = op.get_bind()
    plans = connection.execute(text("SELECT count(*) FROM agent_plans")).scalar()
    if plans:
        raise RuntimeError(f"the agent_plans table holds {plans} plan(s); they would be lost, so this migration is not undone over them")
    calls = connection.execute(text("SELECT count(*) FROM model_calls WHERE feature = 'plan_steps'")).scalar()
    if calls:
        raise RuntimeError(f"model_calls holds {calls} call(s) of plan_steps, which the earlier check refuses; this migration is not undone over them")
    _features(BEFORE)
    op.execute(_guards_view()[0])
    op.drop_index("agent_plans_person_day", table_name="agent_plans")
    op.drop_index("agent_plans_project", table_name="agent_plans")
    op.drop_table("agent_plans")
