"""Tests for Redis fail-closed policy across blacklist, lockout, and health."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.infrastructure.security import (
    blacklist_access_token,
    is_access_token_blacklisted,
)
from src.services.auth import _check_lockout, _record_failed_attempt
from src.services.exceptions import RedisUnavailableError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _broken_redis_pool():
    """Return an async mock for get_redis_pool whose Redis raises on every op."""
    redis = AsyncMock()
    redis.get.side_effect = ConnectionError("Redis down")
    redis.set.side_effect = ConnectionError("Redis down")
    redis.ttl.side_effect = ConnectionError("Redis down")
    redis.incr.side_effect = ConnectionError("Redis down")
    return AsyncMock(return_value=redis)


# ---------------------------------------------------------------------------
# blacklist_access_token — fail-closed write path
# ---------------------------------------------------------------------------


class TestBlacklistAccessTokenFailClosed:
    @pytest.mark.asyncio
    async def test_raises_when_redis_unavailable(self):
        future_exp = 9999999999
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            with pytest.raises(RedisUnavailableError):
                await blacklist_access_token("some-jti", future_exp)

    @pytest.mark.asyncio
    async def test_logs_error_when_redis_unavailable(self, caplog):
        import logging

        future_exp = 9999999999
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            with caplog.at_level(
                logging.ERROR, logger="src.core.infrastructure.security"
            ):
                with pytest.raises(RedisUnavailableError):
                    await blacklist_access_token("jti-123", future_exp)
        assert "redis_unavailable" in caplog.text

    @pytest.mark.asyncio
    async def test_skips_redis_when_token_already_expired(self):
        """Should return immediately without touching Redis if TTL <= 0."""
        past_exp = 1
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            await blacklist_access_token("some-jti", past_exp)
            mock_pool.assert_not_called()


# ---------------------------------------------------------------------------
# is_access_token_blacklisted — fail-closed read path
# ---------------------------------------------------------------------------


class TestIsAccessTokenBlacklistedFailClosed:
    @pytest.mark.asyncio
    async def test_raises_when_redis_unavailable(self):
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            with pytest.raises(RedisUnavailableError):
                await is_access_token_blacklisted("some-jti")

    @pytest.mark.asyncio
    async def test_logs_error_when_redis_unavailable(self, caplog):
        import logging

        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            with caplog.at_level(
                logging.ERROR, logger="src.core.infrastructure.security"
            ):
                with pytest.raises(RedisUnavailableError):
                    await is_access_token_blacklisted("jti-456")
        assert "redis_unavailable" in caplog.text

    @pytest.mark.asyncio
    async def test_returns_true_when_jti_found(self):
        redis = AsyncMock()
        redis.get.return_value = b"1"
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock, return_value=redis
        ):
            result = await is_access_token_blacklisted("revoked-jti")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_jti_not_found(self):
        redis = AsyncMock()
        redis.get.return_value = None
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock, return_value=redis
        ):
            result = await is_access_token_blacklisted("valid-jti")
        assert result is False


# ---------------------------------------------------------------------------
# get_token_payload dependency — 503 on RedisUnavailableError
# ---------------------------------------------------------------------------


class TestGetTokenPayload503:
    @pytest.mark.asyncio
    async def test_returns_503_when_blacklist_check_raises(self):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        from src.core.infrastructure.dependencies import get_token_payload
        from src.core.infrastructure.security import create_access_token

        token = create_access_token({"sub": "1", "email": "x@x.com", "role": "ADMIN"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "src.core.infrastructure.dependencies.is_access_token_blacklisted",
            new_callable=AsyncMock,
            side_effect=RedisUnavailableError("down"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_token_payload(credentials)

        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Lockout helpers — fail-open with structured error log
# ---------------------------------------------------------------------------


class TestLockoutFailOpen:
    @pytest.mark.asyncio
    async def test_check_lockout_does_not_raise_when_redis_down(self):
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            await _check_lockout("user@example.com")  # must not raise

    @pytest.mark.asyncio
    async def test_check_lockout_logs_error_when_redis_down(self, caplog):
        import logging

        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            with caplog.at_level(logging.ERROR, logger="src.services.auth"):
                await _check_lockout("user@example.com")
        assert "redis_unavailable" in caplog.text

    @pytest.mark.asyncio
    async def test_record_failed_attempt_does_not_raise_when_redis_down(self):
        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            await _record_failed_attempt("user@example.com")  # must not raise

    @pytest.mark.asyncio
    async def test_record_failed_attempt_logs_error_when_redis_down(self, caplog):
        import logging

        with patch(
            "src.core.tasks.get_redis_pool", new_callable=AsyncMock
        ) as mock_pool:
            mock_pool.return_value = _broken_redis_pool().return_value
            with caplog.at_level(logging.ERROR, logger="src.services.auth"):
                await _record_failed_attempt("user@example.com")
        assert "redis_unavailable" in caplog.text


# ---------------------------------------------------------------------------
# /health — Redis status surfaced
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_ok_when_redis_up(self, public_client):
        ping_redis = AsyncMock()
        ping_redis.ping = AsyncMock(return_value=True)
        with patch(
            "src.core.tasks.get_redis_pool",
            new_callable=AsyncMock,
            return_value=ping_redis,
        ):
            response = await public_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["redis"] == "ok"
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_degraded_when_redis_down(self, public_client):
        with patch(
            "src.core.tasks.get_redis_pool",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis down"),
        ):
            response = await public_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["redis"] == "unavailable"
        assert data["status"] == "degraded"
