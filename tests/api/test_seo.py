"""Tests for SEO endpoints: /robots.txt, /sitemap.xml, /api/og/*."""

import pytest
from httpx import AsyncClient

from src.enums import JobStatus
from src.models import Job


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
    # Authenticated areas and auth flow pages must not be indexed.
    for path in (
        "/admin",
        "/company",
        "/dashboard",
        "/activate",
        "/login",
        "/register",
    ):
        assert f"Disallow: {path}" in body


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
    # Articles index + at least one article URL.
    assert "/articles" in body
    assert "/articles/mah-ze-nihul-mabnim" in body


@pytest.mark.asyncio
async def test_sitemap_xml_includes_published_jobs(
    public_client: AsyncClient,
    published_job: Job,
):
    """sitemap.xml lists URLs for published jobs."""
    response = await public_client.get("/sitemap.xml")
    assert response.status_code == 200
    assert f"/jobs/{published_job.id}" in response.text


@pytest.mark.asyncio
async def test_og_job_published_returns_meta_html(
    public_client: AsyncClient,
    published_job: Job,
):
    """OG endpoint returns HTML with per-job <head> for a published job."""
    response = await public_client.get(f"/api/og/jobs/{published_job.id}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert published_job.title in body
    assert f"<title>{published_job.title} — RS Recruiting</title>" in body
    assert 'property="og:title"' in body
    assert 'property="og:type" content="article"' in body
    assert 'property="og:locale" content="he_IL"' in body
    assert f"/jobs/{published_job.id}" in body
    assert "application/ld+json" in body
    assert '"@type": "JobPosting"' in body
    assert '"currency": "ILS"' in body
    # Google-recommended fields for rich-result eligibility.
    assert '"validThrough"' in body
    assert '"employmentType": "FULL_TIME"' in body
    assert '"directApply": true' in body
    assert '"identifier"' in body
    # description is HTML-formatted (paragraphs + bullet list).
    assert "\\u003cp\\u003e" in body  # <p> escaped inside <script>
    assert "\\u003cul\\u003e" in body  # <ul> escaped inside <script>
    # BreadcrumbList lives in the same @graph as JobPosting.
    assert '"@type": "BreadcrumbList"' in body
    # Visible body content (for Googlebot indexing, not just <head> scraping).
    assert f"<h1>{published_job.title}</h1>" in body
    assert published_job.location in body
    assert "להגיש מועמדות" in body  # apply link anchor


@pytest.mark.asyncio
async def test_og_home_returns_landing_html(public_client: AsyncClient):
    """/api/og/home returns the landing page prerender with brand JSON-LD."""
    response = await public_client.get("/api/og/home")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "<h1>גיוס לתפקידי ניהול ותפעול מבנים ונכסים</h1>" in body
    assert 'property="og:type" content="website"' in body
    # Brand schema graph + WebSite type for canonical brand entity.
    assert '"@type": "WebSite"' in body
    assert "EmploymentAgency" in body
    # Internal nav so crawlers can follow.
    assert 'href="' in body and "/jobs" in body


@pytest.mark.asyncio
async def test_og_jobs_index_empty(public_client: AsyncClient):
    """/api/og/jobs renders an empty board cleanly."""
    response = await public_client.get("/api/og/jobs")
    assert response.status_code == 200
    body = response.text
    assert "<h1>משרות בתחום ניהול ותפעול מבנים</h1>" in body
    assert '"@type": "BreadcrumbList"' in body


@pytest.mark.asyncio
async def test_og_jobs_index_lists_published_jobs(
    public_client: AsyncClient,
    published_job: Job,
):
    """/api/og/jobs surfaces published jobs as visible links + ItemList."""
    response = await public_client.get("/api/og/jobs")
    assert response.status_code == 200
    body = response.text
    assert published_job.title in body
    assert f"/jobs/{published_job.id}" in body
    assert '"@type": "ItemList"' in body


@pytest.mark.asyncio
async def test_og_job_not_found(public_client: AsyncClient):
    """OG endpoint 404s when the job id doesn't exist."""
    response = await public_client.get("/api/og/jobs/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_og_job_unpublished_is_404(
    public_client: AsyncClient,
    pending_job: Job,
):
    """OG endpoint refuses to surface non-PUBLISHED jobs to scrapers."""
    assert pending_job.status == JobStatus.PENDING_APPROVAL
    response = await public_client.get(f"/api/og/jobs/{pending_job.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_og_job_escapes_html_in_title(
    public_client: AsyncClient,
    company_profile,
):
    """User-supplied content must be HTML-escaped to prevent injection."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as s:
        job = Job(
            company_id=company_profile.id,
            title='Position <script>alert("xss")</script>',
            short_description="Short blurb for testing.",
            description="Role with <b>tricky</b> characters & symbols.",
            requirements=[{"text": "n/a"}, {"text": "Req 2"}, {"text": "Req 3"}],
            location="Tel Aviv",
            salary_min=10000,
            salary_max=20000,
            status=JobStatus.PUBLISHED,
        )
        s.add(job)
        await s.commit()
        await s.refresh(job)

    response = await public_client.get(f"/api/og/jobs/{job.id}")
    assert response.status_code == 200
    body = response.text
    # Raw script tag must not appear; ampersand and angles must be escaped.
    assert "<script>alert" not in body
    assert "&lt;script&gt;alert" in body
    assert "&amp;" in body
