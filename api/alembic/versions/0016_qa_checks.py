"""The QA record: every quality check of every coupon job, kept for good (ADR-0137).

A coupon run already checks its setup, compares its result with a second solver and studies its mesh, but each of these lived in a
file of its own and nothing set them beside each other. `qa_checks` keeps one row per check per job: its place in the run's list, when
it was recorded, its layer (data, physics, fea, output, software), its id and the version of its rule, its verdict (pass, warn, block),
its label and message in the words a customer reads, what it measured, and the decision record or clause behind it. A job's verdict
follows from its rows alone, so it is not stored.

Rows are never updated or deleted: a trigger refuses both, as the runs table's does (ADR-0026). A row names its job; a job with checks
cannot be deleted before them, so the one clearing of the hosted trials (scripts/clear-hosted-trials.py) deletes them first, with the
trigger off for that statement as it does for the runs. The downgrade refuses while the table holds a row: the record would be lost.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

# As anisotropy_fea.qa names them on the day of this migration.
LAYERS = ("data", "physics", "fea", "output", "software")
VERDICTS = ("pass", "warn", "block")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "qa_checks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False, comment="The coupon job the check belongs to"),
        sa.Column("position", sa.Integer, nullable=False, comment="The check's place in the run's list, from 0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, comment="When the check was written into the record"),
        sa.Column("layer", sa.String(10), nullable=False, comment="data, physics, fea, output or software"),
        sa.Column("check_id", sa.String(64), nullable=False, comment="The check's id, such as FEA-SECOND-SOLVER"),
        sa.Column("version", sa.Integer, nullable=False, comment="The version of the check's rule when it judged"),
        sa.Column("verdict", sa.String(5), nullable=False, comment="pass, warn or block"),
        sa.Column("label", sa.Text, nullable=False, comment="The check's name, as a customer reads it"),
        sa.Column("message", sa.Text, nullable=False, comment="What the check found, as a customer reads it"),
        sa.Column("evidence", JSONB, nullable=False, comment="What the check measured: a few values"),
        sa.Column("basis", sa.String(40), nullable=False, comment="The decision record or clause behind the rule"),
        sa.CheckConstraint(f"layer IN ({_sql_list(LAYERS)})", name="qa_checks_layer_known"),
        sa.CheckConstraint(f"verdict IN ({_sql_list(VERDICTS)})", name="qa_checks_verdict_known"),
        sa.CheckConstraint("version >= 1", name="qa_checks_version_positive"),
        sa.UniqueConstraint("job_id", "position", name="qa_checks_one_per_place"),
        comment="One row per quality check of a coupon job, never edited or deleted (ADR-0137)",
    )
    op.create_index("qa_checks_recorded_at_idx", "qa_checks", ["recorded_at"])
    op.create_index("qa_checks_check_idx", "qa_checks", ["check_id", "verdict"])
    op.execute("""
        CREATE FUNCTION qa_checks_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'QA checks are never edited or deleted (ADR-0137)';
        END
        $$;
    """)
    op.execute("CREATE TRIGGER qa_checks_immutable BEFORE UPDATE OR DELETE ON qa_checks FOR EACH ROW EXECUTE FUNCTION qa_checks_are_immutable();")
    # Written once: a job's checks all carry the moment they were recorded, so a row for a job that already has rows from another
    # moment is a second write, refused here as well as by the API, so no check can be added to a run's record afterwards.
    op.execute("""
        CREATE FUNCTION qa_checks_written_once() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM qa_checks WHERE job_id = NEW.job_id AND recorded_at <> NEW.recorded_at) THEN
                RAISE EXCEPTION 'a job''s QA checks are written once (ADR-0137)';
            END IF;
            RETURN NEW;
        END
        $$;
    """)
    op.execute("CREATE TRIGGER qa_checks_once BEFORE INSERT ON qa_checks FOR EACH ROW EXECUTE FUNCTION qa_checks_written_once();")


def downgrade() -> None:
    count = op.get_bind().execute(text("SELECT count(*) FROM qa_checks")).scalar()
    if count:
        raise RuntimeError(f"the qa_checks table holds {count} check(s); the QA record would be lost, so this migration is not undone over them")
    op.execute("DROP TRIGGER qa_checks_once ON qa_checks;")
    op.execute("DROP FUNCTION qa_checks_written_once();")
    op.execute("DROP TRIGGER qa_checks_immutable ON qa_checks;")
    op.execute("DROP FUNCTION qa_checks_are_immutable();")
    op.drop_index("qa_checks_check_idx", table_name="qa_checks")
    op.drop_index("qa_checks_recorded_at_idx", table_name="qa_checks")
    op.drop_table("qa_checks")
