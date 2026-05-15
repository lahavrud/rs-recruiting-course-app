"""Tests for CandidateProfile model."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CandidateProfile


@pytest.mark.asyncio
async def test_candidate_profile_creation(session: AsyncSession):
    """Test creating a CandidateProfile model."""
    candidate = CandidateProfile(
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone="+1234567890",
        resume_path="/uploads/resumes/jane_doe.pdf",
        linkedin_url="https://linkedin.com/in/janedoe",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    # Verify candidate was created
    assert candidate.id is not None
    assert candidate.full_name == "Jane Doe"
    assert candidate.email == "jane.doe@example.com"
    assert candidate.created_at is not None


@pytest.mark.asyncio
async def test_candidate_profile_minimal_data(session: AsyncSession):
    """Test creating a candidate with minimal required data."""
    candidate = CandidateProfile(
        full_name="John Smith",
        email="john.smith@example.com",
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.full_name == "John Smith"
    assert candidate.phone == "050-000-0000"
    assert candidate.resume_path is None
    assert candidate.linkedin_url is None


@pytest.mark.asyncio
async def test_candidate_profile_unique_email(session: AsyncSession):
    """Test that email must be unique."""
    candidate1 = CandidateProfile(
        full_name="User One",
        email="duplicate@example.com",
        phone="050-000-0000",
    )
    session.add(candidate1)
    await session.commit()

    # Attempting to create another candidate with same email should fail
    candidate2 = CandidateProfile(
        full_name="User Two",
        email="duplicate@example.com",
        phone="050-000-0000",
    )
    session.add(candidate2)

    with pytest.raises(Exception):  # Should raise IntegrityError
        await session.commit()


@pytest.mark.asyncio
async def test_candidate_profile_query_by_email(session: AsyncSession):
    """Test querying candidates by email."""
    candidate = CandidateProfile(
        full_name="Query Test",
        email="query@example.com",
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.commit()

    # Query by email
    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.email == "query@example.com"  # type: ignore[arg-type]
        )
    )
    found_candidate = result.scalar_one()

    assert found_candidate.full_name == "Query Test"
    assert found_candidate.email == "query@example.com"


# Security Tests: Path Traversal Prevention
# Note: field_validator runs during model_validate(), not during direct instantiation
# These tests use model_validate() which simulates API input validation


def test_candidate_profile_path_traversal_parent_directory():
    """Test that paths with '..' are rejected (path traversal attack)."""
    with pytest.raises(ValueError, match="Path cannot contain '..'"):
        CandidateProfile.model_validate(
            {
                "full_name": "Malicious User",
                "email": "malicious1@example.com",
                "phone": "050-000-0000",
                "resume_path": "../../../../etc/passwd",
            }
        )


def test_candidate_profile_path_traversal_relative_parent():
    """Test that relative parent paths are rejected."""
    with pytest.raises(ValueError, match="Path cannot contain '..'"):
        CandidateProfile.model_validate(
            {
                "full_name": "Malicious User",
                "email": "malicious2@example.com",
                "phone": "050-000-0000",
                "resume_path": "../config.py",
            }
        )


def test_candidate_profile_absolute_path_rejected():
    """Test that absolute paths are rejected."""
    with pytest.raises(ValueError, match="Path cannot be absolute"):
        CandidateProfile.model_validate(
            {
                "full_name": "Malicious User",
                "email": "malicious3@example.com",
                "phone": "050-000-0000",
                "resume_path": "/root/sensitive_file",
            }
        )


def test_candidate_profile_path_outside_uploads_directory():
    """Test that paths outside uploads/resumes/ are rejected."""
    with pytest.raises(ValueError, match="Path must be within 'uploads/resumes/'"):
        CandidateProfile.model_validate(
            {
                "full_name": "Malicious User",
                "email": "malicious4@example.com",
                "phone": "050-000-0000",
                "resume_path": "config/secrets.env",
            }
        )


@pytest.mark.asyncio
async def test_candidate_profile_valid_resume_path(session: AsyncSession):
    """Test that valid paths within uploads/resumes/ are accepted."""
    candidate_data = {
        "full_name": "Valid User",
        "email": "valid@example.com",
        "phone": "050-000-0000",
        "resume_path": "uploads/resumes/valid_resume.pdf",
    }
    candidate = CandidateProfile.model_validate(candidate_data)
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.resume_path == "uploads/resumes/valid_resume.pdf"


@pytest.mark.asyncio
async def test_candidate_profile_none_resume_path_allowed(session: AsyncSession):
    """Test that None is allowed for optional resume_path field."""
    candidate = CandidateProfile(
        full_name="No Resume User",
        email="noresume@example.com",
        resume_path=None,
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.resume_path is None


@pytest.mark.asyncio
async def test_candidate_profile_nested_valid_path(session: AsyncSession):
    """Test that nested paths within uploads/resumes/ are accepted."""
    candidate_data = {
        "full_name": "Nested Path User",
        "email": "nested@example.com",
        "phone": "050-000-0000",
        "resume_path": "uploads/resumes/2026/01/resume.pdf",
    }
    candidate = CandidateProfile.model_validate(candidate_data)
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.resume_path == "uploads/resumes/2026/01/resume.pdf"
