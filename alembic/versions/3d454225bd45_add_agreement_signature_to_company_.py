"""add agreement signature to company_profile

Revision ID: 3d454225bd45
Revises: ba07bffc6f1f
Create Date: 2026-05-02 12:25:24.747050

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d454225bd45"
down_revision: Union[str, Sequence[str], None] = "ba07bffc6f1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "companyprofile",
        sa.Column("agreement_signed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "companyprofile",
        sa.Column("agreement_signature_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("companyprofile", "agreement_signature_url")
    op.drop_column("companyprofile", "agreement_signed_at")
