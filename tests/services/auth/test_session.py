"""Unit tests for authentication service layer.

Registration is covered in `test_auth_register.py` (mirrors the
`auth.py` → `auth_register.py` source split).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash, hash_token
from src.enums import UserRole
from src.models import RefreshToken, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth.registration import register_company_user
from src.services.auth.session import (
    authenticate_user,
    create_user_tokens,
    logout_user,
    refresh_user_tokens,
)
from src.services.exceptions import (
    InvalidCredentialsError,
    PendingApprovalError,
)
from tests.conftest import FAKE_LOGO
from tests.conftest import FAKE_SIG_B64 as FAKE_SIGNATURE_B64


def _active_user(email: str = "session-test@example.com") -> User:
    return User(
        email=email,
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )


FAKE_LOGO_NAME = "logo.png"


def _make_user_create(email: str = "company@example.com") -> UserCreate:
    return UserCreate(
        email=email,
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Test Company",
            company_id="123456789",
            address="רח׳ הדוגמה 1, תל אביב",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )


@pytest.mark.asyncio
async def test_authenticate_user_success(session: AsyncSession):
    """Test successful user authentication."""
    user_data = _make_user_create("login@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    result = await session.execute(
        select(User).where(User.email == "login@example.com")  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    authenticated_user = await authenticate_user(
        "login@example.com", "SecurePass1!", session
    )
    assert authenticated_user.email == "login@example.com"
    assert authenticated_user.is_active is True


@pytest.mark.asyncio
async def test_authenticate_user_invalid_email(session: AsyncSession):
    """Test authentication fails with unknown email."""
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user("nonexistent@example.com", "somepassword", session)


@pytest.mark.asyncio
async def test_authenticate_user_invalid_password(session: AsyncSession):
    """Test authentication fails with wrong password."""
    user_data = _make_user_create("wrongpass@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    result = await session.execute(
        select(User).where(User.email == "wrongpass@example.com")  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await authenticate_user("wrongpass@example.com", "wrongpassword", session)


@pytest.mark.asyncio
async def test_authenticate_user_inactive(session: AsyncSession):
    """Test authentication fails for inactive users."""
    user_data = _make_user_create("inactive@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    with pytest.raises(PendingApprovalError):
        await authenticate_user("inactive@example.com", "SecurePass1!", session)


# ── create_user_tokens ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user_tokens_returns_token_pair(session: AsyncSession):
    """create_user_tokens returns non-empty access and refresh token strings."""
    user = _active_user()
    session.add(user)
    await session.commit()
    await session.refresh(user)

    access, refresh = await create_user_tokens(user, session)

    assert isinstance(access, str) and len(access) > 0
    assert isinstance(refresh, str) and len(refresh) > 0


@pytest.mark.asyncio
async def test_create_user_tokens_persists_refresh_row(session: AsyncSession):
    """create_user_tokens writes a RefreshToken row keyed by the returned raw token."""
    user = _active_user("persist@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw_refresh = await create_user_tokens(user, session)
    await session.commit()

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw_refresh)  # pyright: ignore[reportArgumentType]
        )
    )
    db_token = result.scalar_one_or_none()
    assert db_token is not None
    assert db_token.user_id == user.id


@pytest.mark.asyncio
async def test_create_user_tokens_remember_me_stored(session: AsyncSession):
    """create_user_tokens stores the remember_me flag on the RefreshToken row."""
    user = _active_user("remember@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw_refresh = await create_user_tokens(user, session, remember_me=True)
    await session.commit()

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw_refresh)  # pyright: ignore[reportArgumentType]
        )
    )
    assert result.scalar_one().remember_me is True


# ── refresh_user_tokens ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_user_tokens_rotates_token(session: AsyncSession):
    """refresh_user_tokens deletes the consumed row and issues a fresh pair."""
    user = _active_user("rotate@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, old_raw = await create_user_tokens(user, session)
    await session.commit()

    new_access, new_raw, _ = await refresh_user_tokens(old_raw, session)
    await session.commit()

    assert isinstance(new_access, str) and new_access
    assert isinstance(new_raw, str) and new_raw != old_raw

    old_result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(old_raw)  # pyright: ignore[reportArgumentType]
        )
    )
    assert old_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_refresh_user_tokens_single_use(session: AsyncSession):
    """A consumed refresh token cannot be reused — second rotation raises
    InvalidCredentialsError."""
    user = _active_user("singleuse@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, old_raw = await create_user_tokens(user, session)
    await session.commit()

    await refresh_user_tokens(old_raw, session)
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens(old_raw, session)


@pytest.mark.asyncio
async def test_refresh_user_tokens_carries_remember_me(session: AsyncSession):
    """refresh_user_tokens propagates remember_me from the old token to the new one."""
    user = _active_user("rememberrotate@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, old_raw = await create_user_tokens(user, session, remember_me=True)
    await session.commit()

    _, new_raw, remember_me = await refresh_user_tokens(old_raw, session)
    await session.commit()

    assert remember_me is True
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(new_raw)  # pyright: ignore[reportArgumentType]
        )
    )
    assert result.scalar_one().remember_me is True


@pytest.mark.asyncio
async def test_refresh_user_tokens_invalid_token(session: AsyncSession):
    """refresh_user_tokens raises InvalidCredentialsError for an unknown token."""
    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens("not-a-real-token", session)


@pytest.mark.asyncio
@patch("src.services.auth.session._delete_refresh_token", new_callable=AsyncMock)
async def test_refresh_user_tokens_expired_token(
    mock_delete: AsyncMock,
    session: AsyncSession,
):
    """refresh_user_tokens rejects an expired token and triggers its deletion.

    _delete_refresh_token is patched for the same reason as _mock_lockout_db_writes
    in conftest: it opens its own async_session which is bound to the base DATABASE_URL
    at import time, so in -n auto parallel runs it would write to the wrong worker DB.
    We verify the correct deletion call instead of querying the row absence.
    """
    user = _active_user("expired@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    raw_token = "test-expired-raw-token"
    db_token = RefreshToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        remember_me=False,
    )
    session.add(db_token)
    await session.commit()
    await session.refresh(db_token)

    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens(raw_token, session)

    mock_delete.assert_awaited_once_with(db_token.id)


# ── logout_user ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_user_deletes_refresh_token(session: AsyncSession):
    """logout_user removes the refresh token row so the session cannot be reused."""
    user = _active_user("logout@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw = await create_user_tokens(user, session)
    await session.commit()

    await logout_user(raw, session)
    await session.commit()

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw)  # pyright: ignore[reportArgumentType]
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_logout_user_noop_for_unknown_token(session: AsyncSession):
    """logout_user does not raise when the token is not in the database."""
    await logout_user("not-a-real-token", session)


@pytest.mark.asyncio
async def test_logout_user_noop_for_none(session: AsyncSession):
    """logout_user does not raise when passed None."""
    await logout_user(None, session)
