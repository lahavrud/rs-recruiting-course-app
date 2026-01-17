"""Tests for CandidateProfile model."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from src.models import CandidateProfile

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session factory
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[None, None]:
    """Create and drop test database tables for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
async def session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with TestSessionLocal() as session:
        yield session


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
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.full_name == "John Smith"
    assert candidate.phone is None
    assert candidate.resume_path is None
    assert candidate.linkedin_url is None


@pytest.mark.asyncio
async def test_candidate_profile_unique_email(session: AsyncSession):
    """Test that email must be unique."""
    candidate1 = CandidateProfile(
        full_name="User One",
        email="duplicate@example.com",
    )
    session.add(candidate1)
    await session.commit()

    # Attempting to create another candidate with same email should fail
    candidate2 = CandidateProfile(
        full_name="User Two",
        email="duplicate@example.com",
    )
    session.add(candidate2)

    with pytest.raises(Exception):  # Should raise IntegrityError
        await session.commit()


@pytest.mark.asyncio
async def test_candidate_profile_interview_fields(session: AsyncSession):
    """Test interview form fields can be stored."""
    candidate = CandidateProfile(
        full_name="Interview Candidate",
        email="interview@example.com",
        service_concept="I understand the role is about...",
        salary_expectations="15,000 - 20,000 ILS per month",
        military_service_details="Completed military service in 2018",
        transportation="Own car, can travel",
        personality_weakness="Sometimes too detail-oriented",
        personality_strength="Strong problem-solving skills",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    # Verify interview fields are stored correctly
    assert candidate.service_concept == "I understand the role is about..."
    assert candidate.salary_expectations == "15,000 - 20,000 ILS per month"
    assert candidate.military_service_details == "Completed military service in 2018"
    assert candidate.transportation == "Own car, can travel"
    assert candidate.personality_weakness == "Sometimes too detail-oriented"
    assert candidate.personality_strength == "Strong problem-solving skills"


@pytest.mark.asyncio
async def test_candidate_profile_long_text_fields(session: AsyncSession):
    """Test that text fields can handle long content."""
    long_text = "This is a very long text " * 100  # 2500+ characters

    candidate = CandidateProfile(
        full_name="Long Text User",
        email="longtext@example.com",
        service_concept=long_text,
        salary_expectations=long_text,
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.service_concept is not None
    assert len(candidate.service_concept) > 2000
    assert candidate.service_concept == long_text


@pytest.mark.asyncio
async def test_candidate_profile_query_by_email(session: AsyncSession):
    """Test querying candidates by email."""
    candidate = CandidateProfile(
        full_name="Query Test",
        email="query@example.com",
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


@pytest.mark.asyncio
async def test_candidate_profile_no_authentication(session: AsyncSession):
    """Test that CandidateProfile has no password or authentication fields."""
    candidate = CandidateProfile(
        full_name="No Auth User",
        email="noauth@example.com",
    )

    # Verify there's no password or auth-related fields
    assert not hasattr(candidate, "password")
    assert not hasattr(candidate, "hashed_password")
    assert not hasattr(candidate, "is_active")
    assert not hasattr(candidate, "role")


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
                "resume_path": "config/secrets.env",
            }
        )


@pytest.mark.asyncio
async def test_candidate_profile_valid_resume_path(session: AsyncSession):
    """Test that valid paths within uploads/resumes/ are accepted."""
    candidate_data = {
        "full_name": "Valid User",
        "email": "valid@example.com",
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
        "resume_path": "uploads/resumes/2026/01/resume.pdf",
    }
    candidate = CandidateProfile.model_validate(candidate_data)
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.resume_path == "uploads/resumes/2026/01/resume.pdf"
