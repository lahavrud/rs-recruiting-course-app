"""add activationtoken.full_name

Snapshot the registered name onto the activation token so the
``CandidateProfile`` created at activation can prefill it without
prompting the user. Nullable: legacy tokens minted before this column
existed have NULL here and the activation service falls back to the
email local-part.

Revision ID: 6c424e44ec00
Revises: e05ba7c8b4ac
Create Date: 2026-05-20 21:00:04.968134

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6c424e44ec00"
down_revision: Union[str, Sequence[str], None] = "e05ba7c8b4ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activationtoken",
        sa.Column("full_name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activationtoken", "full_name")
