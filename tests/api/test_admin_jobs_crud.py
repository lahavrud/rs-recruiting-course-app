"""Integration tests for the admin jobs CRUD endpoints."""

import pytest
from httpx import AsyncClient

from src.enums import JobStatus
from src.models import CompanyProfile, Job


def _payload(company_id: int, **overrides) -> dict:
    base = {
        "company_id": company_id,
        "title": "QA Engineer",
        "description": "ביצוע בדיקות אוטומטיות ומאניאוליות",
        "requirements": "ניסיון של 2 שנים לפחות",
        "location": "רמת גן",
        "salary_min": 14000,
        "salary_max": 20000,
    }
    base.update(overrides)
    return base


# ── POST /api/admin/jobs ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_job_defaults_to_published(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    response = await admin_client.post(
        "/api/admin/jobs", json=_payload(company_profile.id)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == company_profile.id
    assert data["status"] == JobStatus.PUBLISHED.value
    assert data["title"] == "QA Engineer"


@pytest.mark.asyncio
async def test_create_job_with_explicit_status(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    response = await admin_client.post(
        "/api/admin/jobs",
        json=_payload(company_profile.id, status=JobStatus.PENDING_APPROVAL.value),
    )
    assert response.status_code == 201
    assert response.json()["status"] == JobStatus.PENDING_APPROVAL.value


@pytest.mark.asyncio
async def test_create_job_unknown_company_returns_404(admin_client: AsyncClient):
    response = await admin_client.post(
        "/api/admin/jobs", json=_payload(company_id=99999)
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_job_requires_admin(public_client: AsyncClient):
    response = await public_client.post("/api/admin/jobs", json=_payload(1))
    assert response.status_code == 401


# ── GET /api/admin/jobs/{id} ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_job_returns_any_status(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.get(f"/api/admin/jobs/{pending_job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pending_job.id
    assert data["status"] == JobStatus.PENDING_APPROVAL.value


@pytest.mark.asyncio
async def test_get_job_not_found(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/jobs/99999")
    assert response.status_code == 404


# ── PUT /api/admin/jobs/{id} ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_job_partial(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.put(
        f"/api/admin/jobs/{pending_job.id}",
        json={"title": "Updated Title", "status": JobStatus.PUBLISHED.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == JobStatus.PUBLISHED.value
    # Untouched fields preserved
    assert data["description"] == pending_job.description


@pytest.mark.asyncio
async def test_update_job_not_found(admin_client: AsyncClient):
    response = await admin_client.put("/api/admin/jobs/99999", json={"title": "x"})
    assert response.status_code == 404


# ── DELETE /api/admin/jobs/{id} ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_job_succeeds(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.delete(f"/api/admin/jobs/{pending_job.id}")
    assert response.status_code == 204

    # Subsequent GET returns 404
    follow_up = await admin_client.get(f"/api/admin/jobs/{pending_job.id}")
    assert follow_up.status_code == 404


@pytest.mark.asyncio
async def test_delete_job_not_found(admin_client: AsyncClient):
    response = await admin_client.delete("/api/admin/jobs/99999")
    assert response.status_code == 404


# ── GET /api/admin/jobs (list-all-statuses, paginated) ───────────────────────


@pytest.mark.asyncio
async def test_list_jobs_envelope(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.get("/api/admin/jobs")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "next_cursor"}
    assert any(item["id"] == pending_job.id for item in body["items"])


@pytest.mark.asyncio
async def test_list_jobs_filters_by_status(
    admin_client: AsyncClient, pending_job: Job, published_job: Job
):
    response = await admin_client.get(
        "/api/admin/jobs", params={"status": JobStatus.PUBLISHED.value}
    )
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert published_job.id in ids
    assert pending_job.id not in ids


@pytest.mark.asyncio
async def test_list_jobs_invalid_cursor_returns_400(admin_client: AsyncClient):
    response = await admin_client.get(
        "/api/admin/jobs", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_jobs_paginates_through_all(
    admin_client: AsyncClient,
    company_profile: CompanyProfile,
):
    """Cursor walk over /api/admin/jobs visits every job exactly once."""
    total = 7
    for i in range(total):
        response = await admin_client.post(
            "/api/admin/jobs",
            json=_payload(company_profile.id, title=f"Role {i:02d}"),
        )
        assert response.status_code == 201

    seen: set[int] = set()
    cursor: str | None = None
    pages = 0
    while True:
        params: dict[str, object] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = await admin_client.get("/api/admin/jobs", params=params)
        assert response.status_code == 200
        body = response.json()
        seen.update(item["id"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == total
    assert pages == 3


@pytest.mark.asyncio
async def test_list_jobs_requires_admin(public_client: AsyncClient):
    response = await public_client.get("/api/admin/jobs")
    assert response.status_code == 401
