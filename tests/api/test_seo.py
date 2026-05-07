"""Tests for SEO endpoints: /robots.txt and /sitemap.xml."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_robots_txt(public_client: AsyncClient):
    """robots.txt is accessible to all and contains correct directives."""
    response = await public_client.get("/robots.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "User-agent: *" in body
    assert "Allow: /" in body
    assert "Sitemap:" in body


@pytest.mark.asyncio
async def test_sitemap_xml_empty(public_client: AsyncClient):
    """sitemap.xml returns valid XML even when no jobs are published."""
    response = await public_client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert '<?xml version="1.0"' in body
    assert "<urlset" in body
    # Static pages always present
    assert "/jobs" in body


@pytest.mark.asyncio
async def test_sitemap_xml_includes_published_jobs(
    public_client: AsyncClient,
    admin_client: AsyncClient,
):
    """sitemap.xml lists URLs for published jobs."""
    # Create and publish a job via admin
    create_resp = await admin_client.post(
        "/api/admin/jobs",
        json={
            "company_id": 1,
            "title": "Sitemap Test Job",
            "description": "desc",
            "requirements": "req",
            "location": "תל אביב",
            "status": "PUBLISHED",
        },
    )
    if create_resp.status_code != 201:
        pytest.skip("No active company available for job creation")

    job_id = create_resp.json()["id"]
    response = await public_client.get("/sitemap.xml")
    assert response.status_code == 200
    assert f"/jobs/{job_id}" in response.text
