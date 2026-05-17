"""Tests for admin company invite-token endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_generate_invite_token_returns_token(admin_client: AsyncClient):
    """Admin can generate an invite token."""
    response = await admin_client.post(
        "/api/admin/companies/invite",
        json={"email": "invite@example.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "token_hash" in data
    # Value is set by the global mock_invite_tokens fixture in conftest.py.
    assert data["token_hash"] == "test-invite-token-abc123"


@pytest.mark.asyncio
async def test_generate_invite_token_requires_admin(public_client: AsyncClient):
    """Unauthenticated clients cannot generate invites."""
    response = await public_client.post("/api/admin/companies/invite")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_invites_returns_cursor_page_envelope(admin_client: AsyncClient):
    """The invites list returns a CursorPage envelope, not a bare array."""
    response = await admin_client.get("/api/admin/companies/invites")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "next_cursor"}
    assert body["next_cursor"] is None
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_list_invites_invalid_cursor_returns_400(admin_client: AsyncClient):
    response = await admin_client.get(
        "/api/admin/companies/invites", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400
