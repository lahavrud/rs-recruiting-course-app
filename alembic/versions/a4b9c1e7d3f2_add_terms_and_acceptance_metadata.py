"""add terms-of-service + acceptance metadata to companyprofile and tos to candidate

Revision ID: a4b9c1e7d3f2
Revises: c2d3e4f5a6b7
Create Date: 2026-05-15 14:00:00.000000

Splits the legal acceptance into two independently versioned documents
(Terms of Service + Privacy Policy) on both registration paths:

CompanyProfile gains:
  - privacy_policy_version       version string the company saw at signup
  - terms_accepted_at            timestamp of ToS acceptance
  - terms_version                version string the company saw at signup
  - acceptance_ip                IP recorded at registration
  - acceptance_user_agent        UA recorded at registration

CandidateProfile gains (mirroring existing consent_* fields):
  - tos_accepted_at              timestamp of ToS acceptance
  - tos_version                  version string the candidate saw at apply

All columns are nullable; pre-existing rows stay NULL and are treated as
legacy by audits — they pre-date the split.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a4b9c1e7d3f2"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "companyprofile",
        sa.Column("privacy_policy_version", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "companyprofile",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "companyprofile",
        sa.Column("terms_version", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "companyprofile",
        sa.Column("acceptance_ip", sa.String(length=45), nullable=True),
    )
    op.add_column(
        "companyprofile",
        sa.Column("acceptance_user_agent", sa.Text(), nullable=True),
    )
    op.add_column(
        "candidateprofile",
        sa.Column("tos_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "candidateprofile",
        sa.Column("tos_version", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("candidateprofile", "tos_version")
    op.drop_column("candidateprofile", "tos_accepted_at")
    op.drop_column("companyprofile", "acceptance_user_agent")
    op.drop_column("companyprofile", "acceptance_ip")
    op.drop_column("companyprofile", "terms_version")
    op.drop_column("companyprofile", "terms_accepted_at")
    op.drop_column("companyprofile", "privacy_policy_version")
