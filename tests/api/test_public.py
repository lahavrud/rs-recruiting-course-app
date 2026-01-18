"""Integration tests for public API endpoints (no authentication required)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.core.infrastructure.database import get_session
from src.enums import JobStatus
from src.main import app
from src.models import CompanyProfile, Job, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth import register_company_user
from tests.conftest import TestSessionLocal


@pytest.fixture
async def company_user(test_db):
    """Create an approved company user for testing."""
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password="password",
            company_profile=CompanyProfileCreate(name="Test Company"),
        )
        result = await register_company_user(user_data, session)
        await session.commit()
        # Activate the user (simulate admin approval)
        user = result.user
        user.is_active = True
        await session.commit()
        return result.user


@pytest.fixture
async def company_profile(company_user: User):
    """Get company profile for testing."""
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                CompanyProfile.user_id == company_user.id
            )
        )
        return result.scalar_one()


@pytest.fixture
async def published_job(company_profile: CompanyProfile):
    """Create a published job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            description="We are looking for a senior Python developer...",
            requirements="5+ years experience with Python, FastAPI, PostgreSQL",
            location="Tel Aviv, Israel",
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def pending_job(company_profile: CompanyProfile):
    """Create a pending job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Junior Developer",
            description="We are looking for a junior developer...",
            requirements="1+ years experience",
            location="Remote",
            status=JobStatus.PENDING_APPROVAL,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def closed_job(company_profile: CompanyProfile):
    """Create a closed job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Closed Position",
            description="This position is closed",
            requirements="N/A",
            location="N/A",
            status=JobStatus.CLOSED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def client():
    """Create test client without authentication (public endpoints)."""

    async def override_get_session():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_public_jobs_empty(client: AsyncClient):
    """Test getting public jobs when none exist."""
    response = await client.get("/api/public/jobs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_public_jobs_only_published(
    client: AsyncClient,
    company_profile: CompanyProfile,
    published_job: Job,
    pending_job: Job,
    closed_job: Job,
):
    """Test that public endpoint only returns published jobs."""
    response = await client.get("/api/public/jobs")
    assert response.status_code == 200

    data = response.json()
    # Should only return published job, not pending or closed
    assert len(data) == 1
    assert data[0]["id"] == published_job.id
    assert data[0]["status"] == "PUBLISHED"
    assert data[0]["title"] == "Senior Python Developer"


@pytest.mark.asyncio
async def test_get_public_jobs_multiple_published(
    client: AsyncClient, company_profile: CompanyProfile, published_job: Job
):
    """Test getting multiple published jobs."""
    # Create another published job
    async with TestSessionLocal() as session:
        job2 = Job(
            company_id=company_profile.id,
            title="Frontend Developer",
            description="We are looking for a frontend developer...",
            requirements="3+ years experience with React",
            location="Tel Aviv, Israel",
            status=JobStatus.PUBLISHED,
        )
        session.add(job2)
        await session.commit()

    response = await client.get("/api/public/jobs")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    # Should be ordered by creation date (newest first)
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)
    assert all("status" in job for job in data)
    assert all(job["status"] == "PUBLISHED" for job in data)


@pytest.mark.asyncio
async def test_get_public_job_success(client: AsyncClient, published_job: Job):
    """Test getting a specific published job."""
    response = await client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == published_job.id
    assert data["title"] == published_job.title
    assert data["description"] == published_job.description
    assert data["requirements"] == published_job.requirements
    assert data["location"] == published_job.location
    assert data["status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_get_public_job_not_found(client: AsyncClient):
    """Test getting a non-existent job returns 404."""
    response = await client.get("/api/public/jobs/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_public_job_pending_not_visible(
    client: AsyncClient, pending_job: Job
):
    """Test that pending jobs are not visible via public endpoint."""
    response = await client.get(f"/api/public/jobs/{pending_job.id}")
    assert response.status_code == 404
    detail = response.json()["detail"].lower()
    assert "not published" in detail or "not found" in detail


@pytest.mark.asyncio
async def test_get_public_job_closed_not_visible(client: AsyncClient, closed_job: Job):
    """Test that closed jobs are not visible via public endpoint."""
    response = await client.get(f"/api/public/jobs/{closed_job.id}")
    assert response.status_code == 404
    detail = response.json()["detail"].lower()
    assert "not published" in detail or "not found" in detail


@pytest.mark.asyncio
async def test_public_endpoints_no_auth_required(
    client: AsyncClient, published_job: Job
):
    """Test that public endpoints work without authentication."""
    # These endpoints should work without any auth token
    response = await client.get("/api/public/jobs")
    assert response.status_code == 200

    response = await client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200
