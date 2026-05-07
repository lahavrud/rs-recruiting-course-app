"""companyprofile user_id nullable

Revision ID: 175fb94581a1
Revises: afc9218a03de
Create Date: 2026-05-07 14:40:00.000000

Allow `companyprofile.user_id` to be NULL so admins can post jobs against
companies that have no user account yet. The UNIQUE index is preserved —
Postgres treats NULLs as not-equal, so multiple admin-created (user-less)
companies coexist while any real user still owns at most one company.

Downgrade re-applies NOT NULL and will fail if any rows have NULL user_id;
either backfill or delete those rows before downgrading.

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "175fb94581a1"
down_revision: Union[str, Sequence[str], None] = "afc9218a03de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "companyprofile",
        "user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "companyprofile",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
