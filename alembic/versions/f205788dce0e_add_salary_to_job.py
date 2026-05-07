"""add_salary_to_job

Revision ID: f205788dce0e
Revises: 6484c273cd57
Create Date: 2026-05-08 00:15:02.019094

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f205788dce0e"
down_revision: str | Sequence[str] | None = "6484c273cd57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job", sa.Column("salary_min", sa.Integer(), nullable=True))
    op.add_column("job", sa.Column("salary_max", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("job", "salary_max")
    op.drop_column("job", "salary_min")
