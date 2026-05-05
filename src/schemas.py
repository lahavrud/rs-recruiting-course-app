"""Pydantic schemas for request/response validation."""

import os
import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.enums import ApplicationStatus, InviteTokenStatus, JobStatus, UserRole


def _validate_phone_value(v: str | None) -> str | None:
    """Validate phone number format.

    Used by CandidateProfileCreate and CandidateProfileUpdate.
    """
    if v is None or v == "":
        return None
    pattern = r"^[+\d\s()-]*$"
    if not re.match(pattern, v):
        raise ValueError("Phone number may only contain digits, spaces, +, -, (, )")
    digits = re.sub(r"\D", "", v)
    if len(digits) < 5:
        raise ValueError("Phone number must have at least 5 digits")
    return v


def _validate_linkedin_url_value(v: str | None) -> str | None:
    """Validate LinkedIn URL format.

    Used by CandidateProfileCreate and CandidateProfileUpdate.
    """
    if v is None or v == "":
        return None
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("LinkedIn URL must start with http:// or https://")
    hostname = parsed.hostname or ""
    if not (hostname == "linkedin.com" or hostname.endswith(".linkedin.com")):
        raise ValueError("LinkedIn URL must be a linkedin.com address")
    return v


class InviteTokenCreate(BaseModel):
    """Admin input for creating an invite — email only."""

    email: EmailStr = Field(..., max_length=255)


class InviteTokenRead(BaseModel):
    """Full invite record returned to admin."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    email: str
    company_name: str | None
    contact_first_name: str | None
    contact_last_name: str | None
    note: str | None
    status: InviteTokenStatus
    created_by_admin_id: int
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None


class InviteMetadataPublic(BaseModel):
    """Safe pre-fill data returned to the registration page."""

    model_config = ConfigDict(from_attributes=True)

    email: str


# Registration Schemas
class CompanyProfileCreate(BaseModel):
    """Schema for creating a company profile."""

    name: str = Field(..., max_length=100)
    company_id: str  # ח.פ — 9-digit Israeli company registration number
    address: str = Field(..., max_length=200)
    contact_first_name: str = Field(..., min_length=2, max_length=100)
    contact_last_name: str = Field(..., min_length=2, max_length=100)
    contact_mobile_phone: str
    contact_landline_phone: str | None = Field(None, max_length=20)

    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: str) -> str:
        if not re.fullmatch(r"\d{9}", v):
            raise ValueError("Company ID must be exactly 9 digits")
        return v

    @field_validator("contact_mobile_phone")
    @classmethod
    def validate_mobile_phone(cls, v: str) -> str:
        if not re.fullmatch(r"05[0-9]\d{7}", v):
            raise ValueError(
                "Mobile phone must be a valid Israeli mobile number (05X-XXXXXXX)"
            )
        return v


def _validate_password_complexity(v: str) -> str:
    """Enforce password complexity: min 8 chars, upper, lower, digit, special."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Password must contain at least one special character")
    return v


class UserCreate(BaseModel):
    """Schema for creating a user (registration)."""

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    company_profile: CompanyProfileCreate

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


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
    company_id: str | None
    address: str | None
    contact_first_name: str | None
    contact_last_name: str | None
    contact_mobile_phone: str | None
    contact_landline_phone: str | None
    agreement_signed_at: datetime | None
    agreement_signature_url: str | None
    privacy_accepted_at: datetime | None
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
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Schema for requesting a new access token using a refresh token."""

    refresh_token: str


# Job Schemas
class JobCreate(BaseModel):
    """Schema for creating a job posting."""

    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=5000)
    requirements: str = Field(..., max_length=5000)
    location: str = Field(..., max_length=100)


class JobUpdate(BaseModel):
    """Schema for updating a job posting."""

    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    requirements: str | None = Field(None, max_length=5000)
    location: str | None = Field(None, max_length=100)
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


class JobPublicRead(BaseModel):
    """Schema for public job board responses.

    Excludes internal fields (company_id, status, updated_at) that should
    not be exposed to unauthenticated users. Status is omitted because the
    public endpoint only ever returns PUBLISHED jobs — it carries no
    information and leaks an internal enum.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    requirements: str
    location: str
    created_at: datetime


# CandidateProfile Schemas
class CandidateProfileCreate(BaseModel):
    """Schema for creating a candidate profile (application form)."""

    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., max_length=255)
    phone: str = Field(..., max_length=30)
    resume_path: str | None = None
    linkedin_url: str | None = Field(None, max_length=500)
    # Interview form fields
    service_concept: str | None = Field(None, max_length=2000)
    salary_expectations: str | None = Field(None, max_length=2000)
    personality_weakness: str | None = Field(None, max_length=2000)
    personality_strength: str | None = Field(None, max_length=2000)

    @field_validator("resume_path")
    @classmethod
    def validate_resume_path(cls, v: str | None) -> str | None:
        """Validate resume path to prevent path traversal attacks.

        Note: This field is typically not set manually. The service layer
        handles file uploads and sets resume_path automatically with UUID-based
        identifiers from the storage provider.

        Security Rules:
        - Reject paths containing path traversal sequences ('../', '..\\')
        - Reject absolute paths (starting with '/' or '\\')
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

        # Reject paths with parent directory traversal sequences
        if "../" in v or "..\\" in v:
            raise ValueError(
                "Path cannot contain path traversal sequences ('../' or '..\\')"
            )

        # Reject absolute paths
        if v.startswith("/") or v.startswith("\\"):
            raise ValueError(
                "Path cannot be absolute (must not start with '/' or '\\')"
            )

        # Normalize the path to resolve any redundant separators
        normalized = os.path.normpath(v)

        # Additional check: ensure no path traversal after normalization
        if ".." in normalized:
            raise ValueError("Path cannot contain '..' (parent directory reference)")

        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        if not v.strip():
            raise ValueError("Phone number is required")
        result = _validate_phone_value(v)
        if result is None:
            raise ValueError("Phone number is required")
        return result

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: str | None) -> str | None:
        """Validate LinkedIn URL format."""
        return _validate_linkedin_url_value(v)


class CandidateProfileUpdate(BaseModel):
    """Schema for updating a candidate profile."""

    full_name: str | None = Field(None, min_length=2, max_length=100)
    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=30)
    resume_path: str | None = None
    linkedin_url: str | None = Field(None, max_length=500)
    service_concept: str | None = Field(None, max_length=2000)
    salary_expectations: str | None = Field(None, max_length=2000)
    personality_weakness: str | None = Field(None, max_length=2000)
    personality_strength: str | None = Field(None, max_length=2000)

    @field_validator("resume_path")
    @classmethod
    def validate_resume_path(cls, v: str | None) -> str | None:
        """Validate resume path to prevent path traversal attacks."""
        if v is None:
            return None
        if "../" in v or "..\\" in v:
            raise ValueError(
                "Path cannot contain path traversal sequences ('../' or '..\\')"
            )
        if v.startswith("/") or v.startswith("\\"):
            raise ValueError(
                "Path cannot be absolute (must not start with '/' or '\\')"
            )
        normalized = os.path.normpath(v)
        if ".." in normalized:
            raise ValueError("Path cannot contain '..' (parent directory reference)")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Validate phone number format."""
        return _validate_phone_value(v)

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: str | None) -> str | None:
        """Validate LinkedIn URL format."""
        return _validate_linkedin_url_value(v)


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
    personality_weakness: str | None
    personality_strength: str | None
    created_at: datetime


# Application (Match) Schemas
class ApplicationCreate(BaseModel):
    """Schema for creating an application (match)."""

    job_id: int
    candidate_id: int


class ApplicationStatusUpdate(BaseModel):
    """Schema for admin status updates on an application.

    status is required — use ApplicationUpdate for partial updates
    where status is optional.
    """

    status: ApplicationStatus
    admin_notes: str | None = Field(None, max_length=2000)


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""

    status: ApplicationStatus | None = None
    admin_notes: str | None = Field(None, max_length=2000)


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


class JobContactEmailRequest(BaseModel):
    """Schema for admin sending a contextual email to a company about a job."""

    admin_note: str = Field(default="", max_length=2000)


# Admin Schemas
class PendingCompanyRead(BaseModel):
    """Schema for pending company registration (user + company profile)."""

    user: UserRead
    company_profile: CompanyProfileRead


class ApprovedCompanyRead(BaseModel):
    """Schema for approved company (user + company profile)."""

    user: UserRead
    company_profile: CompanyProfileRead


class ActiveCompanyRead(BaseModel):
    """Schema for an active company in the admin company list."""

    user: UserRead
    company_profile: CompanyProfileRead
