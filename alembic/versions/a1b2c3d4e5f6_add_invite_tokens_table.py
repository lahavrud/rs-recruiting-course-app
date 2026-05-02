"""add invite_tokens table

Revision ID: a1b2c3d4e5f6
Revises: 3d454225bd45
Create Date: 2026-05-02 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "3d454225bd45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE invitetokenstatus
                    AS ENUM ('pending', 'used', 'expired', 'revoked');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    op.create_table(
        "invitetoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("contact_first_name", sa.String(), nullable=True),
        sa.Column("contact_last_name", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "used",
                "expired",
                "revoked",
                name="invitetokenstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invitetoken_token"), "invitetoken", ["token"], unique=True)
    op.create_index(
        op.f("ix_invitetoken_created_by_admin_id"),
        "invitetoken",
        ["created_by_admin_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_invitetoken_created_by_admin_id"), table_name="invitetoken")
    op.drop_index(op.f("ix_invitetoken_token"), table_name="invitetoken")
    op.drop_table("invitetoken")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    JOIN pg_type t ON t.oid = a.atttypid
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'invitetokenstatus'
                      AND n.nspname = current_schema()
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                ) THEN
                    -- IF EXISTS guards against the case where the type was
                    -- never created (e.g. a partial upgrade that was rolled
                    -- back before the CREATE TYPE ran).
                    DROP TYPE IF EXISTS invitetokenstatus;
                END IF;
            END $$;
            """
        )
