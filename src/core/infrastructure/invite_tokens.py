"""Redis-backed invite token management for gated company registration."""

import secrets
from datetime import datetime, timedelta, timezone

from src.services.exceptions import InvalidInviteTokenError

TOKEN_TTL_SECONDS = 48 * 60 * 60  # 48 hours
_KEY_PREFIX = "invite_token:"


def _key(token: str) -> str:
    return f"{_KEY_PREFIX}{token}"


async def generate_invite_token() -> tuple[str, datetime]:
    """Generate a cryptographically secure token, store in Redis.

    Returns (token, expires_at).
    """
    from src.core.tasks import (
        get_redis_pool,  # local import to avoid circular at load time
    )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)
    redis = await get_redis_pool()
    await redis.set(_key(token), "1", ex=TOKEN_TTL_SECONDS)
    return token, expires_at


async def validate_invite_token(token: str) -> None:
    """Raise InvalidInviteTokenError if the token does not exist or has expired."""
    from src.core.tasks import get_redis_pool

    redis = await get_redis_pool()
    value = await redis.get(_key(token))
    if value is None:
        raise InvalidInviteTokenError("Invite token is invalid or has expired")


async def consume_invite_token(token: str) -> None:
    """Delete the token from Redis after successful registration (best-effort)."""
    try:
        from src.core.tasks import get_redis_pool

        redis = await get_redis_pool()
        await redis.delete(_key(token))
    except Exception:
        pass  # registration already committed; token expiry via TTL is the safety net


async def revoke_invite_token(token: str) -> None:
    """Delete the token from Redis (best-effort; token may already be expired)."""
    try:
        from src.core.tasks import get_redis_pool

        redis = await get_redis_pool()
        await redis.delete(_key(token))
    except Exception:
        pass
