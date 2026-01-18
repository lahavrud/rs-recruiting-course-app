"""Tests for admin job approval endpoints."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlmodel import SQLModel

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin, get_current_user
from src.core.infrastructure.security import get_password_hash
from src.enums import JobStatus, UserRole
from src.main import app
from src.models import CompanyProfile, Job, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth import register_company_user
from tests.conftest import TestSessionLocal, test_engine


async def override_get_session():
    """Override get_session dependency for tests."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def admin_user():
    """Create an admin user for authentication."""
    # Ensure tables exist (idempotent)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with TestSessionLocal() as session:
        admin = User(
            email="admin@test.com",
            hashed_password=get_password_hash("adminpassword"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


@pytest.fixture(scope="function")
async def approved_company_user():
    """Create an approved company user with profile."""
    with patch("src.services.auth.enqueue_email_task") as mock_enqueue:
        mock_enqueue.return_value = "test-job-id"
        async with TestSessionLocal() as session:
            user_data = UserCreate(
                email="approved@test.com",
                password="password",
                company_profile=CompanyProfileCreate(name="Approved Company"),
            )
            result = await register_company_user(user_data, session)
            # Activate the user (simulate admin approval)
            result.user.is_active = True
            await session.commit()
            return result.user


@pytest.fixture(scope="function")
async def company_profile(approved_company_user: User):
    """Get company profile for approved company user."""
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                CompanyProfile.user_id == approved_company_user.id
            )
        )
        return result.scalar_one()


@pytest.fixture(scope="function")
async def pending_job(company_profile: CompanyProfile):
    """Create a pending job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            description="We are looking for a senior Python developer...",
            requirements="5+ years experience with Python, FastAPI, PostgreSQL",
            location="Tel Aviv, Israel",
            status=JobStatus.PENDING_APPROVAL,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


def setup_admin_overrides(admin_user):
    """Helper function to set up admin authentication overrides."""
    # Override database dependency
    app.dependency_overrides[get_session] = override_get_session

    # Override get_current_user to return admin_user directly (no DB query)
    # Accept same parameters as original but ignore them
    async def override_get_current_user(
        credentials=None,  # noqa: ARG001
        session=None,  # noqa: ARG001
    ):
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_admin] = override_get_current_user


@pytest.fixture(scope="function")
async def client(admin_user):
    """Create test client with overridden dependencies."""
    setup_admin_overrides(admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_get_pending_jobs_empty(client: AsyncClient):
    """Test getting pending jobs when none exist."""
    response = await client.get("/api/admin/jobs/pending")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_pending_jobs(
    client: AsyncClient, company_profile: CompanyProfile, pending_job: Job
):
    """Test getting list of pending jobs."""
    # Create another pending job
    async with TestSessionLocal() as session:
        job2 = Job(
            company_id=company_profile.id,
            title="Frontend Developer",
            description="We are looking for a frontend developer...",
            requirements="3+ years experience with React",
            location="Remote",
            status=JobStatus.PENDING_APPROVAL,
        )
        session.add(job2)
        await session.commit()

    response = await client.get("/api/admin/jobs/pending")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    # Should be ordered by creation date (oldest first)
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)
    assert all(job["status"] == "PENDING_APPROVAL" for job in data)


@pytest.mark.asyncio
async def test_get_pending_jobs_excludes_published_and_closed(
    client: AsyncClient, company_profile: CompanyProfile, pending_job: Job
):
    """Test that pending jobs endpoint only returns pending jobs."""
    # Create published and closed jobs
    async with TestSessionLocal() as session:
        published_job = Job(
            company_id=company_profile.id,
            title="Published Job",
            description="This is published",
            requirements="N/A",
            location="N/A",
            status=JobStatus.PUBLISHED,
        )
        closed_job = Job(
            company_id=company_profile.id,
            title="Closed Job",
            description="This is closed",
            requirements="N/A",
            location="N/A",
            status=JobStatus.CLOSED,
        )
        session.add(published_job)
        session.add(closed_job)
        await session.commit()

    response = await client.get("/api/admin/jobs/pending")
    assert response.status_code == 200

    data = response.json()
    # Should only return pending job
    assert len(data) == 1
    assert data[0]["id"] == pending_job.id
    assert data[0]["status"] == "PENDING_APPROVAL"


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_approve_job_success(
    mock_enqueue_email, client: AsyncClient, pending_job: Job
):
    """Test successfully approving a job."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await client.post(f"/api/admin/jobs/{pending_job.id}/approve")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == pending_job.id
    assert data["status"] == "PUBLISHED"

    # Verify in database
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.id == pending_job.id)  # pyright: ignore[reportArgumentType]
        )
        job = result.scalar_one()
        assert job.status == JobStatus.PUBLISHED

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_approve_job_not_found(client: AsyncClient):
    """Test approving a non-existent job returns 404."""
    response = await client.post("/api/admin/jobs/99999/approve")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_approve_job_already_published(
    client: AsyncClient, company_profile: CompanyProfile
):
    """Test approving an already published job returns 400."""
    # Create a published job
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Published Job",
            description="This is published",
            requirements="N/A",
            location="N/A",
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    # Try to approve
    response = await client.post(f"/api/admin/jobs/{job.id}/approve")
    assert response.status_code == 400
    assert "not pending" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_reject_job_success(
    mock_enqueue_email, client: AsyncClient, pending_job: Job
):
    """Test successfully rejecting a job."""
    mock_enqueue_email.return_value = "test-job-id"
    job_id = pending_job.id

    response = await client.post(f"/api/admin/jobs/{job_id}/reject")
    assert response.status_code == 204

    # Verify job status is CLOSED
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
        )
        job = result.scalar_one()
        assert job.status == JobStatus.CLOSED

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_reject_job_not_found(client: AsyncClient):
    """Test rejecting a non-existent job returns 404."""
    response = await client.post("/api/admin/jobs/99999/reject")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reject_job_already_published(
    client: AsyncClient, company_profile: CompanyProfile
):
    """Test rejecting an already published job returns 400."""
    # Create a published job
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Published Job",
            description="This is published",
            requirements="N/A",
            location="N/A",
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    # Try to reject
    response = await client.post(f"/api/admin/jobs/{job.id}/reject")
    assert response.status_code == 400
    assert "not pending" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_job_endpoints_require_auth(test_db, admin_user):
    """Test that admin job endpoints require authentication."""
    # Clear any existing overrides from session-scoped fixtures
    app.dependency_overrides.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Override only database, not auth
        app.dependency_overrides[get_session] = override_get_session

        response = await client.get("/api/admin/jobs/pending")
        assert response.status_code == 401  # Unauthorized (no auth token)

        response = await client.post("/api/admin/jobs/1/approve")
        assert response.status_code == 401

        response = await client.post("/api/admin/jobs/1/reject")
        assert response.status_code == 401

    app.dependency_overrides.clear()
    # Restore admin overrides for subsequent tests
    setup_admin_overrides(admin_user)


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_admin_job_endpoints_require_admin_role(
    mock_enqueue_email, test_db, admin_user
):
    """Test that admin job endpoints require admin role."""
    # Clear any existing overrides from session-scoped fixtures
    app.dependency_overrides.clear()

    mock_enqueue_email.return_value = "test-job-id"
    # Create a company user (not admin)
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password="password",
            company_profile=CompanyProfileCreate(name="Company"),
        )
        result = await register_company_user(user_data, session)
        await session.commit()
        company_user = result.user

    # Override get_current_user to return company user
    async def override_get_current_company_user():
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == company_user.id)  # pyright: ignore[reportArgumentType]
            )
            return result.scalar_one()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_company_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/admin/jobs/pending")
        assert response.status_code == 403  # Forbidden (not admin)
        assert "admin" in response.json()["detail"].lower()

        response = await client.post("/api/admin/jobs/1/approve")
        assert response.status_code == 403

        response = await client.post("/api/admin/jobs/1/reject")
        assert response.status_code == 403

    app.dependency_overrides.clear()
    # Restore admin overrides for subsequent tests
    setup_admin_overrides(admin_user)
