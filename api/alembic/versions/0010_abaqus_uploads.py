"""The uploads from Abaqus and the tokens that send them (ADR-0094, part 6 and step 5).

A bundle a user sends from their own Abaqus is private: it belongs to who sent it. `abaqus_uploads` keeps one row per stored bundle:
its owner (the signed-in email behind Cloudflare Access, or the actor locally, as a project's), the bundle's SHA-256 and size, what
the check found in it, where the object store keeps it (`uploads/<id>/bundle.zip`), and, once it was put beside a run of ours, that
job, the verdict and the comparison. `may_train` is the box of part 6: false unless the owner ticked it.

`upload_tokens` keeps what the connector sends with: the SHA-256 of a token the owner created, never the token, with its last four
characters to tell one from another, when it was last used and when it was cancelled. A cancelled token stays, so the uploads it
sent still name it.

Rows here change and an upload's row is deleted with its bundle when its owner asks. The downgrade refuses while either table holds
rows: they would be lost.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

VERDICTS = ("agrees", "differs", "incomplete", "refused")


def upgrade() -> None:
    op.create_table(
        "upload_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("user_email", sa.String(320)),
        sa.Column("name", sa.Text, nullable=False, server_default=""),
        sa.Column("token_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("hint", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("upload_tokens_owner_idx", "upload_tokens", ["user_email", "created_at"])
    op.create_index("upload_tokens_actor_idx", "upload_tokens", ["actor", "created_at"])
    op.create_table(
        "abaqus_uploads",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("user_email", sa.String(320)),
        sa.Column("token_id", sa.Uuid(as_uuid=True), sa.ForeignKey("upload_tokens.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bundle_sha256", sa.String(64), nullable=False),
        sa.Column("bundle_bytes", sa.BigInteger, nullable=False),
        sa.Column("object_key", sa.Text, nullable=False),
        sa.Column("units", sa.String(20), nullable=False),
        sa.Column("job", sa.Text),
        sa.Column("coupon", sa.Text),
        sa.Column("in_scope", sa.Boolean, nullable=False),
        sa.Column("facts", JSONB, nullable=False),
        sa.Column("may_train", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id")),
        sa.Column("verdict", sa.String(12)),
        sa.Column("comparison", JSONB),
        sa.Column("compared_at", sa.DateTime(timezone=True)),
        sa.Column("not_compared", sa.Text),
        sa.CheckConstraint("verdict IS NULL OR verdict IN (" + ", ".join(f"'{verdict}'" for verdict in VERDICTS) + ")", name="abaqus_uploads_verdict_known"),
        sa.CheckConstraint("(verdict IS NULL) = (comparison IS NULL)", name="abaqus_uploads_verdict_has_comparison"),
    )
    op.create_index("abaqus_uploads_owner_idx", "abaqus_uploads", ["user_email", "created_at"])
    op.create_index("abaqus_uploads_actor_idx", "abaqus_uploads", ["actor", "created_at"])


def downgrade() -> None:
    for table, what in (("abaqus_uploads", "upload(s)"), ("upload_tokens", "token(s)")):
        count = op.get_bind().execute(text(f"SELECT count(*) FROM {table}")).scalar()
        if count:
            raise RuntimeError(f"the {table} table holds {count} {what}; they would be lost, so this migration is not undone over them")
    op.drop_index("abaqus_uploads_actor_idx", table_name="abaqus_uploads")
    op.drop_index("abaqus_uploads_owner_idx", table_name="abaqus_uploads")
    op.drop_table("abaqus_uploads")
    op.drop_index("upload_tokens_actor_idx", table_name="upload_tokens")
    op.drop_index("upload_tokens_owner_idx", table_name="upload_tokens")
    op.drop_table("upload_tokens")
