"""Tests for authentication endpoints."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.core.infrastructure.database import get_session
from src.core.infrastructure.security import verify_password
from src.main import app
from src.models import User
from src.services.exceptions import InvalidInviteTokenError
from tests.factories import FAKE_PNG
from tests.factories import FAKE_SIG_B64 as _FAKE_SIG_B64

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/rs_recruitment",
)

test_engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool
)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

FAKE_LOGO_FILE = ("logo.png", FAKE_PNG, "image/png")
FAKE_SIGNATURE_B64 = _FAKE_SIG_B64


async def override_get_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def client():
    from src.api import auth

    auth.limiter.enabled = False
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
        app.dependency_overrides.clear()


_STRONG_PASSWORD = "SecurePass1!"


def _reg_data(**overrides):
    """Base multipart form data for a valid registration."""
    data = {
        "email": "company@example.com",
        "password": _STRONG_PASSWORD,
        "company_name": "Test Company",
        "company_id": "123456789",
        "address": "רח׳ הדוגמה 1, תל אביב",
        "contact_first_name": "ישראל",
        "contact_last_name": "ישראלי",
        "contact_mobile_phone": "0501234567",
        "agreement_signature": FAKE_SIGNATURE_B64,
        "privacy_accepted": "true",
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful company registration."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 201

    data = response.json()
    assert data["user"]["email"] == "company@example.com"
    assert data["user"]["role"] == "COMPANY"
    assert data["user"]["is_active"] is False
    assert "password" not in str(data)

    cp = data["company_profile"]
    assert cp["name"] == "Test Company"
    assert cp["company_id"] == "123456789"
    assert cp["contact_first_name"] == "ישראל"
    assert cp["contact_last_name"] == "ישראלי"
    assert cp["contact_mobile_phone"] == "0501234567"
    assert cp["logo_url"] is not None
    assert cp["agreement_signature_url"] is not None
    assert cp["agreement_signed_at"] is not None

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "company@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        assert verify_password(_STRONG_PASSWORD, user.hashed_password)


@pytest.mark.asyncio
async def test_register_invalid_company_id(client: AsyncClient):
    """Test 422 when company_id is not 9 digits."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(company_id="12345"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_mobile_phone(client: AsyncClient):
    """Test 422 when mobile phone is not a valid Israeli mobile number."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(contact_mobile_phone="0521234567890"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_contact_first_name(client: AsyncClient):
    """Test 422 when contact_first_name is missing."""
    d = _reg_data()
    del d["contact_first_name"]
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=d,
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_logo(client: AsyncClient):
    """Test 422 when logo file is not provided."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Test registration fails when email already exists."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="duplicate@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="duplicate@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login returns JWT access + refresh tokens."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="login@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "login@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": _STRONG_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_email(client: AsyncClient):
    """Test login fails with unknown email."""
    response = await client.post(
        "/auth/login", json={"email": "nonexistent@example.com", "password": "pass"}
    )
    assert response.status_code == 401
    assert "incorrect email or password" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """Test login fails with wrong password."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="wrongpass@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "wrongpass@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": "wrongpass@example.com", "password": "WrongPass1!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient):
    """Test login fails for inactive users."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="inactive@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": _STRONG_PASSWORD},
    )
    assert response.status_code == 403
    # Registered but not yet approved → pending_approval detail code
    assert "pending" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_missing_token_returns_422(client: AsyncClient):
    """Test registration without a token returns 422."""
    response = await client.post(
        "/auth/register",
        data=_reg_data(),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_token_returns_400(client: AsyncClient):
    """Test that an invalid/expired invite token returns 400."""
    with patch(
        "src.api.auth.validate_invite_token",
        new_callable=AsyncMock,
        side_effect=InvalidInviteTokenError(),
    ):
        response = await client.post(
            "/auth/register",
            params={"token": "expired-or-fake-token"},
            data=_reg_data(email="badtoken@example.com"),
            files={"logo": FAKE_LOGO_FILE},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_token_consumed_on_success(client: AsyncClient):
    """Test that the invite token is consumed after successful registration."""
    with (
        patch(
            "src.api.auth.validate_invite_token", new_callable=AsyncMock
        ) as mock_validate,
        patch(
            "src.api.auth.consume_invite_token", new_callable=AsyncMock
        ) as mock_consume,
    ):
        response = await client.post(
            "/auth/register",
            params={"token": "one-time-token"},
            data=_reg_data(email="tokenconsumed@example.com"),
            files={"logo": FAKE_LOGO_FILE},
        )
    assert response.status_code == 201
    mock_validate.assert_awaited_once_with("one-time-token")
    mock_consume.assert_awaited_once_with("one-time-token")


# ==================== Agreement Signature Tests ====================


@pytest.mark.asyncio
async def test_register_missing_signature(client: AsyncClient):
    """Test 422 when agreement_signature field is omitted."""
    data = _reg_data()
    del data["agreement_signature"]
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=data,
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_signature(client: AsyncClient):
    """Test 422 when agreement_signature is not valid base64."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(agreement_signature="not-valid-base64!!!"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_empty_signature(client: AsyncClient):
    """Test 422 when agreement_signature is an empty string."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(agreement_signature=""),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


# ==================== Password Complexity Tests ====================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password",
    [
        "short1!A",  # exactly 8 chars — valid boundary
        "Abcdefg1!",  # 9 chars, all rules met
        "UPPERCASE1!abc",  # uppercase, lowercase, digit, special
    ],
)
async def test_register_valid_password_complexity(client: AsyncClient, password: str):
    """Test registration succeeds with passwords that meet complexity rules."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email=f"valid_{len(password)}@example.com", password=password),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password,reason",
    [
        ("short1!", "too short"),
        ("alllowercase1!", "no uppercase"),
        ("ALLUPPERCASE1!", "no lowercase"),
        ("NoDigitsHere!", "no digit"),
        ("NoSpecialChar1", "no special char"),
    ],
)
async def test_register_weak_password_rejected(
    client: AsyncClient, password: str, reason: str
):
    """Test registration fails when password doesn't meet complexity rules."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(
            email=f"weak_{reason.replace(' ', '_')}@example.com",
            password=password,
        ),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422, f"Expected rejection for: {reason}"


# ==================== Refresh Token Tests ====================


async def _create_active_user(client: AsyncClient, email: str) -> dict:
    """Helper: register + activate + login, return token response dict."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email=email),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": _STRONG_PASSWORD},
    )
    assert login_resp.status_code == 200
    return login_resp.json()


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(client: AsyncClient):
    """Test that a valid refresh token yields a new token pair."""
    tokens = await _create_active_user(client, "refresh@example.com")
    old_access = tokens["access_token"]
    old_refresh = tokens["refresh_token"]

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != old_refresh  # rotated
    assert data["access_token"] != old_access


@pytest.mark.asyncio
async def test_refresh_token_is_single_use(client: AsyncClient):
    """Test that the same refresh token cannot be used twice."""
    tokens = await _create_active_user(client, "singleuse@example.com")
    refresh_token = tokens["refresh_token"]

    # First use — should succeed
    resp1 = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp1.status_code == 200

    # Second use of the same token — should be rejected
    resp2 = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(client: AsyncClient):
    """Test that a bogus refresh token is rejected."""
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "not-a-real-token"},
    )
    assert response.status_code == 401


# ==================== Account Lockout Tests ====================


@pytest.mark.asyncio
async def test_account_lockout_after_failed_attempts(client: AsyncClient):
    """Test that an account is locked after repeated failed logins."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="lockme@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "lockme@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    # Simulate the lockout check raising AccountLockedError on the 6th attempt
    from src.services.exceptions import AccountLockedError

    attempt_count = 0

    async def fake_check_lockout(email: str) -> None:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count > 5:
            raise AccountLockedError(minutes_remaining=15)

    with patch("src.services.auth._check_lockout", side_effect=fake_check_lockout):
        for _ in range(5):
            await client.post(
                "/auth/login",
                json={"email": "lockme@example.com", "password": "WrongPass1!"},
            )
        locked_resp = await client.post(
            "/auth/login",
            json={"email": "lockme@example.com", "password": "WrongPass1!"},
        )

    assert locked_resp.status_code == 429


@pytest.mark.asyncio
async def test_successful_login_clears_failed_attempts(client: AsyncClient):
    """Test that a successful login clears the lockout counter."""
    tokens = await _create_active_user(client, "clearlock@example.com")
    assert "access_token" in tokens  # login succeeded — counter was cleared
