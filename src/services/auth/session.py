"""Authentication service layer for business logic.

Company registration lives in `auth_register.py` to keep this file
under the service-layer line cap.
"""

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import (
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
from src.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_DURATION = timedelta(minutes=15)


def _email_prefix(email: str) -> str:
    """First two chars of the local part — loggable without storing PII."""
    local = email.split("@")[0]
    return f"{local[:2]}***"


def _check_lockout(user: User, client_ip: str | None = None) -> None:
    """Raise AccountLockedError if the user is currently locked out."""
    if user.locked_until is None:
        return
    now = datetime.now(timezone.utc)
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until > now:
        ttl = (locked_until - now).total_seconds()
        logger.warning(
            "login_lockout_hit",
            extra={
                "email_prefix": _email_prefix(user.email),
                "ttl_s": int(ttl),
                "ip": client_ip,
            },
        )
        raise AccountLockedError(minutes_remaining=math.ceil(ttl / 60))


async def _record_failed_attempt(
    user_id: int, email: str, client_ip: str | None = None
) -> None:
    """Atomically increment failed_login_attempts; lock the account at threshold.

    Uses its own DB session so the write persists even when the calling
    request raises InvalidCredentialsError and its session rolls back.
    The UPDATE is a single atomic SQL statement — no read-modify-write race.
    """
    from src.core.infrastructure.database import async_session as _session_factory

    async with _session_factory() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)  # type: ignore[arg-type]
            .values(failed_login_attempts=User.failed_login_attempts + 1)
        )
        await session.flush()

        result = await session.execute(
            select(User.failed_login_attempts).where(User.id == user_id)  # type: ignore[arg-type]
        )
        count = result.scalar_one()

        if count >= _MAX_FAILED_ATTEMPTS:
            await session.execute(
                update(User)
                .where(User.id == user_id)  # type: ignore[arg-type]
                .values(
                    failed_login_attempts=0,
                    locked_until=datetime.now(timezone.utc) + _LOCKOUT_DURATION,
                )
            )
            logger.warning(
                "login_account_locked",
                extra={"email_prefix": _email_prefix(email), "ip": client_ip},
            )
        else:
            logger.warning(
                "login_failed",
                extra={
                    "email_prefix": _email_prefix(email),
                    "attempt": count,
                    "ip": client_ip,
                },
            )

        await session.commit()


async def _clear_failed_attempts(user_id: int) -> None:
    """Reset lockout state on successful login or password reset."""
    from src.core.infrastructure.database import async_session as _session_factory

    async with _session_factory() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)  # type: ignore[arg-type]
            .values(failed_login_attempts=0, locked_until=None)
        )
        await session.commit()


async def authenticate_user(
    email: str,
    password: str,
    session: AsyncSession,
    client_ip: str | None = None,
) -> User:
    """Authenticate a user by email and password.

    Checks for account lockout before attempting credential validation.
    Tracks failed attempts and locks the account after too many failures.
    """
    email = email.lower().strip()
    result = await session.execute(
        select(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("login_email_not_found", extra={"ip": client_ip})
        raise InvalidCredentialsError("Incorrect email or password")

    _check_lockout(user, client_ip)

    if not verify_password(password, user.hashed_password):
        assert user.id is not None
        await _record_failed_attempt(user.id, email, client_ip)
        raise InvalidCredentialsError("Incorrect email or password")

    if not user.is_active:
        # Distinguish: has a pending activation token → admin approved but company
        # hasn't clicked the link yet.  No token → still awaiting admin review.
        activation_result = await session.execute(
            select(ActivationToken).where(
                ActivationToken.user_id == user.id,  # type: ignore[arg-type]
                ActivationToken.used == False,  # noqa: E712
            )
        )
        if activation_result.scalar_one_or_none() is not None:
            raise PendingActivationError("account_pending_activation")
        raise PendingApprovalError("account_pending_approval")

    assert user.id is not None
    await _clear_failed_attempts(user.id)
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

    if db_token is None:
        raise InvalidCredentialsError("Invalid or expired refresh token")

    # Expired-on-discovery rows are deleted on the way out so the
    # ``refreshtoken`` table doesn't accumulate dead state without a
    # cleanup path (issue #641). The HTTP behaviour is unchanged — the
    # caller still gets 401.
    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await session.delete(db_token)
        raise InvalidCredentialsError("Invalid or expired refresh token")

    user_result = await session.execute(
        select(User).where(User.id == db_token.user_id)  # pyright: ignore[reportArgumentType]
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise InvalidCredentialsError("Invalid or expired refresh token")

    # Rotate: drop the consumed token before minting the next one. The
    # previous "is_revoked = True" approach left rows accumulating
    # forever — and the code treated ``revoked`` and ``missing``
    # identically (both raised InvalidCredentialsError), so the column
    # provided no extra security value.
    await session.delete(db_token)
    await session.flush()

    return await create_user_tokens(user, session)


async def logout_user(
    raw_refresh_token: str | None,
    session: AsyncSession,
) -> None:
    """End the session: delete the refresh-token row.

    The 10-minute access token TTL (shortened from 30 min as part of the
    Redis removal) is the accepted tolerance window after logout.
    """
    if raw_refresh_token:
        token_hash = hash_token(raw_refresh_token)
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
            )
        )
        db_token = result.scalar_one_or_none()
        if db_token is not None:
            await session.delete(db_token)


async def mark_invite_used(token: str, session: AsyncSession) -> None:
    """Mark the invite DB record as used after successful registration."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.token_hash == hash_token(token))  # type: ignore[arg-type]
    )
    record = result.scalar_one_or_none()
    if record and record.status == InviteTokenStatus.PENDING:
        record.status = InviteTokenStatus.USED
        record.used_at = datetime.now(timezone.utc)
        session.add(record)
        await record_audit_event(
            session,
            actor_user_id=None,
            action="invite_used",
            target_type="invite",
            target_id=record.id,
            detail=record.email,
        )
