"""How often the guards set the model's answers aside, week by week (ADR-0139).

Every request the model answered is a run record (ADR-0026), and its response says what became of the model's words: kept (`model`
named), set aside by a guard (`withheld`, ADR-0052, ADR-0102, ADR-0139), some of its proposals dropped (`dropped`, ADR-0088, ADR-0100),
no answer (`reason` with no model), or not asked because the person reached the day's cap (ADR-0139). Nobody looked at those counts.
One view reads them in plain columns:

- `assistant_guards_by_feature`: each week (UTC, from Monday) and route: the requests a model was asked for, how many of its answers
  were kept, set aside or had something dropped, how many got no answer and how many were capped; the share set aside against the four
  weeks before, and a flag when it is more than 10 points above. A jump after a change of model or instructions is drift.

The view reads the run records' responses and adds nothing to them. The reader of the cost views (`cost_reader`, ADR-0120) may read it
too when that role exists, so the monthly report can show it. The downgrade drops the view; no row is lost.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-24
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# The reason the API gives when a person's day's cap was reached (DAILY_LIMIT_REASON in anisotropy_api.assistant, on the day of this
# migration); such a request asked no model.
CAPPED = "the day's limit of free-text readings for this sign-in is reached"
LOOK = 10  # a week whose share set aside is more than this many points above the four before is flagged

GUARDS = f"""
CREATE VIEW assistant_guards_by_feature AS
WITH asked AS (
    SELECT date_trunc('week', created_at AT TIME ZONE 'UTC')::date AS week_of,
           CASE WHEN endpoint LIKE '%/explain' THEN 'explain' ELSE regexp_replace(endpoint, '^/v1/', '') END AS feature,
           response->>'model' IS NOT NULL AS kept,
           coalesce((response->>'withheld')::boolean, false) AS set_aside,
           coalesce(jsonb_typeof(response->'dropped') = 'array' AND jsonb_array_length(response->'dropped') > 0, false) AS dropped_some,
           coalesce(response->>'reason' = '{CAPPED.replace("'", "''")}', false) AS capped  -- coalesce: a NULL here would drop the row from every count
    FROM runs
    WHERE status = 'solved' AND response ? 'writer'
      AND (response->>'model' IS NOT NULL OR response->>'reason' IS NOT NULL OR coalesce((response->>'withheld')::boolean, false))
), weekly AS (
    SELECT week_of, feature,
           count(*) FILTER (WHERE NOT capped) AS asked,
           count(*) FILTER (WHERE kept) AS kept,
           count(*) FILTER (WHERE set_aside) AS set_aside,
           count(*) FILTER (WHERE dropped_some) AS with_dropped,
           count(*) FILTER (WHERE NOT kept AND NOT set_aside AND NOT capped) AS no_answer,
           count(*) FILTER (WHERE capped) AS capped
    FROM asked
    GROUP BY 1, 2
), rated AS (
    SELECT *, round(100.0 * set_aside / nullif(asked, 0), 1) AS set_aside_pct
    FROM weekly
), compared AS (
    SELECT *, round(avg(set_aside_pct) OVER before, 1) AS usual_set_aside_pct
    FROM rated
    WINDOW before AS (PARTITION BY feature ORDER BY week_of ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
)
SELECT week_of, feature, asked, kept, set_aside, with_dropped, no_answer, capped, set_aside_pct, usual_set_aside_pct,
       CASE WHEN usual_set_aside_pct IS NULL THEN 'no earlier week to compare with'
            WHEN set_aside_pct > usual_set_aside_pct + {LOOK} THEN 'look: more answers set aside than usual'
            ELSE 'ok' END AS flag
FROM compared
ORDER BY week_of DESC, asked DESC, feature
"""

COMMENT = ("Each week (UTC, from Monday) and route: the requests a model was asked for, its answers kept, set aside by a guard or with "
           "something dropped, no answer and capped, the share set aside against the four weeks before, flagged above 10 points (ADR-0139)")

# Granted only where the cost views' reader exists (ADR-0120): the hosted database; a test database or a new one has no such role.
GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cost_reader') THEN
        GRANT SELECT ON assistant_guards_by_feature TO cost_reader;
    END IF;
END $$
"""


def upgrade() -> None:
    op.execute(GUARDS)
    op.execute(f"COMMENT ON VIEW assistant_guards_by_feature IS '{COMMENT}'")
    op.execute(GRANT)


def downgrade() -> None:
    op.execute("DROP VIEW assistant_guards_by_feature")
