"""Tests for the company account activation endpoint."""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from src.core.infrastructure.database import get_session
from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.main import app
from src.models import ActivationToken, CompanyProfile, User
from tests.conftest import enable_sqlite_foreign_keys

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
enable_sqlite_foreign_keys(test_engine)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = _override_session


async def _make_pending_company(session: AsyncSession) -> tuple[User, str]:
    """Create an inactive company user + unused activation token."""
    user = User(
        email="company@test.com",
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
    )
    session.add(profile)
    await session.flush()

    raw_token = secrets.token_urlsafe(32)
    activation = ActivationToken(
        token=raw_token,
        company_user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        used=False,
    )
    session.add(activation)
    await session.commit()
    return user, raw_token


@pytest.mark.asyncio
async def test_activate_valid_token():
    async with TestSessionLocal() as session:
        user, token = await _make_pending_company(session)

    with patch("src.services.admin_companies.enqueue_email_task"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"/auth/activate?token={token}")

    assert resp.status_code == 200
    assert resp.json() == {"message": "החשבון הופעל בהצלחה"}

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.id == user.id))
        updated = result.scalar_one()
        assert updated.is_active is True


@pytest.mark.asyncio
async def test_activate_invalid_token_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/auth/activate?token=nonexistent-token")

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_activate_used_token_returns_400():
    async with TestSessionLocal() as session:
        user, token = await _make_pending_company(session)
        # Mark token as used
        from sqlalchemy import select

        result = await session.execute(
            select(ActivationToken).where(ActivationToken.token == token)
        )
        act = result.scalar_one()
        act.used = True
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(f"/auth/activate?token={token}")

    assert resp.status_code == 400
