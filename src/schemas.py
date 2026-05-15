"""Pydantic schemas for request/response validation."""

import os
import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from src.enums import ApplicationStatus, InviteTokenStatus, JobStatus, UserRole


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
    user_id: int | None
    name: str
    logo_url: str | None
    company_id: str
    address: str
    contact_email: EmailStr
    contact_first_name: str
    contact_last_name: str
    contact_mobile_phone: str
    contact_landline_phone: str | None
    agreement_signed_at: datetime | None
    agreement_signature_url: str | None
    contract_pdf_url: str | None
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


class ForgotPasswordRequest(BaseModel):
    """Schema for requesting a password reset email.

    `email` is a plain `str` (not `EmailStr`) so malformed addresses produce
    the same 200-OK as valid ones — Pydantic's 422 on `EmailStr` would
    distinguish "well-formed unknown email" from "malformed input" and leak
    a signal back to an attacker.
    """

    email: str = Field(..., max_length=255)


class ResetPasswordRequest(BaseModel):
    """Schema for completing a password reset with a token + new password."""

    token: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


# Job Schemas
JOB_SHORT_DESC_MAX = 140
JOB_TAG_MAX_LEN = 30
JOB_TAG_MAX_COUNT = 6
JOB_REQ_TEXT_MAX = 200
JOB_REQ_MIN_COUNT = 3
JOB_REQ_MAX_COUNT = 15


class JobRequirementItem(BaseModel):
    """A single requirement bullet."""

    text: str = Field(..., min_length=1, max_length=JOB_REQ_TEXT_MAX)

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("requirement text cannot be empty")
        return stripped


def _validate_requirements(
    v: list[JobRequirementItem],
) -> list[JobRequirementItem]:
    if not (JOB_REQ_MIN_COUNT <= len(v) <= JOB_REQ_MAX_COUNT):
        raise ValueError(
            f"requirements must have between {JOB_REQ_MIN_COUNT} and "
            f"{JOB_REQ_MAX_COUNT} items"
        )
    return v


def _validate_tags(v: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in v:
        tag = raw.strip()
        if not tag:
            continue
        if len(tag) > JOB_TAG_MAX_LEN:
            raise ValueError(f"tag must be at most {JOB_TAG_MAX_LEN} characters")
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tag)
    if len(cleaned) > JOB_TAG_MAX_COUNT:
        raise ValueError(f"at most {JOB_TAG_MAX_COUNT} tags allowed")
    return cleaned


class JobCreate(BaseModel):
    """Schema for creating a job posting."""

    title: str = Field(..., max_length=100)
    short_description: str = Field(..., min_length=1, max_length=JOB_SHORT_DESC_MAX)
    description: str = Field(..., max_length=5000)
    requirements: list[JobRequirementItem]
    tags: list[str] = Field(default_factory=list)
    location: str = Field(..., max_length=100)
    salary_min: int = Field(..., ge=0)
    salary_max: int = Field(..., ge=0)

    _validate_requirements = field_validator("requirements")(_validate_requirements)
    _validate_tags = field_validator("tags")(_validate_tags)

    @model_validator(mode="after")
    def _check_salary_range(self):
        if self.salary_min > self.salary_max:
            raise ValueError("salary_min must be <= salary_max")
        return self


class JobUpdate(BaseModel):
    """Schema for a company updating their job posting.

    Fields backed by NOT NULL columns reject an explicit ``null`` so a PATCH
    cannot bypass the database constraint. ``is_featured`` is intentionally
    omitted — only admins toggle that flag (see ``JobAdminUpdate``).
    """

    title: str | None = Field(None, max_length=100)
    short_description: str | None = Field(
        None, min_length=1, max_length=JOB_SHORT_DESC_MAX
    )
    description: str | None = Field(None, max_length=5000)
    requirements: list[JobRequirementItem] | None = None
    tags: list[str] | None = None
    location: str | None = Field(None, max_length=100)
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    status: JobStatus | None = None

    @field_validator(
        "title",
        "short_description",
        "description",
        "requirements",
        "tags",
        "location",
        "salary_min",
        "salary_max",
    )
    @classmethod
    def reject_explicit_null(cls, v: object) -> object:
        if v is None:
            raise ValueError("Field cannot be set to null on update")
        return v

    @field_validator("requirements")
    @classmethod
    def _validate_requirements_list(
        cls, v: list[JobRequirementItem]
    ) -> list[JobRequirementItem]:
        return _validate_requirements(v)

    @field_validator("tags")
    @classmethod
    def _validate_tags_list(cls, v: list[str]) -> list[str]:
        return _validate_tags(v)

    @model_validator(mode="after")
    def _check_salary_range(self):
        # Only enforce when BOTH bounds are being set in the same request;
        # partial updates that change only one bound rely on the DB CHECK
        # constraint ck_job_salary_range as the safety net.
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must be <= salary_max")
        return self


class JobAdminCreate(BaseModel):
    """Schema for an admin creating a job posting against a specific company."""

    company_id: int
    title: str = Field(..., max_length=100)
    short_description: str = Field(..., min_length=1, max_length=JOB_SHORT_DESC_MAX)
    description: str = Field(..., max_length=5000)
    requirements: list[JobRequirementItem]
    tags: list[str] = Field(default_factory=list)
    is_featured: bool = False
    location: str = Field(..., max_length=100)
    salary_min: int = Field(..., ge=0)
    salary_max: int = Field(..., ge=0)
    status: JobStatus = JobStatus.PUBLISHED

    _validate_requirements = field_validator("requirements")(_validate_requirements)
    _validate_tags = field_validator("tags")(_validate_tags)

    @model_validator(mode="after")
    def _check_salary_range(self):
        if self.salary_min > self.salary_max:
            raise ValueError("salary_min must be <= salary_max")
        return self


class JobAdminUpdate(JobUpdate):
    """Admin-only update schema. Adds ``is_featured`` toggle."""

    is_featured: bool | None = None

    @field_validator("is_featured")
    @classmethod
    def _reject_null_featured(cls, v: bool | None) -> bool:
        if v is None:
            raise ValueError("Field cannot be set to null on update")
        return v


class JobRead(BaseModel):
    """Schema for reading job data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    short_description: str
    description: str
    requirements: list[JobRequirementItem]
    tags: list[str]
    is_featured: bool
    location: str
    salary_min: int
    salary_max: int
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class CompanyDataExport(BaseModel):
    """Right-to-data-portability export payload for a company.

    File URLs on the embedded ``company_profile`` are presigned (1-hour
    validity for S3) so the recipient can download them without a
    follow-up auth round-trip.
    """

    exported_at: datetime
    user: UserRead
    company_profile: CompanyProfileRead
    jobs: list[JobRead]


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
    short_description: str
    description: str
    requirements: list[JobRequirementItem]
    tags: list[str]
    is_featured: bool
    location: str
    salary_min: int
    salary_max: int
    created_at: datetime


# CandidateProfile Schemas
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
    """Schema for an active company in the admin company list.

    ``user`` is ``None`` for profiles created directly by admins (user_id=null).
    """

    user: UserRead | None
    company_profile: CompanyProfileRead


class CompanyProfileAdminCreate(BaseModel):
    """Schema for an admin creating a company profile without a user account."""

    name: str = Field(..., max_length=100)
    company_id: str  # ח.פ — 9-digit Israeli company registration number
    address: str = Field(..., max_length=200)
    contact_email: EmailStr = Field(..., max_length=255)
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


class CompanyProfileAdminUpdate(BaseModel):
    """Partial-update schema for an admin editing a company profile.

    The five fields ``name``, ``company_id``, ``address``, ``contact_first_name``,
    ``contact_last_name``, and ``contact_mobile_phone`` are NOT NULL in the
    database. They stay typed as Optional only for partial-update semantics
    (omit-to-leave-unchanged); an explicit ``null`` is rejected by validators
    so a PATCH cannot bypass the DB constraint.
    """

    name: str | None = Field(None, max_length=100)
    company_id: str | None = None
    address: str | None = Field(None, max_length=200)
    contact_email: EmailStr | None = Field(None, max_length=255)
    contact_first_name: str | None = Field(None, min_length=2, max_length=100)
    contact_last_name: str | None = Field(None, min_length=2, max_length=100)
    contact_mobile_phone: str | None = None
    contact_landline_phone: str | None = Field(None, max_length=20)

    @field_validator(
        "name",
        "address",
        "contact_email",
        "contact_first_name",
        "contact_last_name",
    )
    @classmethod
    def reject_explicit_null(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Field cannot be set to null on update")
        return v

    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("company_id cannot be set to null on update")
        if not re.fullmatch(r"\d{9}", v):
            raise ValueError("Company ID must be exactly 9 digits")
        return v

    @field_validator("contact_mobile_phone")
    @classmethod
    def validate_mobile_phone(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("contact_mobile_phone cannot be set to null on update")
        if not re.fullmatch(r"05[0-9]\d{7}", v):
            raise ValueError(
                "Mobile phone must be a valid Israeli mobile number (05X-XXXXXXX)"
            )
        return v


class AuditLogRead(BaseModel):
    """Audit log entry returned by the admin query endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    action: str
    target_type: str
    target_id: int
    detail: str | None
    ip_address: str | None
    created_at: datetime
