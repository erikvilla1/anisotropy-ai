"""What each call to the language model cost, and who asked (ADR-0119).

The assistant's calls (ADR-0052) came back with what the provider billed for them, and that was thrown away. `model_calls` keeps one
row per call: when, the signed-in email that asked and the client, what the call was for, the model that answered and the effort
asked for, the tokens billed by kind (the hidden thinking within the output), the length of the answer received, how it ended, how
long it took, the cost at the list's prices on the day, and the run record of the request. Three views read it in plain columns:

- `model_costs_by_person`: each month, each person: calls, what they used, tokens, cost.
- `model_costs_by_feature`: each week, each feature: tokens, the share of the output that was hidden thinking, cost per call, both
  against the four weeks before, and a flag when either is more than 30% above.
- `model_costs_by_day`: each day and model, the counts and the cost to set beside the provider's own usage page.

Months, weeks (from Monday) and days are in UTC, as the provider's usage and invoices are. A row's run may be cleared (ADR-0026
amendment 2); the row stays and its link is emptied. The downgrade refuses while the table holds a row: the history would be lost.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# What a call is for, as `anisotropy_api.model_costs.FEATURES` names them on the day of this migration.
FEATURES = ("explain_setup", "explain_result", "explain_laminate", "propose_changes", "read_question", "answer_question", "choose_tools")
JUMP = 1.3  # a week more than 30% above the four before it is flagged

BY_PERSON = """
CREATE VIEW model_costs_by_person AS
SELECT to_char(called_at AT TIME ZONE 'UTC', 'YYYY-MM') AS month,
       coalesce(user_email, '(no sign-in: ' || actor || ')') AS person,
       count(*) AS calls,
       string_agg(DISTINCT feature, ', ' ORDER BY feature) AS features,
       sum(input_tokens) AS input_tokens,
       sum(output_tokens) AS output_tokens,
       sum(thinking_tokens) AS thinking_tokens,
       sum(cost_usd) AS cost_usd,
       count(*) FILTER (WHERE cost_usd IS NULL) AS unpriced_calls,
       max(called_at) AS last_call_at
FROM model_calls
GROUP BY 1, 2
ORDER BY month DESC, cost_usd DESC NULLS LAST, person
"""

BY_FEATURE = f"""
CREATE VIEW model_costs_by_feature AS
WITH weekly AS (
    SELECT date_trunc('week', called_at AT TIME ZONE 'UTC')::date AS week_of,
           feature,
           count(*) AS calls,
           sum(input_tokens) AS input_tokens,
           sum(output_tokens) AS output_tokens,
           sum(thinking_tokens) AS thinking_tokens,
           sum(cost_usd) AS cost_usd,
           count(*) FILTER (WHERE cost_usd IS NULL) AS unpriced_calls,
           string_agg(DISTINCT model, ', ' ORDER BY model) AS models
    FROM model_calls
    GROUP BY 1, 2
), rated AS (
    SELECT *,
           round(cost_usd / calls, 6) AS cost_per_call_usd,
           round(100.0 * thinking_tokens / nullif(output_tokens, 0), 1) AS thinking_share_pct
    FROM weekly
), compared AS (
    SELECT *,
           round(avg(cost_per_call_usd) OVER before, 6) AS usual_cost_per_call_usd,
           round(avg(thinking_share_pct) OVER before, 1) AS usual_thinking_share_pct
    FROM rated
    WINDOW before AS (PARTITION BY feature ORDER BY week_of ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
)
SELECT week_of, feature, calls, input_tokens, output_tokens, thinking_tokens,
       thinking_share_pct, usual_thinking_share_pct, cost_usd, cost_per_call_usd, usual_cost_per_call_usd, unpriced_calls, models,
       CASE WHEN usual_cost_per_call_usd IS NULL AND usual_thinking_share_pct IS NULL THEN 'no earlier week to compare with'
            WHEN cost_per_call_usd > {JUMP} * usual_cost_per_call_usd THEN 'look: cost per call more than 30% above the usual'
            WHEN thinking_share_pct > {JUMP} * usual_thinking_share_pct THEN 'look: hidden thinking share more than 30% above the usual'
            ELSE 'ok' END AS flag
FROM compared
ORDER BY week_of DESC, cost_usd DESC NULLS LAST, feature
"""

BY_DAY = """
CREATE VIEW model_costs_by_day AS
SELECT (called_at AT TIME ZONE 'UTC')::date AS day,
       model,
       count(*) AS calls,
       sum(input_tokens) AS input_tokens,
       sum(output_tokens) AS output_tokens,
       sum(thinking_tokens) AS thinking_tokens,
       sum(cache_read_tokens) AS cache_read_tokens,
       sum(cache_write_tokens) AS cache_write_tokens,
       sum(cost_usd) AS cost_usd,
       count(*) FILTER (WHERE cost_usd IS NULL) AS unpriced_calls
FROM model_calls
GROUP BY 1, 2
ORDER BY day DESC, model
"""

VIEW_COMMENTS = {
    "model_costs_by_person": "Each month (UTC) and person: calls, what they used, tokens and cost (ADR-0119)",
    "model_costs_by_feature": "Each week (UTC, from Monday) and feature: tokens, hidden thinking share and cost per call against the four weeks "
                              "before, flagged above 30% (ADR-0119)",
    "model_costs_by_day": "Each day (UTC) and model: the counts and cost to set beside the provider's usage page (ADR-0119)",
}


def upgrade() -> None:
    op.create_table(
        "model_calls",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False, comment="When the model answered"),
        sa.Column("user_email", sa.String(320), comment="Who asked: the signed-in email; empty when nobody was signed in"),
        sa.Column("actor", sa.String(40), nullable=False, comment="Which client sent the request: studio, browser, assistant ..."),
        sa.Column("feature", sa.String(40), nullable=False, comment="What the call was for, such as explain_result"),
        sa.Column("model", sa.String(80), nullable=False, comment="The model that answered"),
        sa.Column("effort", sa.String(10), comment="The effort the call asked for"),
        sa.Column("input_tokens", sa.Integer, nullable=False, comment="Tokens read, billed at the input price"),
        sa.Column("output_tokens", sa.Integer, nullable=False,
                  comment="Tokens written, billed at the output price; the hidden thinking is part of them"),
        sa.Column("thinking_tokens", sa.Integer, comment="The part of output_tokens that was hidden thinking, as the API reports it"),
        sa.Column("cache_read_tokens", sa.Integer, nullable=False, server_default=text("0"), comment="Tokens read from the prompt cache"),
        sa.Column("cache_write_tokens", sa.Integer, nullable=False, server_default=text("0"), comment="Tokens written to the prompt cache"),
        sa.Column("answer_characters", sa.Integer, nullable=False, comment="Length of the answer we received, in characters"),
        sa.Column("stop_reason", sa.String(20), comment="How the call ended: end_turn, max_tokens, refusal"),
        sa.Column("seconds", sa.Float, nullable=False, comment="How long the call took"),
        sa.Column("cost_usd", sa.Numeric(12, 6), comment="US dollars at the list prices of prices_as_of; empty when not priced"),
        sa.Column("prices_as_of", sa.String(10), comment="The date of the price list the cost was taken from"),
        sa.Column("run_id", sa.Uuid(as_uuid=True), sa.ForeignKey("runs.id", ondelete="SET NULL"),
                  comment="The run record of the request the call answered"),
        sa.Column("attempts", JSONB, comment="Each attempt's tokens when there was more than one"),
        sa.CheckConstraint("feature IN (" + ", ".join(f"'{feature}'" for feature in FEATURES) + ")", name="model_calls_feature_known"),
        sa.CheckConstraint("input_tokens >= 0 AND output_tokens >= 0 AND cache_read_tokens >= 0 AND cache_write_tokens >= 0 "
                           "AND answer_characters >= 0", name="model_calls_counts_not_negative"),
        sa.CheckConstraint("thinking_tokens IS NULL OR thinking_tokens BETWEEN 0 AND output_tokens", name="model_calls_thinking_within_output"),
        comment="One row per call to the language model: who asked, for what, the tokens billed and the cost (ADR-0119)",
    )
    op.create_index("model_calls_called_at_idx", "model_calls", ["called_at"])
    op.create_index("model_calls_person_idx", "model_calls", ["user_email", "called_at"])
    for view in (BY_PERSON, BY_FEATURE, BY_DAY):
        op.execute(view)
    for name, comment in VIEW_COMMENTS.items():
        quoted = comment.replace("'", "''")
        op.execute(f"COMMENT ON VIEW {name} IS '{quoted}'")


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM model_calls")).scalar()
    if count:
        raise RuntimeError(f"the model_calls table holds {count} call(s); the cost history would be lost, so this migration is not undone over them")
    for name in VIEW_COMMENTS:
        op.execute(f"DROP VIEW {name}")
    op.drop_index("model_calls_person_idx", table_name="model_calls")
    op.drop_index("model_calls_called_at_idx", table_name="model_calls")
    op.drop_table("model_calls")
