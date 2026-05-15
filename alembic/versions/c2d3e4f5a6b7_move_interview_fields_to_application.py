"""move interview answer fields from candidateprofile to application

Revision ID: c2d3e4f5a6b7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-15 00:00:00.000000

CandidateProfile becomes a clean identity + consent record.
Application gains the four per-job answer fields.
Two dead columns (military_service_details, transportation) are also dropped.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "9eed17087de9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add answer columns to application
    op.add_column("application", sa.Column("service_concept", sa.Text(), nullable=True))
    op.add_column(
        "application", sa.Column("salary_expectations", sa.Text(), nullable=True)
    )
    op.add_column("application", sa.Column("strength", sa.Text(), nullable=True))
    op.add_column("application", sa.Column("growth_area", sa.Text(), nullable=True))

    # 2. Backfill: copy current candidate answers to all their applications.
    # For multi-application candidates the stored value is from their first
    # application (set-if-None semantics), so copying to all rows is the best
    # approximation available.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                UPDATE application a
                SET
                    service_concept     = cp.service_concept,
                    salary_expectations = cp.salary_expectations,
                    strength            = cp.personality_strength,
                    growth_area         = cp.personality_weakness
                FROM candidateprofile cp
                WHERE a.candidate_id = cp.id
                """
            )
        )
    else:
        # SQLite: UPDATE … FROM is not supported; use correlated subquery
        bind.execute(
            sa.text(
                """
                UPDATE application
                SET
                    service_concept     = (SELECT service_concept     FROM candidateprofile WHERE id = application.candidate_id),
                    salary_expectations = (SELECT salary_expectations FROM candidateprofile WHERE id = application.candidate_id),
                    strength            = (SELECT personality_strength FROM candidateprofile WHERE id = application.candidate_id),
                    growth_area         = (SELECT personality_weakness FROM candidateprofile WHERE id = application.candidate_id)
                """
            )
        )

    # 3. Drop moved + dead columns from candidateprofile
    op.drop_column("candidateprofile", "service_concept")
    op.drop_column("candidateprofile", "salary_expectations")
    op.drop_column("candidateprofile", "personality_strength")
    op.drop_column("candidateprofile", "personality_weakness")
    op.drop_column("candidateprofile", "military_service_details")
    op.drop_column("candidateprofile", "transportation")


def downgrade() -> None:
    """Downgrade schema."""
    # Restore columns to candidateprofile (data is lost — accepted trade-off)
    op.add_column(
        "candidateprofile", sa.Column("service_concept", sa.Text(), nullable=True)
    )
    op.add_column(
        "candidateprofile", sa.Column("salary_expectations", sa.Text(), nullable=True)
    )
    op.add_column(
        "candidateprofile", sa.Column("personality_strength", sa.Text(), nullable=True)
    )
    op.add_column(
        "candidateprofile", sa.Column("personality_weakness", sa.Text(), nullable=True)
    )
    op.add_column(
        "candidateprofile",
        sa.Column("military_service_details", sa.Text(), nullable=True),
    )
    op.add_column(
        "candidateprofile", sa.Column("transportation", sa.Text(), nullable=True)
    )

    # Drop answer columns from application
    op.drop_column("application", "growth_area")
    op.drop_column("application", "strength")
    op.drop_column("application", "salary_expectations")
    op.drop_column("application", "service_concept")
