"""Tests for /api/companies endpoints (self-service)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from rs_shared.models import CompanyProfile, Job


@pytest.mark.asyncio
async def test_export_my_company_data_returns_full_payload(
    company_client: AsyncClient,
    company_profile: CompanyProfile,
    pending_job: Job,
):
    """Happy path: returns user, profile and jobs."""
    fake_storage = AsyncMock()
    fake_storage.get_file_url.return_value = "https://example.com/presigned"

    with patch(
        "rs_api.api.company.profile.get_storage_provider", return_value=fake_storage
    ):
        response = await company_client.get("/api/companies/me/export")

    assert response.status_code == 200
    data = response.json()

    assert "exported_at" in data
    assert data["user"]["id"] == company_profile.user_id
    assert data["company_profile"]["id"] == company_profile.id
    assert data["company_profile"]["name"] == company_profile.name
    assert isinstance(data["jobs"], list)
    job_ids = [j["id"] for j in data["jobs"]]
    assert pending_job.id in job_ids


@pytest.mark.asyncio
async def test_export_my_company_data_requires_company_auth(
    public_client: AsyncClient,
):
    """Unauthenticated callers receive 401."""
    response = await public_client.get("/api/companies/me/export")
    assert response.status_code == 401
