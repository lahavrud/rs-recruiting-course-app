"""Integration tests for the admin audit-log endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AuditLog


@pytest.mark.asyncio
async def test_admin_can_list_empty(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/audit-log")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_admin_can_filter(admin_client: AsyncClient, session: AsyncSession):
    session.add(
        AuditLog(
            actor_user_id=1,
            action="company.approve",
            target_type="CompanyProfile",
            target_id=10,
            ip_address="203.0.113.1",
        )
    )
    session.add(
        AuditLog(
            actor_user_id=2,
            action="candidate.delete",
            target_type="CandidateProfile",
            target_id=20,
        )
    )
    await session.commit()

    response = await admin_client.get(
        "/api/admin/audit-log", params={"target_type": "CandidateProfile"}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["action"] == "candidate.delete"
    assert items[0]["target_id"] == 20


@pytest.mark.asyncio
async def test_audit_log_requires_admin(public_client: AsyncClient):
    response = await public_client.get("/api/admin/audit-log")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audit_log_invalid_cursor_returns_400(admin_client: AsyncClient):
    response = await admin_client.get(
        "/api/admin/audit-log", params={"cursor": "not-real"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_audit_log_paginates_through_all_rows(
    admin_client: AsyncClient, session: AsyncSession
):
    """A cursor walk over the audit log returns every row exactly once."""
    total = 7
    for i in range(total):
        session.add(
            AuditLog(
                actor_user_id=1,
                action="company.approve",
                target_type="CompanyProfile",
                target_id=i,
            )
        )
    await session.commit()

    seen: set[int] = set()
    cursor: str | None = None
    pages = 0
    while True:
        params: dict[str, object] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = await admin_client.get("/api/admin/audit-log", params=params)
        assert response.status_code == 200
        body = response.json()
        seen.update(item["target_id"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == set(range(total))
    # 7 rows / limit 3 => 3 pages (last is partial).
    assert pages == 3


@pytest.mark.asyncio
async def test_candidate_delete_writes_audit_row(
    admin_client: AsyncClient, candidate_profile, session: AsyncSession
):
    """End-to-end: deleting a candidate produces a candidate.delete audit row."""
    candidate_id = candidate_profile.id
    response = await admin_client.delete(f"/api/admin/candidates/{candidate_id}")
    assert response.status_code == 204

    audit_response = await admin_client.get(
        "/api/admin/audit-log",
        params={"target_type": "CandidateProfile"},
    )
    items = audit_response.json()["items"]
    assert len(items) == 1
    assert items[0]["action"] == "candidate.delete"
    assert items[0]["target_id"] == candidate_id
    assert items[0]["actor_user_id"] is not None
