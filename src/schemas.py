"""Pydantic schemas for request/response validation."""

import os
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from src.enums import ApplicationStatus, JobStatus, UserRole


# Registration Schemas
class CompanyProfileCreate(BaseModel):
    """Schema for creating a company profile."""

    name: str
    logo_url: str | None = None
    contact_person: str | None = None
    contact_phone: str | None = None


class UserCreate(BaseModel):
    """Schema for creating a user (registration)."""

    email: EmailStr
    password: str
    company_profile: CompanyProfileCreate


class UserRead(BaseModel):
    """Schema for reading user data (excludes sensitive fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime


class CompanyProfileRead(BaseModel):
    """Schema for reading company profile data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    logo_url: str | None
    contact_person: str | None
    contact_phone: str | None
    created_at: datetime


class UserWithCompanyRead(BaseModel):
    """Schema for user with company profile."""

    user: UserRead
    company_profile: CompanyProfileRead


# Login Schemas
class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"


# Job Schemas
class JobCreate(BaseModel):
    """Schema for creating a job posting."""

    title: str
    description: str
    requirements: str
    location: str


class JobUpdate(BaseModel):
    """Schema for updating a job posting."""

    title: str | None = None
    description: str | None = None
    requirements: str | None = None
    location: str | None = None
    status: JobStatus | None = None


class JobRead(BaseModel):
    """Schema for reading job data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    description: str
    requirements: str
    location: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime


# CandidateProfile Schemas
class CandidateProfileCreate(BaseModel):
    """Schema for creating a candidate profile (application form)."""

    full_name: str
    email: EmailStr
    phone: str | None = None
    resume_path: str | None = None
    linkedin_url: str | None = None
    # Interview form fields
    service_concept: str | None = None
    salary_expectations: str | None = None
    military_service_details: str | None = None
    transportation: str | None = None
    personality_weakness: str | None = None
    personality_strength: str | None = None

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


class CandidateProfileUpdate(BaseModel):
    """Schema for updating a candidate profile."""

    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    resume_path: str | None = None
    linkedin_url: str | None = None
    service_concept: str | None = None
    salary_expectations: str | None = None
    military_service_details: str | None = None
    transportation: str | None = None
    personality_weakness: str | None = None
    personality_strength: str | None = None

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


class CandidateProfileRead(BaseModel):
    """Schema for reading candidate profile data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str | None
    resume_path: str | None
    linkedin_url: str | None
    service_concept: str | None
    salary_expectations: str | None
    military_service_details: str | None
    transportation: str | None
    personality_weakness: str | None
    personality_strength: str | None
    created_at: datetime


# Application (Match) Schemas
class ApplicationCreate(BaseModel):
    """Schema for creating an application (match)."""

    job_id: int
    candidate_id: int


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""

    status: ApplicationStatus | None = None
    admin_notes: str | None = None


class ApplicationRead(BaseModel):
    """Schema for reading application data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    admin_notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationWithDetails(BaseModel):
    """Schema for application with related job and candidate details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    admin_notes: str | None
    created_at: datetime
    updated_at: datetime
    job: JobRead
    candidate: CandidateProfileRead
