"""Tests for admin job approval endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.enums import JobStatus
from src.models import CompanyProfile, Job
from tests.conftest import TestSessionLocal
from tests.factories import FAKE_LOGO, FAKE_SIG_B64


@pytest.mark.asyncio
async def test_get_pending_jobs_empty(admin_client: AsyncClient):
    """Test getting pending jobs when none exist."""
    response = await admin_client.get("/api/admin/jobs/pending")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_pending_jobs(
    admin_client: AsyncClient, company_profile: CompanyProfile, pending_job: Job
):
    """Test getting list of pending jobs."""
    # Create another pending job
    assert company_profile.id is not None
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

    response = await admin_client.get("/api/admin/jobs/pending")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    # Should be ordered by creation date (oldest first)
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)
    assert all(job["status"] == "PENDING_APPROVAL" for job in data)


@pytest.mark.asyncio
async def test_get_pending_jobs_excludes_published_and_closed(
    admin_client: AsyncClient, company_profile: CompanyProfile, pending_job: Job
):
    """Test that pending jobs endpoint only returns pending jobs."""
    # Create published and closed jobs
    assert company_profile.id is not None
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

    response = await admin_client.get("/api/admin/jobs/pending")
    assert response.status_code == 200

    data = response.json()
    # Should only return pending job
    assert len(data) == 1
    assert data[0]["id"] == pending_job.id
    assert data[0]["status"] == "PENDING_APPROVAL"


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_approve_job_success(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test successfully approving a job."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(f"/api/admin/jobs/{pending_job.id}/approve")
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
async def test_approve_job_not_found(admin_client: AsyncClient):
    """Test approving a non-existent job returns 404."""
    response = await admin_client.post("/api/admin/jobs/99999/approve")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_approve_job_already_published(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    """Test approving an already published job returns 400."""
    # Create a published job
    assert company_profile.id is not None
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
    response = await admin_client.post(f"/api/admin/jobs/{job.id}/approve")
    assert response.status_code == 400
    assert "not pending" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_reject_job_success(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test successfully rejecting a job."""
    mock_enqueue_email.return_value = "test-job-id"
    job_id = pending_job.id

    response = await admin_client.post(f"/api/admin/jobs/{job_id}/reject")
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
async def test_reject_job_not_found(admin_client: AsyncClient):
    """Test rejecting a non-existent job returns 404."""
    response = await admin_client.post("/api/admin/jobs/99999/reject")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reject_job_already_published(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    """Test rejecting an already published job returns 400."""
    # Create a published job
    assert company_profile.id is not None
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
    response = await admin_client.post(f"/api/admin/jobs/{job.id}/reject")
    assert response.status_code == 400
    assert "not pending" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_contact_job_success(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test successfully sending a contact email for a job."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{pending_job.id}/contact",
        json={"admin_note": "נא לעדכן את דרישות המשרה."},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_contact_job_no_note(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test contact email with empty admin note (optional field)."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{pending_job.id}/contact",
        json={"admin_note": ""},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_contact_job_no_body(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test contact email with no request body (admin_note defaults to empty string)."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{pending_job.id}/contact",
        json={},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_contact_job_not_found(admin_client: AsyncClient):
    """Test contacting a non-existent job returns 404."""
    response = await admin_client.post(
        "/api/admin/jobs/99999/contact",
        json={"admin_note": "test"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("src.services.jobs_admin.enqueue_email_task")
async def test_contact_job_works_for_published_job(
    mock_enqueue_email, admin_client: AsyncClient, company_profile: CompanyProfile
):
    """Test contact email works for any job status (not just pending)."""
    assert company_profile.id is not None
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Published Job",
            description="Description",
            requirements="Requirements",
            location="Tel Aviv",
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{job.id}/contact",
        json={"admin_note": "Follow-up on published job."},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_admin_job_endpoints_require_auth(test_db):
    """Test that admin job endpoints require authentication."""
    from httpx import ASGITransport, AsyncClient

    from src.core.infrastructure.database import get_session
    from src.main import app
    from tests.conftest import override_get_session

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

        response = await client.post(
            "/api/admin/jobs/1/contact", json={"admin_note": ""}
        )
        assert response.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_admin_job_endpoints_require_admin_role(mock_enqueue_email, test_db):
    """Test that admin job endpoints require admin role."""
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from src.core.infrastructure.database import get_session
    from src.core.infrastructure.dependencies import get_current_user
    from src.main import app
    from src.models import User
    from src.schemas import CompanyProfileCreate, UserCreate
    from src.services.auth import register_company_user
    from tests.conftest import override_get_session

    app.dependency_overrides.clear()

    mock_enqueue_email.return_value = "test-job-id"
    # Create a company user (not admin)
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password="SecurePass1!",
            company_profile=CompanyProfileCreate(
                name="Company",
                company_id="123456789",
                address="רח׳ הדוגמה 1, תל אביב",
                contact_first_name="ישראל",
                contact_last_name="ישראלי",
                contact_mobile_phone="0501234567",
            ),
        )

        result = await register_company_user(
            user_data,
            session,
            FAKE_LOGO,
            "logo.png",
            "image/png",
            FAKE_SIG_B64,
        )
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

        response = await client.post(
            "/api/admin/jobs/1/contact", json={"admin_note": ""}
        )
        assert response.status_code == 403

    app.dependency_overrides.clear()
