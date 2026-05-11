"""Self-service password reset.

Security model:
- Reset tokens are random 32-byte URL-safe strings; DB stores only their
  SHA-256 hash (mirrors `RefreshToken`).
- `forgot_password` MUST be indistinguishable for known and unknown emails:
  the caller always sees the same response, and the email send is deferred
  via `defer_after_commit` so timing differences from SMTP cannot leak.
- Per-email rate limit (3/hour) lives in Redis and protects victims from
  inbox-spam when the IP rate limit is wide-open.
- Successful reset revokes every refresh token for the user and clears any
  lockout state, so a leaked password can no longer ride existing sessions.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.models import PasswordResetToken, RefreshToken, User
from src.services.auth import _clear_failed_attempts
from src.services.exceptions import InvalidPasswordResetTokenError
from src.templates.email import build_password_reset_html

logger = logging.getLogger(__name__)

_RESET_TOKEN_TTL = timedelta(hours=1)
_EMAIL_RATE_LIMIT_PREFIX = "password_reset:email:"
_EMAIL_RATE_LIMIT_WINDOW_SECONDS = 60 * 60  # 1 hour
_EMAIL_RATE_LIMIT_MAX = 3


async def _per_email_rate_limit_ok(email: str) -> bool:
    """Allow at most _EMAIL_RATE_LIMIT_MAX reset requests per email per hour.

    Fails open if Redis is unavailable — losing the limit briefly is better
    than locking everyone out of password recovery during a Redis outage.
    """
    from src.core.tasks import get_redis_pool

    key = f"{_EMAIL_RATE_LIMIT_PREFIX}{email.lower()}"
    try:
        redis = await get_redis_pool()
        # INCR + EXPIRE(NX) issued as one pipelined transaction so a request
        # that increments the counter cannot leave the key without a TTL.
        # A prior implementation set EXPIRE only on count==1, which left the
        # key permanent if the EXPIRE round-trip dropped — observed in the
        # wild as count=13, ttl=-1.
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, _EMAIL_RATE_LIMIT_WINDOW_SECONDS, nx=True)
            count, _ = await pipe.execute()
        return count <= _EMAIL_RATE_LIMIT_MAX
    except Exception:
        logger.error(
            "redis_unavailable", extra={"surface": "password_reset_rate_limit"}
        )
        return True


async def request_password_reset(email: str, session: AsyncSession) -> None:
    """Issue a reset token + send email when the address belongs to a user.

    Silent on unknown emails. The caller always observes the same outcome.
    Matches the existing case-sensitive lookup used by `authenticate_user`.
    """
    cleaned = email.strip()
    if not cleaned:
        return

    result = await session.execute(
        select(User).where(User.email == cleaned)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if user is None or user.id is None:
        return

    if not await _per_email_rate_limit_ok(cleaned):
        # Silent skip — surface only via logs.  Returning here keeps the
        # endpoint response identical to the unknown-email branch and stops
        # an attacker from flooding the user's inbox.
        logger.info(
            "password_reset_rate_limited", extra={"email_hash": hash_token(cleaned)}
        )
        return

    raw_token = secrets.token_urlsafe(32)
    token_record = PasswordResetToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + _RESET_TOKEN_TTL,
        used=False,
    )
    session.add(token_record)

    reset_url = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    recipient = user.email
    html = build_password_reset_html(reset_url)
    plain = (
        "קיבלנו בקשה לאיפוס סיסמה לחשבון שלך ב-RS Recruiting.\n"
        f"להגדרת סיסמה חדשה: {reset_url}\n"
        "הקישור תקף ל-60 דקות.\n"
        "אם לא ביקשת איפוס סיסמה, ניתן להתעלם מההודעה."
    )
    defer_after_commit(
        lambda: enqueue_email_task(
            to=recipient,
            subject="איפוס סיסמה — RS Recruiting",
            body=plain,
            html_body=html,
        )
    )


async def reset_password(
    raw_token: str, new_password: str, session: AsyncSession
) -> User:
    """Consume a reset token, set the new password, revoke all refresh tokens.

    Raises:
        InvalidPasswordResetTokenError: token missing, used, or expired.
    """
    token_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
        )
    )
    record = result.scalar_one_or_none()
    if record is None or record.used:
        raise InvalidPasswordResetTokenError("הקישור אינו תקף או שכבר נעשה בו שימוש")
    if record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise InvalidPasswordResetTokenError("פג תוקף הקישור")

    user_result = await session.execute(
        select(User).where(User.id == record.user_id)  # pyright: ignore[reportArgumentType]
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise InvalidPasswordResetTokenError("המשתמש לא נמצא")

    user.hashed_password = get_password_hash(new_password)
    record.used = True

    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,  # pyright: ignore[reportArgumentType]
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        .values(is_revoked=True)
    )

    defer_after_commit(lambda: _clear_failed_attempts(user.email))
    return user
