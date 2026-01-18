"""Unit tests for public job board service functions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import JobStatus, UserRole
from src.models import CompanyProfile, Job, User
from src.services.exceptions import JobNotFoundError
from src.services.jobs_public import get_published_job, list_published_jobs


@pytest.fixture
async def company_with_user(session: AsyncSession) -> CompanyProfile:
    """Create a company user and profile for testing."""
    user = User(
        email="company@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None

    company = CompanyProfile(
        user_id=user.id,
        name="Test Company",
        contact_person="John Doe",
        contact_phone="123-456-7890",
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    assert company.id is not None
    return company


@pytest.mark.asyncio
async def test_list_published_jobs_empty(session: AsyncSession):
    """Test listing published jobs when none exist."""
    jobs = await list_published_jobs(session)
    assert jobs == []


@pytest.mark.asyncio
async def test_list_published_jobs(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test listing published jobs."""
    # Create multiple published jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Job 1",
        description="Description 1",
        requirements="Requirements 1",
        location="Location 1",
        status=JobStatus.PUBLISHED,
    )
    job2 = Job(
        company_id=company_with_user.id,
        title="Job 2",
        description="Description 2",
        requirements="Requirements 2",
        location="Location 2",
        status=JobStatus.PUBLISHED,
    )
    # Create a pending job (should not be included)
    pending_job = Job(
        company_id=company_with_user.id,
        title="Pending Job",
        description="Description",
        requirements="Requirements",
        location="Location",
        status=JobStatus.PENDING_APPROVAL,
    )
    session.add(job1)
    session.add(job2)
    session.add(pending_job)
    await session.commit()

    jobs = await list_published_jobs(session)

    assert len(jobs) == 2
    assert all(job.status == JobStatus.PUBLISHED for job in jobs)
    # Should be ordered by creation date (newest first)
    assert jobs[0].title == "Job 2"
    assert jobs[1].title == "Job 1"


@pytest.mark.asyncio
async def test_get_published_job_success(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test getting a published job by ID."""
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
        status=JobStatus.PUBLISHED,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    result = await get_published_job(job.id, session)

    assert result.id == job.id
    assert result.title == "Senior Python Developer"
    assert result.status == JobStatus.PUBLISHED


@pytest.mark.asyncio
async def test_get_published_job_not_found(session: AsyncSession):
    """Test getting a non-existent job."""
    with pytest.raises(JobNotFoundError, match="not found"):
        await get_published_job(99999, session)


@pytest.mark.asyncio
async def test_get_published_job_not_published(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test getting a job that is not published."""
    job = Job(
        company_id=company_with_user.id,
        title="Pending Job",
        description="Description",
        requirements="Requirements",
        location="Location",
        status=JobStatus.PENDING_APPROVAL,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    with pytest.raises(JobNotFoundError, match="not published"):
        await get_published_job(job.id, session)
