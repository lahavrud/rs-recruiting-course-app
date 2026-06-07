"""Tests for Pydantic schemas validation."""

import pytest
from pydantic import ValidationError

from src.schemas import (
    CandidateProfileCreate,
    CandidateProfileUpdate,
    JobAdminCreate,
    JobCreate,
    JobUpdate,
)


@pytest.mark.parametrize(
    "schema_class,create_kwargs,expected_path",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "050-000-0000",
                "resume_path": "uploads/resumes/test_resume.pdf",
            },
            "uploads/resumes/test_resume.pdf",
        ),
        (
            CandidateProfileUpdate,
            {"resume_path": "uploads/resumes/updated_resume.pdf"},
            "uploads/resumes/updated_resume.pdf",
        ),
    ],
)
def test_valid_resume_path(schema_class, create_kwargs, expected_path):
    """Test that valid paths within uploads/resumes/ are accepted."""
    schema = schema_class(**create_kwargs)
    assert schema.resume_path == expected_path


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "050-000-0000",
                "resume_path": None,
            },
        ),
        (CandidateProfileUpdate, {"resume_path": None}),
    ],
)
def test_none_resume_path(schema_class, create_kwargs):
    """Test that None is allowed for optional resume_path field."""
    schema = schema_class(**create_kwargs)
    assert schema.resume_path is None


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "../../../../etc/passwd",
            },
        ),
        (CandidateProfileUpdate, {"resume_path": "../../../../etc/passwd"}),
    ],
)
def test_path_traversal_parent_directory(schema_class, create_kwargs):
    """Test that paths with '..' are rejected (path traversal attack)."""
    with pytest.raises(
        ValidationError, match="Path cannot contain path traversal sequences"
    ):
        schema_class(**create_kwargs)


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "../config.py",
            },
        ),
        (CandidateProfileUpdate, {"resume_path": "../config.py"}),
    ],
)
def test_path_traversal_relative_parent(schema_class, create_kwargs):
    """Test that relative parent paths are rejected."""
    with pytest.raises(
        ValidationError, match="Path cannot contain path traversal sequences"
    ):
        schema_class(**create_kwargs)


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "/root/sensitive_file",
            },
        ),
        (CandidateProfileUpdate, {"resume_path": "/root/sensitive_file"}),
    ],
)
def test_absolute_path_rejected(schema_class, create_kwargs):
    """Test that absolute paths are rejected."""
    with pytest.raises(ValidationError, match="Path cannot be absolute"):
        schema_class(**create_kwargs)


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "config/secrets.env",
            },
        ),
        (CandidateProfileUpdate, {"resume_path": "config/secrets.env"}),
    ],
)
def test_path_outside_uploads_directory(schema_class, create_kwargs):
    """Test that paths outside uploads/resumes/ are accepted (validation simplified).

    Note: The validation no longer enforces the uploads/resumes/ directory structure
    as the service layer handles file uploads and sets resume_path automatically
    with UUID-based identifiers from the storage provider.
    """
    # Paths outside uploads/resumes/ are now accepted (as long as no path traversal)
    schema = schema_class(**create_kwargs)
    assert schema.resume_path == "config/secrets.env"


@pytest.mark.parametrize(
    "schema_class,create_kwargs,expected_path",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "050-000-0000",
                "resume_path": "uploads/resumes/2026/01/resume.pdf",
            },
            "uploads/resumes/2026/01/resume.pdf",
        ),
        (
            CandidateProfileUpdate,
            {"resume_path": "uploads/resumes/2026/01/updated.pdf"},
            "uploads/resumes/2026/01/updated.pdf",
        ),
    ],
)
def test_nested_valid_path(schema_class, create_kwargs, expected_path):
    """Test that nested paths within uploads/resumes/ are accepted."""
    schema = schema_class(**create_kwargs)
    assert schema.resume_path == expected_path


# ---------------------------------------------------------------------------
# Phone validation tests
# ---------------------------------------------------------------------------

BASE_CREATE = {
    "full_name": "Test User",
    "email": "test@example.com",
    "phone": "050-000-0000",
}


@pytest.mark.parametrize(
    "schema_class,phone,expected",
    [
        (CandidateProfileCreate, "0501234567", "0501234567"),
        (CandidateProfileCreate, "050-123-4567", "050-123-4567"),
        (CandidateProfileCreate, "050 123 4567", "050 123 4567"),
        (CandidateProfileUpdate, "(050) 123-4567", "(050) 123-4567"),
    ],
)
def test_valid_phone(schema_class, phone, expected):
    """Israeli mobile (10 digits starting with 05) — accepted in any common
    shape (spaces, dashes, parens), regardless of update vs create."""
    if schema_class is CandidateProfileCreate:
        kwargs = {**BASE_CREATE, "phone": phone}
    else:
        kwargs = {"phone": phone}
    schema = schema_class(**kwargs)
    assert schema.phone == expected


@pytest.mark.parametrize(
    "schema_class,phone,error_match",
    [
        (CandidateProfileCreate, "", "required"),
        (CandidateProfileCreate, "abc", "digits, spaces"),
        # 9 digits, looks Israeli but missing one — the bug that prompted
        # tightening from min-5-digits to a strict 05\\d{8} match.
        (CandidateProfileCreate, "051234567", "Israeli mobile"),
        # Landline (03) — no longer accepted; candidates must use a mobile.
        (CandidateProfileCreate, "(03) 123 4567", "Israeli mobile"),
        # International format — same number, but candidates must enter the
        # local form so we have a uniform shape downstream.
        (CandidateProfileCreate, "+972 50 123 4567", "Israeli mobile"),
        (CandidateProfileUpdate, "!@#$", "digits, spaces"),
        (CandidateProfileUpdate, "1234", "Israeli mobile"),
    ],
)
def test_invalid_phone(schema_class, phone, error_match):
    """Test that invalid phone numbers are rejected."""
    if schema_class is CandidateProfileCreate:
        kwargs = {**BASE_CREATE, "phone": phone}
    else:
        kwargs = {"phone": phone}
    with pytest.raises(ValidationError, match=error_match):
        schema_class(**kwargs)


def test_candidate_profile_update_phone_null_clears():
    """``phone`` is nullable on the model — explicit-null clears the column.

    Profile UX rule: only full_name + email are mandatory identity. Phone is
    autofill metadata; the user can drop it and re-enter it inline on the
    next apply-form submission.
    """
    patch = CandidateProfileUpdate(phone=None)
    # Pydantic keeps the explicit-None when set, so the field is in the dump.
    assert patch.model_dump(exclude_unset=True) == {"phone": None}


# ---------------------------------------------------------------------------
# LinkedIn URL validation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema_class,url,expected",
    [
        (
            CandidateProfileCreate,
            "https://www.linkedin.com/in/johndoe",
            "https://www.linkedin.com/in/johndoe",
        ),
        (CandidateProfileCreate, None, None),
        (CandidateProfileCreate, "", None),
        (
            CandidateProfileUpdate,
            "https://linkedin.com/company/acme",
            "https://linkedin.com/company/acme",
        ),
        (CandidateProfileUpdate, None, None),
    ],
)
def test_valid_linkedin_url(schema_class, url, expected):
    """Test that valid LinkedIn URLs are accepted."""
    if schema_class is CandidateProfileCreate:
        kwargs = {**BASE_CREATE, "linkedin_url": url}
    else:
        kwargs = {"linkedin_url": url}
    schema = schema_class(**kwargs)
    assert schema.linkedin_url == expected


@pytest.mark.parametrize(
    "schema_class,url,error_match",
    [
        # Wrong scheme (http is no longer accepted — https only)
        (CandidateProfileCreate, "http://linkedin.com/in/janedoe", "https"),
        (CandidateProfileCreate, "ftp://linkedin.com/in/foo", "https"),
        # Not a linkedin.com host (substring bypass attempt)
        (
            CandidateProfileCreate,
            "https://evil.com/linkedin.com/in/foo",
            "linkedin.com",
        ),
        # Missing scheme
        (CandidateProfileCreate, "linkedin.com/in/foo", "https"),
        # Wrong host entirely
        (CandidateProfileUpdate, "https://notlinkedin.com/in/foo", "linkedin.com"),
    ],
)
def test_invalid_linkedin_url(schema_class, url, error_match):
    """Test that invalid LinkedIn URLs are rejected."""
    if schema_class is CandidateProfileCreate:
        kwargs = {**BASE_CREATE, "linkedin_url": url}
    else:
        kwargs = {"linkedin_url": url}
    with pytest.raises(ValidationError, match=error_match):
        schema_class(**kwargs)


# ── Job schemas: salary_min must be <= salary_max ─────────────────────────────


_JOB_BASE = {
    "title": "Backend Engineer",
    "short_description": "Backend role on the platform team.",
    "description": "Build services.",
    "requirements": [
        {"text": "Python fluency"},
        {"text": "FastAPI experience"},
        {"text": "PostgreSQL"},
    ],
    "location": "Tel Aviv",
}


@pytest.mark.parametrize(
    "schema_class, extra",
    [
        (JobCreate, {}),
        (JobAdminCreate, {"company_id": 1}),
    ],
)
def test_job_create_rejects_inverted_salary_range(schema_class, extra):
    """JobCreate / JobAdminCreate reject salary_min > salary_max."""
    with pytest.raises(ValidationError, match="salary_min must be <= salary_max"):
        schema_class(**_JOB_BASE, **extra, salary_min=30000, salary_max=20000)


def test_job_create_accepts_equal_salaries():
    """Equal salary_min and salary_max is a valid single-point range."""
    job = JobCreate(**_JOB_BASE, salary_min=20000, salary_max=20000)
    assert job.salary_min == job.salary_max == 20000


def test_job_update_rejects_inverted_salary_range_when_both_set():
    """JobUpdate enforces the range when both bounds are in the same payload."""
    with pytest.raises(ValidationError, match="salary_min must be <= salary_max"):
        JobUpdate(salary_min=30000, salary_max=20000)


def test_job_update_allows_partial_salary_change():
    """JobUpdate is OK when only one bound is set (DB CHECK guards the rest)."""
    JobUpdate(salary_min=25000)  # no salary_max in payload -> no schema check
    JobUpdate(salary_max=25000)  # symmetric
