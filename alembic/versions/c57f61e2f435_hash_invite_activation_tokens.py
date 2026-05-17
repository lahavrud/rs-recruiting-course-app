"""hash_invite_activation_tokens

Revision ID: c57f61e2f435
Revises: a4b9c1e7d3f2
Create Date: 2026-05-17 18:48:58.779416

Renames token → token_hash on InviteToken and ActivationToken and backfills
each row with SHA-256(old plaintext value).

Impact on existing data:
- ActivationToken: existing pending activation links continue to work — the
  backfilled hash matches what the new code computes on lookup.
- InviteToken: existing invite links become invalid because the Redis key
  format also changes (was invite_token:{raw}, now invite_token:{sha256}).
  Re-send any outstanding PENDING invites after deploying.
"""

import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "c57f61e2f435"
down_revision: Union[str, Sequence[str], None] = "a4b9c1e7d3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()

    # ── activationtoken ─────────────────────────────────────────────────────
    op.add_column(
        "activationtoken",
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    rows = conn.execute(sa.text("SELECT id, token FROM activationtoken")).fetchall()
    for row_id, raw in rows:
        conn.execute(
            sa.text("UPDATE activationtoken SET token_hash = :h WHERE id = :id"),
            {"h": _sha256(raw), "id": row_id},
        )
    op.alter_column("activationtoken", "token_hash", nullable=False)
    op.drop_index(op.f("ix_activationtoken_token"), table_name="activationtoken")
    op.create_index(
        op.f("ix_activationtoken_token_hash"),
        "activationtoken",
        ["token_hash"],
        unique=True,
    )
    op.drop_column("activationtoken", "token")

    # ── invitetoken ──────────────────────────────────────────────────────────
    op.add_column(
        "invitetoken",
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    rows = conn.execute(sa.text("SELECT id, token FROM invitetoken")).fetchall()
    for row_id, raw in rows:
        conn.execute(
            sa.text("UPDATE invitetoken SET token_hash = :h WHERE id = :id"),
            {"h": _sha256(raw), "id": row_id},
        )
    op.alter_column("invitetoken", "token_hash", nullable=False)
    op.drop_index(op.f("ix_invitetoken_token"), table_name="invitetoken")
    op.create_index(
        op.f("ix_invitetoken_token_hash"), "invitetoken", ["token_hash"], unique=True
    )
    op.drop_column("invitetoken", "token")

    # ── job indexes (idempotent — already exist on some environments) ──────────
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_job_created_at ON job (created_at)")
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_job_status ON job (status)"))


def downgrade() -> None:
    op.drop_index(op.f("ix_job_status"), table_name="job")
    op.drop_index(op.f("ix_job_created_at"), table_name="job")

    # Hashing is one-way; downgrade renames columns back but cannot restore
    # the original plaintext values (rows will have the hash as the "token").
    op.add_column(
        "invitetoken",
        sa.Column("token", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.drop_index(op.f("ix_invitetoken_token_hash"), table_name="invitetoken")
    op.create_index(op.f("ix_invitetoken_token"), "invitetoken", ["token"], unique=True)
    op.drop_column("invitetoken", "token_hash")

    op.add_column(
        "activationtoken",
        sa.Column("token", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.drop_index(op.f("ix_activationtoken_token_hash"), table_name="activationtoken")
    op.create_index(
        op.f("ix_activationtoken_token"), "activationtoken", ["token"], unique=True
    )
    op.drop_column("activationtoken", "token_hash")
