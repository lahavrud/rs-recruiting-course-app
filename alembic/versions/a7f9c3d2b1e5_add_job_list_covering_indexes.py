"""add covering indexes for job list endpoints

Revision ID: a7f9c3d2b1e5
Revises: e7f3a2b1c8d4
Create Date: 2026-05-11 14:00:00.000000

Supports three cursor-paginated list endpoints:
- /api/public/jobs       — filters status=PUBLISHED, orders by created_at DESC
- /api/jobs/             — filters by company_id, orders by created_at DESC
- /api/admin/jobs/pending — filters status=PENDING_APPROVAL, orders by created_at DESC
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7f9c3d2b1e5"
down_revision: str | Sequence[str] | None = "e7f3a2b1c8d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Covers public job board and admin pending list (filter by status, sort by date)
    op.create_index(
        "ix_job_status_created_at",
        "job",
        ["status", "created_at"],
    )
    # Covers company jobs list (filter by company_id, sort by date)
    op.create_index(
        "ix_job_company_id_created_at",
        "job",
        ["company_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_company_id_created_at", table_name="job")
    op.drop_index("ix_job_status_created_at", table_name="job")
