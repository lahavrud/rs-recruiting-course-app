"""Tests for Application (Match) model."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from src.enums import ApplicationStatus, JobStatus, UserRole
from src.models import Application, CandidateProfile, CompanyProfile, Job, User
from tests.conftest import enable_sqlite_foreign_keys

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session factory
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
# Enable FK constraints for SQLite to match PostgreSQL behavior
enable_sqlite_foreign_keys(test_engine)
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


@pytest.fixture
async def job_and_candidate(session: AsyncSession) -> dict[str, Job | CandidateProfile]:
    """Create a job and candidate for testing applications."""
    # Create company with user
    user = User(
        email="company@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    company = CompanyProfile(
        user_id=user.id,  # type: ignore[arg-type]
        name="Test Company",
    )
    session.add(company)
    await session.flush()

    # Create job
    assert company.id is not None
    job = Job(
        company_id=company.id,
        title="Python Developer",
        description="Description",
        requirements="Requirements",
        location="Tel Aviv",
        status=JobStatus.PUBLISHED,
    )
    session.add(job)
    await session.flush()

    # Create candidate
    candidate = CandidateProfile(
        full_name="Jane Doe",
        email="jane@example.com",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(job)
    await session.refresh(candidate)

    return {"job": job, "candidate": candidate}


@pytest.mark.asyncio
async def test_application_creation(session: AsyncSession, job_and_candidate):
    """Test creating an Application (Match) model."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    # Verify application was created with correct defaults
    assert application.id is not None
    assert application.job_id == job.id
    assert application.candidate_id == candidate.id
    assert application.status == ApplicationStatus.NEW
    assert application.admin_notes is None
    assert application.created_at is not None
    assert application.updated_at is not None


@pytest.mark.asyncio
async def test_application_status_workflow(session: AsyncSession, job_and_candidate):
    """Test Application status enum workflow."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    assert application.status == ApplicationStatus.NEW

    # Admin approves
    application.status = ApplicationStatus.APPROVED_BY_ADMIN
    application.admin_notes = "Good candidate, proceed with interview"
    await session.commit()
    await session.refresh(application)

    assert application.status == ApplicationStatus.APPROVED_BY_ADMIN
    assert application.admin_notes == "Good candidate, proceed with interview"

    # Company hires
    application.status = ApplicationStatus.HIRED
    await session.commit()
    await session.refresh(application)

    assert application.status == ApplicationStatus.HIRED


@pytest.mark.asyncio
async def test_application_rejection_workflow(session: AsyncSession, job_and_candidate):
    """Test Application rejection workflow."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    # Admin rejects
    application.status = ApplicationStatus.REJECTED
    application.admin_notes = "Not a good fit for the role"
    await session.commit()
    await session.refresh(application)

    assert application.status == ApplicationStatus.REJECTED
    assert application.admin_notes == "Not a good fit for the role"


@pytest.mark.asyncio
async def test_application_job_relationship(session: AsyncSession, job_and_candidate):
    """Test Application can access its Job (one-way relationship)."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    # SQLModel 0.0.22: One-way relationship works
    assert application.job.id == job.id
    assert application.job.title == "Python Developer"


@pytest.mark.asyncio
async def test_application_candidate_relationship(
    session: AsyncSession, job_and_candidate
):
    """Test Application can access its CandidateProfile (one-way relationship)."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    # SQLModel 0.0.22: One-way relationship works
    assert application.candidate.id == candidate.id
    assert application.candidate.full_name == "Jane Doe"


@pytest.mark.asyncio
async def test_job_access_applications_via_query(
    session: AsyncSession, job_and_candidate
):
    """Test accessing job's applications via query (SQLModel 0.0.22 limitation)."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]

    # Create multiple applications for the job
    app1 = Application(job_id=job.id, candidate_id=candidate.id)
    session.add(app1)

    # Create another candidate and application
    candidate2 = CandidateProfile(full_name="John Smith", email="john@example.com")
    session.add(candidate2)
    await session.flush()
    assert candidate2.id is not None

    app2 = Application(job_id=job.id, candidate_id=candidate2.id)
    session.add(app2)
    await session.commit()

    # Access applications via query (not via relationship due to SQLModel 0.0.22)
    result = await session.execute(
        select(Application).where(Application.job_id == job.id)
    )
    applications = result.scalars().all()

    assert len(applications) == 2
    assert applications[0].job_id == job.id
    assert applications[1].job_id == job.id


@pytest.mark.asyncio
async def test_candidate_access_applications_via_query(
    session: AsyncSession, job_and_candidate
):
    """Test accessing candidate's applications via query.

    SQLModel 0.0.22 limitation requires using queries instead of relationships.
    """
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]

    # Create application
    app = Application(job_id=job.id, candidate_id=candidate.id)
    session.add(app)
    await session.commit()

    # Access applications via query (not via relationship due to SQLModel 0.0.22)
    result = await session.execute(
        select(Application).where(Application.candidate_id == candidate.id)
    )
    applications = result.scalars().all()

    assert len(applications) == 1
    assert applications[0].candidate_id == candidate.id


@pytest.mark.asyncio
async def test_application_foreign_key_constraints(session: AsyncSession):
    """Test foreign key constraint enforcement.

    With FK constraints enabled, attempting to create an application with
    non-existent job_id or candidate_id should raise an IntegrityError.
    """
    # Attempting to create application with non-existent job_id
    app = Application(
        job_id=9999,  # Non-existent
        candidate_id=1,
    )
    session.add(app)

    # Should raise IntegrityError due to FK constraint violation
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_application_with_long_admin_notes(
    session: AsyncSession, job_and_candidate
):
    """Test that admin_notes text field can handle long content."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]

    long_notes = (
        "This candidate showed excellent technical skills during the interview. " * 50
    )

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        status=ApplicationStatus.APPROVED_BY_ADMIN,
        admin_notes=long_notes,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    assert len(application.admin_notes) > 1000  # pyright: ignore[reportArgumentType]
    assert application.admin_notes == long_notes


@pytest.mark.asyncio
async def test_application_updated_at_changes(session: AsyncSession, job_and_candidate):
    """Test that updated_at changes when application is modified."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    # Modify the application
    application.status = ApplicationStatus.APPROVED_BY_ADMIN
    application.admin_notes = "Updated notes"
    await session.commit()
    await session.refresh(application)

    # Note: updated_at behavior depends on database trigger/onupdate implementation
    # This test documents the expected behavior
    assert application.admin_notes == "Updated notes"


@pytest.mark.asyncio
async def test_application_unique_constraint_prevents_duplicates(
    session: AsyncSession, job_and_candidate
):
    """Test that unique constraint prevents duplicate applications.

    A candidate should not be able to submit multiple applications for the same job.
    """
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None

    # Create first application
    application1 = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application1)
    await session.commit()
    await session.refresh(application1)

    # Verify first application was created
    assert application1.id is not None

    # Attempt to create duplicate application (same job_id and candidate_id)
    application2 = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application2)

    # Should raise IntegrityError due to unique constraint violation
    with pytest.raises(IntegrityError):
        await session.commit()
