from __future__ import annotations

import os
from datetime import datetime, timezone

from pydantic import field_validator
from sqlalchemy import DateTime, Text, UniqueConstraint
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
    company_user_id: int = Field(foreign_key="user.id", index=True)
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
    user_id: int = Field(foreign_key="user.id", index=True)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    is_revoked: bool = Field(default=False)
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

    # Relationship to CompanyProfile (optional, only for COMPANY role)
    # Note: ADMIN users don't have CompanyProfile, so this can be None
    # Reverted to original - CompanyProfile is defined later,
    # but SQLModel handles forward references
    company_profile: CompanyProfile = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False},
    )


class CompanyProfile(SQLModel, table=True):
    """Company profile linked to a User.

    One-to-one relationship with User (for COMPANY role users).
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None, foreign_key="user.id", unique=True, index=True
    )
    name: str
    logo_url: str | None = None
    company_id: str | None = None  # ח.פ — 9-digit Israeli company registration number
    contact_first_name: str | None = None
    contact_last_name: str | None = None
    contact_mobile_phone: str | None = None
    contact_landline_phone: str | None = None
    address: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
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

    # Relationships
    user: User = Relationship(back_populates="company_profile")
    # Note: One-way relationships for Job and Application (SQLModel 0.0.22 limitation)
    # Access via queries: session.exec(select(Job).where(Job.company_id == company.id))


class Job(SQLModel, table=True):
    """Job posting linked to a CompanyProfile.

    Jobs can be posted by companies and require admin approval before being published.
    """

    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="companyprofile.id", index=True)
    title: str
    description: str
    requirements: str
    location: str
    salary_min: int | None = Field(default=None)
    salary_max: int | None = Field(default=None)
    status: JobStatus = Field(default=JobStatus.PENDING_APPROVAL)
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
    phone: str | None = None
    resume_path: str | None = None
    linkedin_url: str | None = None

    # Interview Form Fields (Subject to Change)
    service_concept: str | None = Field(default=None, sa_column=Column(Text))
    salary_expectations: str | None = Field(default=None, sa_column=Column(Text))
    military_service_details: str | None = Field(default=None, sa_column=Column(Text))
    transportation: str | None = Field(default=None, sa_column=Column(Text))
    personality_weakness: str | None = Field(default=None, sa_column=Column(Text))
    personality_strength: str | None = Field(default=None, sa_column=Column(Text))

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
    job_id: int = Field(foreign_key="job.id", index=True)
    candidate_id: int = Field(foreign_key="candidateprofile.id", index=True)
    status: ApplicationStatus = Field(default=ApplicationStatus.NEW, index=True)
    admin_notes: str | None = Field(default=None, sa_column=Column(Text))
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
