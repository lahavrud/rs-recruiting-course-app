"""add worker heartbeat table

Singleton table the SQS worker upserts its running image tag into on startup,
surfaced by the api's /health as worker_version so a worker release can be
smoke-checked through the public domain. Mirrors the WorkerHeartbeat SQLModel
(create_all builds it in dev/test) — keep the two in sync.

Revision ID: a26cddb666fd
Revises: 04c996bcec75
Create Date: 2026-07-12 19:32:14.964016

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a26cddb666fd"
down_revision: Union[str, Sequence[str], None] = "04c996bcec75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeat",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeat")
