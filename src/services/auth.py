"""Authentication service layer for business logic.

Company registration lives in `auth_register.py` to keep this file
under the service-layer line cap.
"""

import logging
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import (
    blacklist_access_token,
    create_access_token,
    create_refresh_token,
    hash_token,
    verify_password,
)
from src.enums import InviteTokenStatus
from src.models import ActivationToken, InviteToken, RefreshToken, User
from src.services.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    PendingActivationError,
    PendingApprovalError,
)

logger = logging.getLogger(__name__)

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60  # 15 minutes
_ATTEMPTS_PREFIX = "login:attempts:"
_LOCKOUT_PREFIX = "login:locked:"


def _attempts_key(email: str) -> str:
    return f"{_ATTEMPTS_PREFIX}{email}"


def _lockout_key(email: str) -> str:
    return f"{_LOCKOUT_PREFIX}{email}"


async def _check_lockout(email: str) -> None:
    from src.core.tasks import get_redis_pool

    try:
        redis = await get_redis_pool()
        ttl = await redis.ttl(_lockout_key(email))
        if ttl > 0:
            raise AccountLockedError(minutes_remaining=math.ceil(ttl / 60))
    except AccountLockedError:
        raise
    except Exception:
        logger.error("redis_unavailable", extra={"surface": "lockout_check"})


async def _record_failed_attempt(email: str) -> None:
    from src.core.tasks import get_redis_pool

    try:
        redis = await get_redis_pool()
        key = _attempts_key(email)
        count = await redis.incr(key)
        await redis.expire(key, _LOCKOUT_SECONDS)
        if count >= _MAX_FAILED_ATTEMPTS:
            await redis.set(_lockout_key(email), "1", ex=_LOCKOUT_SECONDS)
            await redis.delete(key)
    except Exception:
        logger.error("redis_unavailable", extra={"surface": "record_failed_attempt"})


async def _clear_failed_attempts(email: str) -> None:
    from src.core.tasks import get_redis_pool

    try:
        redis = await get_redis_pool()
        await redis.delete(_attempts_key(email))
        await redis.delete(_lockout_key(email))
    except Exception:
        logger.error("redis_unavailable", extra={"surface": "clear_failed_attempts"})


async def authenticate_user(email: str, password: str, session: AsyncSession) -> User:
    """Authenticate a user by email and password.

    Checks for account lockout before attempting credential validation.
    Tracks failed attempts and locks the account after too many failures.
    """
    result = await session.execute(
        select(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if not user:
        raise InvalidCredentialsError("Incorrect email or password")

    await _check_lockout(email)

    if not verify_password(password, user.hashed_password):
        await _record_failed_attempt(email)
        raise InvalidCredentialsError("Incorrect email or password")

    if not user.is_active:
        # Distinguish: has a pending activation token → admin approved but company
        # hasn't clicked the link yet.  No token → still awaiting admin review.
        activation_result = await session.execute(
            select(ActivationToken).where(
                ActivationToken.company_user_id == user.id,  # type: ignore[arg-type]
                ActivationToken.used == False,  # noqa: E712
            )
        )
        if activation_result.scalar_one_or_none() is not None:
            raise PendingActivationError("account_pending_activation")
        raise PendingApprovalError("account_pending_approval")

    await _clear_failed_attempts(email)
    return user


async def create_user_tokens(user: User, session: AsyncSession) -> tuple[str, str]:
    """Issue a new access + refresh token pair.

    Returns (access_token, raw_refresh_token).
    """
    assert user.id is not None
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )

    raw_refresh, hashed_refresh, expires_at = create_refresh_token()
    db_token = RefreshToken(
        token_hash=hashed_refresh,
        user_id=user.id,
        expires_at=expires_at,
    )
    session.add(db_token)

    return access_token, raw_refresh


async def refresh_user_tokens(
    raw_refresh_token: str, session: AsyncSession
) -> tuple[str, str]:
    """Validate and rotate a refresh token.

    Returns (new_access_token, new_raw_refresh_token).
    """
    token_hash = hash_token(raw_refresh_token)
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
        )
    )
    db_token = result.scalar_one_or_none()

    if (
        db_token is None
        or db_token.is_revoked
        or db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
    ):
        raise InvalidCredentialsError("Invalid or expired refresh token")

    db_token.is_revoked = True
    session.add(db_token)

    user_result = await session.execute(
        select(User).where(User.id == db_token.user_id)  # pyright: ignore[reportArgumentType]
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise InvalidCredentialsError("Invalid or expired refresh token")

    return await create_user_tokens(user, session)


async def logout_user(
    jti: str,
    exp: int,
    raw_refresh_token: str | None,
    session: AsyncSession,
) -> None:
    """Revoke the session: blacklist the access token JTI and revoke the refresh
    token."""
    await blacklist_access_token(jti, exp)

    if raw_refresh_token:
        token_hash = hash_token(raw_refresh_token)
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
            )
        )
        db_token = result.scalar_one_or_none()
        if db_token and not db_token.is_revoked:
            db_token.is_revoked = True


async def mark_invite_used(token: str, session: AsyncSession) -> None:
    """Mark the invite DB record as used after successful registration."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.token == token)  # type: ignore[arg-type]
    )
    record = result.scalar_one_or_none()
    if record and record.status == InviteTokenStatus.PENDING:
        record.status = InviteTokenStatus.USED
        record.used_at = datetime.now(timezone.utc)
        session.add(record)
