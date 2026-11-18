"""One-time codes that connect a user's machine to their account (ADR-0094 amendment 1).

The page of a signed-in user asks for a code and hands it to the user's machine in a link. The machine swaps it once, within
minutes, for an upload token of its own, so no token is copied by hand. `pairing_codes` keeps one row per code: its owner (the
signed-in email behind Cloudflare Access, or the actor locally, as a project's), the SHA-256 of the code, never the code, when it
ends, when it was swapped and the token it became.

The downgrade drops the table: a code lives for minutes and what it became is in `upload_tokens`.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pairing_codes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("user_email", sa.String(320)),
        sa.Column("code_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("token_id", sa.Uuid(as_uuid=True), sa.ForeignKey("upload_tokens.id")),
    )
    op.create_index("pairing_codes_owner_idx", "pairing_codes", ["user_email", "created_at"])
    op.create_index("pairing_codes_actor_idx", "pairing_codes", ["actor", "created_at"])


def downgrade() -> None:
    op.drop_index("pairing_codes_actor_idx", table_name="pairing_codes")
    op.drop_index("pairing_codes_owner_idx", table_name="pairing_codes")
    op.drop_table("pairing_codes")
