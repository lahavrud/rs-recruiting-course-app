"""Tests for DB-backed invite token management."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.invite_tokens import (
    TOKEN_TTL_SECONDS,
    generate_invite_token,
    validate_invite_token,
)
from src.core.infrastructure.security import hash_token
from src.enums import InviteTokenStatus
from src.models import InviteToken
from src.services.exceptions import InvalidInviteTokenError


class TestGenerateInviteToken:
    @pytest.mark.asyncio
    async def test_returns_raw_token_hash_and_expiry(self):
        raw, token_hash, expires_at = await generate_invite_token()
        assert isinstance(raw, str) and len(raw) > 0
        assert token_hash == hash_token(raw)
        assert expires_at is not None

    @pytest.mark.asyncio
    async def test_expiry_is_two_hours_from_now(self):
        _, _, expires_at = await generate_invite_token()
        delta = expires_at - datetime.now(timezone.utc)
        assert abs(delta.total_seconds() - TOKEN_TTL_SECONDS) < 5

    @pytest.mark.asyncio
    async def test_each_call_generates_unique_raw_token(self):
        raw_a, _, _ = await generate_invite_token()
        raw_b, _, _ = await generate_invite_token()
        assert raw_a != raw_b


class TestValidateInviteToken:
    @pytest.mark.asyncio
    async def test_raises_when_token_missing(self, session: AsyncSession):
        with pytest.raises(InvalidInviteTokenError):
            await validate_invite_token("nonexistent-token", session)

    @pytest.mark.asyncio
    async def test_raises_when_token_expired(self, session: AsyncSession, admin_user):
        raw, token_hash, _ = await generate_invite_token()
        record = InviteToken(
            token_hash=token_hash,
            email="test@example.com",
            status=InviteTokenStatus.PENDING,
            created_by_admin_id=admin_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(record)
        await session.flush()

        with pytest.raises(InvalidInviteTokenError):
            await validate_invite_token(raw, session)

    @pytest.mark.asyncio
    async def test_raises_when_token_revoked(self, session: AsyncSession, admin_user):
        raw, token_hash, expires_at = await generate_invite_token()
        record = InviteToken(
            token_hash=token_hash,
            email="test@example.com",
            status=InviteTokenStatus.REVOKED,
            created_by_admin_id=admin_user.id,
            expires_at=expires_at,
        )
        session.add(record)
        await session.flush()

        with pytest.raises(InvalidInviteTokenError):
            await validate_invite_token(raw, session)

    @pytest.mark.asyncio
    async def test_does_not_raise_for_valid_pending_token(
        self, session: AsyncSession, admin_user
    ):
        raw, token_hash, expires_at = await generate_invite_token()
        record = InviteToken(
            token_hash=token_hash,
            email="test@example.com",
            status=InviteTokenStatus.PENDING,
            created_by_admin_id=admin_user.id,
            expires_at=expires_at,
        )
        session.add(record)
        await session.flush()

        await validate_invite_token(raw, session)  # should not raise
