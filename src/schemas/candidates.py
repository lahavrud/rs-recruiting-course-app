"""Candidate profile and application schemas."""

import os
import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.enums import ApplicationStatus
from src.schemas.jobs import JobRead


def _validate_phone_value(v: str | None) -> str | None:
    """Validate phone number format — Israeli mobile only.

    Accepts any input shape that, after stripping spaces / `+` / `-` / `(` / `)`,
    is exactly 10 digits starting with `05` (e.g. `0501234567`, `050-123-4567`,
    `+972 50 123 4567` does NOT pass — candidates must use the local form).
    Used by CandidateProfileCreate and CandidateProfileUpdate.
    """
    if v is None or v == "":
        return None
    pattern = r"^[+\d\s()-]*$"
    if not re.match(pattern, v):
        raise ValueError("Phone number may only contain digits, spaces, +, -, (, )")
    digits = re.sub(r"\D", "", v)
    if not re.fullmatch(r"05\d{8}", digits):
        raise ValueError("Phone must be a valid Israeli mobile number (05X-XXXXXXX)")
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


class CandidateProfileCreate(BaseModel):
    """Schema for creating a candidate profile (application form)."""

    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., max_length=255)
    phone: str = Field(..., max_length=30)
    resume_path: str | None = None
    linkedin_url: str | None = Field(None, max_length=500)

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
        """Validate phone number format.

        ``phone`` is NOT NULL in the database, so an explicit ``null`` on PATCH
        is rejected. The field stays Optional purely to keep partial-update
        semantics (omit-to-leave-unchanged) — only an absent key skips the
        validator.
        """
        if v is None:
            raise ValueError("Phone cannot be set to null on update")
        result = _validate_phone_value(v)
        if result is None:
            raise ValueError("Phone number is required")
        return result

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
    phone: str
    resume_path: str | None
    linkedin_url: str | None
    consent_given_at: datetime | None
    consent_policy_version: str | None
    tos_accepted_at: datetime | None
    tos_version: str | None
    created_at: datetime


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


class ApplicationNotesUpdate(BaseModel):
    """Schema for updating only the admin_notes field on an application."""

    admin_notes: str | None = Field(None, max_length=2000)


class ApplicationRead(BaseModel):
    """Schema for reading application data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    admin_notes: str | None
    service_concept: str | None
    salary_expectations: str | None
    strength: str | None
    growth_area: str | None
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
    service_concept: str | None
    salary_expectations: str | None
    strength: str | None
    growth_area: str | None
    created_at: datetime
    updated_at: datetime
    job: JobRead
    candidate: CandidateProfileRead
