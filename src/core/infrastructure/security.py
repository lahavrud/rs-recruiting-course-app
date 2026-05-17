"""Security utilities for password hashing and JWT tokens."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from src.core.infrastructure.config import get_jwt_secret_key, settings
from src.services.exceptions import RedisUnavailableError

logger = logging.getLogger(__name__)

_BLACKLIST_PREFIX = "blacklist:jti:"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def hash_token(token: str) -> str:
    """SHA-256 hash a token for safe DB/Redis storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Create a JWT access token with an embedded JTI for blacklisting."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    to_encode.update({"exp": expire, "jti": secrets.token_urlsafe(16)})
    return jwt.encode(to_encode, get_jwt_secret_key(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, get_jwt_secret_key(), algorithms=[settings.jwt_algorithm]
        )
    except InvalidTokenError:
        return None


def create_refresh_token() -> tuple[str, str, datetime]:
    """Generate a cryptographically secure refresh token.

    Returns:
        (raw_token, hashed_token, expires_at)
    """
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    return raw, hash_token(raw), expires_at


async def blacklist_access_token(jti: str, exp: int) -> None:
    """Store a JTI in Redis so it is rejected until the token would have expired.

    Raises RedisUnavailableError if Redis is unreachable — callers must not
    silently succeed when blacklisting fails (a logged-out token stays valid).
    """
    from src.core.tasks import get_redis_pool  # local import avoids circular

    ttl = exp - int(datetime.now(timezone.utc).timestamp())
    if ttl <= 0:
        return
    try:
        redis = await get_redis_pool()
        await redis.set(f"{_BLACKLIST_PREFIX}{jti}", "1", ex=ttl)
    except Exception as exc:
        logger.error(
            "redis_unavailable",
            extra={"surface": "blacklist_write", "jti": jti},
        )
        raise RedisUnavailableError(
            "Redis unavailable; cannot blacklist token"
        ) from exc


async def is_access_token_blacklisted(jti: str) -> bool:
    """Return True if the JTI has been blacklisted (i.e. logged out).

    Raises RedisUnavailableError when Redis is unavailable — callers must treat
    this as a service outage (fail-closed) rather than assuming the token is valid.
    """
    from src.core.tasks import get_redis_pool

    try:
        redis = await get_redis_pool()
        return await redis.get(f"{_BLACKLIST_PREFIX}{jti}") is not None
    except Exception as exc:
        logger.error(
            "redis_unavailable",
            extra={"surface": "blacklist_read", "jti": jti},
        )
        raise RedisUnavailableError(
            "Redis unavailable; cannot check token blacklist"
        ) from exc
