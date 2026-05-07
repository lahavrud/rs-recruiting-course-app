"""Integration tests for job write API endpoints (POST, PUT, DELETE)."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from src.enums import JobStatus
from src.models import CompanyProfile, Job
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
@patch("src.services.jobs.enqueue_email_task")
@patch("src.services.jobs.get_all_admin_emails")
async def test_create_job_success(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
    company_profile: CompanyProfile,
):
    """Test creating a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = ["admin@test.com"]

    job_data = {
        "title": "Senior Python Developer",
        "description": "We are looking for a senior Python developer...",
        "requirements": "5+ years experience with Python, FastAPI, PostgreSQL",
        "location": "Tel Aviv, Israel",
        "salary_min": 20000,
        "salary_max": 30000,
    }

    response = await company_client.post("/api/jobs/", json=job_data)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "Senior Python Developer"
    assert data["status"] == "PENDING_APPROVAL"
    assert data["company_id"] == company_profile.id
    assert "id" in data
    assert "created_at" in data
    assert data["salary_min"] == 20000
    assert data["salary_max"] == 30000

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.jobs.enqueue_email_task")
@patch("src.services.jobs.get_all_admin_emails")
async def test_update_job_success(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
    job: Job,
):
    """Test updating a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = ["admin@test.com"]

    update_data = {
        "title": "Updated Title",
        "location": "Updated Location",
    }

    response = await company_client.put(f"/api/jobs/{job.id}", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["location"] == "Updated Location"
    assert data["description"] == job.description  # Unchanged

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_update_job_not_found(company_client: AsyncClient):
    """Test updating a non-existent job."""
    update_data = {"title": "Updated Title"}

    response = await company_client.put("/api/jobs/999", json=update_data)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_job_cannot_change_status(company_client: AsyncClient, job: Job):
    """Test that companies cannot change job status."""
    update_data = {"status": "PUBLISHED"}

    response = await company_client.put(f"/api/jobs/{job.id}", json=update_data)
    assert response.status_code == 400
    assert "cannot change job status" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_job_closed_status(company_client: AsyncClient, job: Job):
    """Test updating a job with CLOSED status."""
    # Set job status to CLOSED
    async with TestSessionLocal() as session:
        db_job = await session.get(Job, job.id)
        if db_job is None:
            raise AssertionError(f"Job with id {job.id} not found in database.")
        db_job.status = JobStatus.CLOSED
        await session.commit()

    update_data = {"title": "Updated Title"}

    response = await company_client.put(f"/api/jobs/{job.id}", json=update_data)
    assert response.status_code == 400
    assert "cannot be updated" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_job_success(company_client: AsyncClient, job: Job):
    """Test deleting a job successfully."""
    job_id = job.id
    response = await company_client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 204

    # Verify job was deleted
    async with TestSessionLocal() as session:
        db_job = await session.get(Job, job_id)
        assert db_job is None


@pytest.mark.asyncio
async def test_delete_job_not_found(company_client: AsyncClient):
    """Test deleting a non-existent job."""
    response = await company_client.delete("/api/jobs/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_job_published_status(company_client: AsyncClient, job: Job):
    """Test deleting a job with PUBLISHED status."""
    # Set job status to PUBLISHED
    async with TestSessionLocal() as session:
        db_job = await session.get(Job, job.id)
        if db_job is None:
            raise AssertionError(f"Job with id {job.id} not found in database.")
        db_job.status = JobStatus.PUBLISHED
        await session.commit()

    response = await company_client.delete(f"/api/jobs/{job.id}")
    assert response.status_code == 400
    assert "cannot be deleted" in response.json()["detail"].lower()
    assert "PENDING_APPROVAL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_job_write_endpoints_require_auth(test_db):
    """Test that job write endpoints require authentication."""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/jobs/", json={})
        assert response.status_code == 401  # Unauthorized (no auth token)

        response = await client.put("/api/jobs/1", json={})
        assert response.status_code == 401

        response = await client.delete("/api/jobs/1")
        assert response.status_code == 401


@pytest.mark.asyncio
@patch("src.services.jobs.enqueue_email_task")
@patch("src.services.jobs.get_all_admin_emails")
async def test_create_job_with_salary(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
):
    """Salary is stored and returned when provided at creation."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = []

    response = await company_client.post(
        "/api/jobs/",
        json={
            "title": "Facility Manager",
            "description": "Manage facilities.",
            "requirements": "3+ years experience.",
            "location": "Tel Aviv",
            "salary_min": 15000,
            "salary_max": 20000,
        },
    )
    assert response.status_code == 201
    assert response.json()["salary_min"] == 15000
    assert response.json()["salary_max"] == 20000


@pytest.mark.asyncio
@patch("src.services.jobs.enqueue_email_task")
@patch("src.services.jobs.get_all_admin_emails")
async def test_update_job_salary(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
    job: Job,
):
    """Salary range can be updated."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = []

    response = await company_client.put(
        f"/api/jobs/{job.id}", json={"salary_min": 12000, "salary_max": 15000}
    )
    assert response.status_code == 200
    assert response.json()["salary_min"] == 12000
    assert response.json()["salary_max"] == 15000
