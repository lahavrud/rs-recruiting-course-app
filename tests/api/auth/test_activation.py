"""Tests for the company account activation endpoint."""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.security import get_password_hash, hash_token
from src.enums import UserRole
from src.main import app
from src.models import ActivationToken, CompanyProfile, User
from tests.conftest import TestSessionLocal


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = _override_session


async def _make_pending_company(session: AsyncSession) -> tuple[User, str]:
    """Create an inactive company user + unused activation token.

    Does NOT commit — callers keep the session open so that concurrent
    xdist workers' TRUNCATE teardowns cannot delete the rows before the
    ASGI activation request reads them.
    """
    email = f"activation-{secrets.token_hex(6)}@test.com"
    user = User(
        email=email,
        hashed_password=get_password_hash("Password1!"),
        role=UserRole.COMPANY,
        is_active=False,
    )
    session.add(user)
    await session.flush()

    profile = CompanyProfile(
        user_id=user.id,
        name="Test Co",
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_email=email,
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(profile)
    await session.flush()

    raw_token = secrets.token_urlsafe(32)
    activation = ActivationToken(
        token_hash=hash_token(raw_token),
        company_user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        used=False,
    )
    session.add(activation)
    await session.flush()  # flush but do NOT commit yet
    return user, raw_token


@pytest.mark.asyncio
async def test_activate_valid_token(test_db):
    async with TestSessionLocal() as session:
        user, token = await _make_pending_company(session)

        # Inject the same open session into the app so the ASGI request sees
        # uncommitted rows — preventing concurrent TRUNCATE from wiping them.
        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        with patch("src.services.admin.companies.enqueue_email_task"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/auth/activate?token={token}")

    app.dependency_overrides[get_session] = _override_session  # restore

    assert resp.status_code == 200
    assert resp.json() == {"message": "החשבון הופעל בהצלחה"}


@pytest.mark.asyncio
async def test_activate_invalid_token_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/auth/activate?token=nonexistent-token")

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_activate_used_token_returns_400(test_db):
    async with TestSessionLocal() as session:
        user, token = await _make_pending_company(session)

        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        # Mark the token as already used while session is still open
        from sqlalchemy import select

        result = await session.execute(
            select(ActivationToken).where(
                ActivationToken.token_hash == hash_token(token)  # type: ignore[arg-type]
            )
        )
        act = result.scalar_one()
        act.used = True
        await session.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"/auth/activate?token={token}")

    app.dependency_overrides[get_session] = _override_session

    assert resp.status_code == 400
