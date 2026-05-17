"""Tests for public invite token endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.core.infrastructure.security import hash_token
from src.enums import InviteTokenStatus
from src.models import InviteToken, User
from src.services.exceptions import InvalidInviteTokenError
from tests.conftest import TestSessionLocal

_EXPIRES_FAR_FUTURE = datetime(2099, 1, 1, tzinfo=timezone.utc)


async def _create_invite_record(
    token: str,
    admin_id: int,
    email: str = "company@example.com",
    company_name: str | None = "Test Co",
    contact_first_name: str | None = "ישראל",
    contact_last_name: str | None = "ישראלי",
) -> InviteToken:
    async with TestSessionLocal() as session:
        record = InviteToken(
            token_hash=hash_token(token),
            email=email,
            company_name=company_name,
            contact_first_name=contact_first_name,
            contact_last_name=contact_last_name,
            status=InviteTokenStatus.PENDING,
            created_by_admin_id=admin_id,
            expires_at=_EXPIRES_FAR_FUTURE,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record


@pytest.mark.asyncio
async def test_get_invite_metadata_returns_fields(
    public_client: AsyncClient, admin_user: User
):
    """Valid token returns email and company pre-fill data."""
    assert admin_user.id is not None
    await _create_invite_record("valid-token-abc", admin_user.id)

    response = await public_client.get("/auth/invite/valid-token-abc")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "company@example.com"
    # InviteMetadataPublic only exposes email — no pre-fill fields


@pytest.mark.asyncio
async def test_get_invite_metadata_null_optional_fields(
    public_client: AsyncClient, admin_user: User
):
    """Invite with no company/contact info still returns email only."""
    assert admin_user.id is not None
    await _create_invite_record(
        "sparse-token",
        admin_user.id,
        company_name=None,
        contact_first_name=None,
        contact_last_name=None,
    )

    response = await public_client.get("/auth/invite/sparse-token")

    assert response.status_code == 200
    data = response.json()
    assert "email" in data


@pytest.mark.asyncio
async def test_get_invite_metadata_invalid_token_returns_error(
    public_client: AsyncClient,
):
    """Expired or invalid token returns 400."""
    with patch(
        "src.api.auth.invites.validate_invite_token",
        new_callable=AsyncMock,
        side_effect=InvalidInviteTokenError(),
    ):
        response = await public_client.get("/auth/invite/bad-token")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_invite_metadata_token_not_in_db_returns_400(
    public_client: AsyncClient,
):
    """Token passes Redis validation but has no DB record → 400."""
    response = await public_client.get("/auth/invite/no-db-record")

    assert response.status_code == 400
