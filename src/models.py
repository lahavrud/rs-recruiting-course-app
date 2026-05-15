from __future__ import annotations

import os
from datetime import datetime, timezone

from pydantic import field_validator
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from src.enums import ApplicationStatus, InviteTokenStatus, JobStatus, UserRole


class InviteToken(SQLModel, table=True):
    """Admin-issued invite tokens for gated company registration.

    Metadata is persisted here; Redis stores the live TTL/validity signal.
    """

    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    email: str
    company_name: str | None = None
    contact_first_name: str | None = None
    contact_last_name: str | None = None
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: InviteTokenStatus = Field(default=InviteTokenStatus.PENDING)
    created_by_admin_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class ActivationToken(SQLModel, table=True):
    """One-time activation tokens sent to companies after admin approval.

    Admin approval does not activate the account immediately; instead an
    ActivationToken is generated and emailed to the company.  The company
    must follow the link to activate their account.
    """

    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    company_user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used: bool = Field(default=False)


class RefreshToken(SQLModel, table=True):
    """Stored refresh tokens for the auth rotation flow.

    Tokens are stored as SHA-256 hashes. Each token is single-use:
    it is revoked and replaced on every refresh.
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    is_revoked: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class PasswordResetToken(SQLModel, table=True):
    """Single-use password-reset tokens.

    Stored as SHA-256 hashes; only the raw token (in the reset email link)
    can prove ownership. Marked `used=True` on successful reset.
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class User(SQLModel, table=True):
    """Authenticated user entity (Admins & Companies).

    Users authenticate and log in. Candidates do NOT use this model.
    """

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole
    is_active: bool = Field(default=False, description="False until Admin approves")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # NOTE: annotation is the bare class for SQLModel 0.0.22 compatibility —
    # `Optional[CompanyProfile]` / `CompanyProfile | None` are rejected at
    # mapper init under `from __future__ import annotations`. The relationship
    # IS effectively nullable: ADMIN users have no profile, and after
    # `selectinload(User.company_profile)` the value will be None.
    # See `tests/models/test_user.py::test_admin_user_company_profile_is_none`.
    company_profile: CompanyProfile = Relationship(
        back_populates="user",
        # `passive_deletes="all"` tells SQLAlchemy to leave FK rows alone and
        # rely on the DB's ON DELETE CASCADE (migration c4d2a8f1e9b7) — without
        # it, SA would issue `UPDATE companyprofile SET user_id=NULL` first and
        # orphan the profile instead of cascading.
        sa_relationship_kwargs={"uselist": False, "passive_deletes": "all"},
    )


class CompanyProfile(SQLModel, table=True):
    """Company profile linked to a User.

    One-to-one relationship with User (for COMPANY role users).
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=True,
            unique=True,
            index=True,
        ),
    )
    name: str
    logo_url: str | None = None
    company_id: str  # ח.פ — 9-digit Israeli company registration number
    contact_email: str = Field(index=True, max_length=255)
    contact_first_name: str
    contact_last_name: str
    contact_mobile_phone: str
    contact_landline_phone: str | None = None
    address: str = Field(sa_column=Column(Text, nullable=False))
    agreement_signed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    agreement_signature_url: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    contract_pdf_url: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    privacy_accepted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # NOTE: bare annotation for SQLModel 0.0.22 compatibility (see User above).
    # user_id is nullable (CompanyProfile may be created from an admin invite
    # before any User exists), so this relationship is effectively
    # `User | None` at runtime. See
    # `tests/models/test_user.py::test_orphan_company_profile_user_is_none`.
    user: User = Relationship(back_populates="company_profile")
    # Note: One-way relationships for Job and Application (SQLModel 0.0.22 limitation)
    # Access via queries: session.exec(select(Job).where(Job.company_id == company.id))


class Job(SQLModel, table=True):
    """Job posting linked to a CompanyProfile.

    Jobs can be posted by companies and require admin approval before being published.
    """

    __table_args__ = (
        CheckConstraint(
            "salary_min <= salary_max",
            name="ck_job_salary_range",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("companyprofile.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    title: str
    short_description: str
    description: str
    requirements: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    is_featured: bool = Field(default=False, index=True)
    location: str
    salary_min: int
    salary_max: int
    status: JobStatus = Field(default=JobStatus.PENDING_APPROVAL, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(timezone.utc),
        ),
    )

    # Relationships
    company: CompanyProfile = Relationship()
    # Note: One-way relationship (SQLModel 0.0.22 limitation)
    # Access via: session.exec(select(Job).where(Job.company_id == X))


class CandidateProfile(SQLModel, table=True):
    """Candidate profile (unauthenticated lead).

    Candidates do not authenticate. They are treated as leads/data entities.
    """

    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    email: str = Field(unique=True, index=True)
    phone: str
    resume_path: str | None = None
    linkedin_url: str | None = None

    # Privacy consent — captured at application time
    consent_given_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    consent_policy_version: str | None = Field(default=None, max_length=20)
    consent_ip: str | None = Field(default=None, max_length=45)
    consent_user_agent: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Note: One-way relationships only (SQLModel 0.0.22 limitation)
    # Access applications via:
    # session.exec(select(Application).where(Application.candidate_id == candidate.id))

    @field_validator("resume_path")
    @classmethod
    def validate_resume_path(cls, v: str | None) -> str | None:
        """Validate resume path to prevent path traversal attacks.

        Security Rules:
        - Reject paths containing '..' (parent directory traversal)
        - Reject absolute paths (starting with '/')
        - Normalize path and ensure it stays within uploads/resumes/
        - Allow None values (optional field)

        Args:
            v: The resume path to validate

        Returns:
            The validated path or None

        Raises:
            ValueError: If path contains malicious patterns
        """
        if v is None:
            return None

        # Reject paths with parent directory traversal
        if ".." in v:
            raise ValueError("Path cannot contain '..' (parent directory reference)")

        # Reject absolute paths
        if v.startswith("/"):
            raise ValueError("Path cannot be absolute (must not start with '/')")

        # Normalize the path to resolve any redundant separators or references
        normalized = os.path.normpath(v)

        # Ensure normalized path doesn't escape the expected directory
        # All resume paths should be within uploads/resumes/
        if not normalized.startswith("uploads/resumes/"):
            raise ValueError("Path must be within 'uploads/resumes/' directory")

        return normalized


class Application(SQLModel, table=True):
    """Application (Match) - the core business entity.

    Links a Candidate to a Job. Represents the recruitment match.
    """

    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("job.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    candidate_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("candidateprofile.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    status: ApplicationStatus = Field(default=ApplicationStatus.NEW, index=True)
    admin_notes: str | None = Field(default=None, sa_column=Column(Text))
    service_concept: str | None = Field(default=None, sa_column=Column(Text))
    salary_expectations: str | None = Field(default=None, sa_column=Column(Text))
    strength: str | None = Field(default=None, sa_column=Column(Text))
    growth_area: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(timezone.utc),
        ),
    )

    # Relationships
    job: Job = Relationship()
    candidate: CandidateProfile = Relationship()
    # Note: One-way relationships (SQLModel 0.0.22 limitation)
    # Access job's applications via:
    # session.exec(select(Application).where(Application.job_id == job.id))
    # Access candidate's applications via:
    # session.exec(select(Application).where(Application.candidate_id == candidate.id))


class AuditLog(SQLModel, table=True):
    """Append-only record of sensitive admin operations and system tasks."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    # No FK on actor_user_id: audit rows must outlive the user they reference
    # (deleting a user must not cascade-delete their audit history).
    actor_user_id: int | None = Field(default=None, index=True)
    action: str = Field(index=True, max_length=64)
    target_type: str = Field(index=True, max_length=64)
    target_id: int = Field(index=True)
    detail: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ip_address: str | None = Field(default=None, max_length=45)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
