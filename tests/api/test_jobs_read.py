"""Integration tests for job read API endpoints."""

import pytest
from httpx import AsyncClient

from src.models import CompanyProfile, Job
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_get_company_jobs_empty(company_client: AsyncClient):
    """Test getting jobs when none exist."""
    response = await company_client.get("/api/jobs/")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_company_jobs(
    company_client: AsyncClient, company_profile: CompanyProfile
):
    """Test getting all jobs for a company."""
    # Create jobs
    async with TestSessionLocal() as session:
        assert company_profile.id is not None
        job1 = Job(
            company_id=company_profile.id,
            title="Job 1",
            description="Description 1",
            requirements="Requirements 1",
            location="Location 1",
            salary_min=15000,
            salary_max=25000,
        )
        job2 = Job(
            company_id=company_profile.id,
            title="Job 2",
            description="Description 2",
            requirements="Requirements 2",
            location="Location 2",
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job1)
        session.add(job2)
        await session.commit()

    response = await company_client.get("/api/jobs/")
    assert response.status_code == 200

    data = response.json()["items"]
    assert len(data) == 2
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)


@pytest.mark.asyncio
async def test_get_job_success(company_client: AsyncClient, pending_job: Job):
    """Test getting a specific job."""
    response = await company_client.get(f"/api/jobs/{pending_job.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == pending_job.id
    assert data["title"] == pending_job.title
    assert data["status"] == "PENDING_APPROVAL"


@pytest.mark.asyncio
async def test_get_job_not_found(company_client: AsyncClient):
    """Test getting a non-existent job."""
    response = await company_client.get("/api/jobs/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_job_read_endpoints_require_auth(unauthenticated_client: AsyncClient):
    """Job read endpoints reject requests without an auth token."""
    response = await unauthenticated_client.get("/api/jobs/")
    assert response.status_code == 401

    response = await unauthenticated_client.get("/api/jobs/1")
    assert response.status_code == 401
