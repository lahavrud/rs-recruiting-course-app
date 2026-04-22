"""Integration tests for public API endpoints (no authentication required)."""

import pytest
from httpx import AsyncClient

from src.enums import JobStatus
from src.models import CompanyProfile, Job
from src.schemas import JobPublicRead
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_get_public_jobs_empty(public_client: AsyncClient):
    """Test getting public jobs when none exist."""
    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_public_jobs_only_published(
    public_client: AsyncClient,
    company_profile: CompanyProfile,
    published_job: Job,
    pending_job: Job,
    closed_job: Job,
):
    """Test that public endpoint only returns published jobs."""
    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200

    data = response.json()
    # Should only return published job, not pending or closed
    assert len(data) == 1
    assert data[0]["id"] == published_job.id
    assert data[0]["title"] == "Senior Python Developer"
    assert "status" not in data[0]


@pytest.mark.asyncio
async def test_get_public_jobs_multiple_published(
    public_client: AsyncClient, company_profile: CompanyProfile, published_job: Job
):
    """Test getting multiple published jobs."""
    # Create another published job
    async with TestSessionLocal() as session:
        job2 = Job(
            company_id=company_profile.id if company_profile.id is not None else 0,
            title="Frontend Developer",
            description="We are looking for a frontend developer...",
            requirements="3+ years experience with React",
            location="Tel Aviv, Israel",
            status=JobStatus.PUBLISHED,
        )
        session.add(job2)
        await session.commit()

    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    # Should be ordered by creation date (newest first)
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)
    assert all("status" not in job for job in data)


@pytest.mark.asyncio
async def test_get_public_job_success(public_client: AsyncClient, published_job: Job):
    """Test getting a specific published job."""
    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == published_job.id
    assert data["title"] == published_job.title
    assert data["description"] == published_job.description
    assert data["requirements"] == published_job.requirements
    assert data["location"] == published_job.location
    assert "status" not in data


@pytest.mark.asyncio
async def test_get_public_job_not_found(public_client: AsyncClient):
    """Test getting a non-existent job returns 404."""
    response = await public_client.get("/api/public/jobs/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_public_job_pending_not_visible(
    public_client: AsyncClient, pending_job: Job
):
    """Test that pending jobs are not visible via public endpoint."""
    response = await public_client.get(f"/api/public/jobs/{pending_job.id}")
    assert response.status_code == 404
    detail = response.json()["detail"].lower()
    assert "not published" in detail or "not found" in detail


@pytest.mark.asyncio
async def test_get_public_job_closed_not_visible(
    public_client: AsyncClient, closed_job: Job
):
    """Test that closed jobs are not visible via public endpoint."""
    response = await public_client.get(f"/api/public/jobs/{closed_job.id}")
    assert response.status_code == 404
    detail = response.json()["detail"].lower()
    assert "not published" in detail or "not found" in detail


@pytest.mark.asyncio
async def test_get_public_job_omits_internal_fields(
    public_client: AsyncClient, published_job: Job
):
    """Test that internal fields are omitted from public job responses."""
    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200

    # Extract job data
    data = response.json()

    # 1. Dynamically derive public fields from the schema
    public_fields = set(JobPublicRead.model_fields.keys())

    # 2. Check the raw response for internal fields
    unexpected_keys = set(data.keys()) - public_fields

    assert not unexpected_keys, f"Unexpected fields in response: {unexpected_keys}"

    # 3. Ensure that all public fields are included
    assert public_fields.issubset(data.keys()), "Missing expected public fields."


@pytest.mark.asyncio
async def test_public_endpoints_no_auth_required(
    public_client: AsyncClient, published_job: Job
):
    """Test that public endpoints work without authentication."""
    # These endpoints should work without any auth token
    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200

    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_public_job_payload_integrity(
    public_client: AsyncClient, published_job: Job
):
    """Verify that the public API response matches the JobPublicRead schema exactly."""
    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200

    data = response.json()

    # 1. Validate the structure matches the schema
    # This ensures required fields (title, etc.) are present and valid
    job_public = JobPublicRead.model_validate(data)

    # 2. Check the raw JSON keys to ensure no internal data leaked
    # hasattr(job_public, ...) only checks the Python class, not the actual API output
    assert "company_id" not in data
    assert "updated_at" not in data

    # 3. Verify specific values
    assert job_public.id == published_job.id
    assert job_public.title == published_job.title

    # 4. Assert that only the allowed keys exist in the response
    expected_keys = {
        "id",
        "title",
        "description",
        "requirements",
        "location",
        "created_at",
    }
    assert set(data.keys()) == expected_keys
