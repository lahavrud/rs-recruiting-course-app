"""Service-level tests for candidate self-registration + resend
(Sprint 11 / issue #605).

Most behavior is exercised end-to-end in
`tests/api/auth/test_candidate_registration.py`. This file pins
service-layer invariants that the API tests can't see directly:
the in-process state after a service call (no HTTP marshaling).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import ActivationToken, AuditLog, User
from src.services.auth.candidate_registration import (
    _CANDIDATE_ACTIVATION_TTL_HOURS,
    register_candidate,
    resend_candidate_activation,
)


@pytest.fixture
def _mock_redis():
    """Redis-backed per-email throttle stub — counts within the window."""
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    with patch(
        "src.core.tasks.get_redis_pool",
        new_callable=AsyncMock,
        return_value=redis,
    ):
        yield redis


@pytest.fixture
def _patch_email():
    with patch(
        "src.services.auth.candidate_registration.enqueue_email_task",
        new_callable=AsyncMock,
    ) as p:
        yield p


@pytest.mark.asyncio
async def test_register_candidate_mints_2h_token(session: AsyncSession, _patch_email):
    """Token TTL is exactly the documented 2-hour candidate window."""
    await register_candidate(
        "ttl-check@test.com",
        "SecurePass1!",  # pragma: allowlist secret
        "TTL Check",
        privacy_accepted=True,
        terms_accepted=True,
        session=session,
    )
    await session.commit()

    user = (
        await session.execute(
            select(User).where(User.email == "ttl-check@test.com")  # type: ignore[arg-type]
        )
    ).scalar_one()
    token = (
        await session.execute(
            select(ActivationToken).where(
                ActivationToken.user_id == user.id  # type: ignore[arg-type]
            )
        )
    ).scalar_one()
    delta = token.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
    expected_seconds = _CANDIDATE_ACTIVATION_TTL_HOURS * 3600
    jitter_seconds = abs(delta.total_seconds() - expected_seconds)
    # Allow one minute of jitter between mint and assertion.
    assert jitter_seconds < 60


@pytest.mark.asyncio
async def test_register_candidate_silent_on_active_email(
    session: AsyncSession, _patch_email
):
    """Active-email collision returns silently — no token, no email, no audit.

    Was raising EmailAlreadyExistsError, which leaked existence via the 409.
    """
    session.add(
        User(
            email="active@test.com",
            hashed_password=get_password_hash("Existing1!"),  # pragma: allowlist secret
            role=UserRole.CANDIDATE,
            is_active=True,
        )
    )
    await session.commit()

    result = await register_candidate(
        "active@test.com",
        "AnotherPass1!",  # pragma: allowlist secret
        "Hijack Attempt",
        privacy_accepted=True,
        terms_accepted=True,
        session=session,
    )
    assert result is None

    tokens = (await session.execute(select(ActivationToken))).scalars().all()
    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "candidate_register_requested"  # type: ignore[arg-type]
                )
            )
        )
        .scalars()
        .all()
    )
    assert tokens == []
    assert audits == []


@pytest.mark.asyncio
async def test_register_candidate_silent_on_pending_non_candidate(
    session: AsyncSession, _patch_email
):
    """Pending company user with the same email must not be hijacked AND
    must not reveal its existence via the response."""
    session.add(
        User(
            email="pending-company@test.com",
            hashed_password=get_password_hash("Pending1!"),  # pragma: allowlist secret
            role=UserRole.COMPANY,
            is_active=False,
        )
    )
    await session.commit()

    result = await register_candidate(
        "pending-company@test.com",
        "Other1!",  # pragma: allowlist secret
        "Other",
        privacy_accepted=True,
        terms_accepted=True,
        session=session,
    )
    assert result is None

    # The company user row is untouched.
    existing = (
        await session.execute(
            select(User).where(User.email == "pending-company@test.com")  # type: ignore[arg-type]
        )
    ).scalar_one()
    assert existing.role == UserRole.COMPANY
    assert existing.is_active is False


@pytest.mark.asyncio
async def test_register_candidate_requires_consent(session: AsyncSession, _patch_email):
    with pytest.raises(ValueError):
        await register_candidate(
            "no-consent@test.com",
            "SecurePass1!",  # pragma: allowlist secret
            "No Consent",
            privacy_accepted=False,
            terms_accepted=True,
            session=session,
        )


@pytest.mark.asyncio
async def test_resend_silent_when_user_unknown(
    session: AsyncSession, _patch_email, _mock_redis
):
    """No user matching the email → service returns None, enqueues nothing."""
    await resend_candidate_activation("unknown@test.com", session=session)
    await session.commit()
    _patch_email.assert_not_called()


@pytest.mark.asyncio
async def test_resend_blocked_when_per_email_limit_exceeded(
    session: AsyncSession, _patch_email
):
    """When Redis reports the email has hit its quota, no token is minted."""
    user = User(
        email="throttled@test.com",
        hashed_password=get_password_hash("X1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=False,
    )
    session.add(user)
    await session.commit()

    blocked_redis = AsyncMock()
    blocked_redis.incr = AsyncMock(return_value=2)  # already over the 1/hour cap
    blocked_redis.expire = AsyncMock(return_value=True)
    with patch(
        "src.core.tasks.get_redis_pool",
        new_callable=AsyncMock,
        return_value=blocked_redis,
    ):
        await resend_candidate_activation("throttled@test.com", session=session)
    await session.commit()

    tokens = (
        (
            await session.execute(
                select(ActivationToken).where(
                    ActivationToken.user_id == user.id  # type: ignore[arg-type]
                )
            )
        )
        .scalars()
        .all()
    )
    assert tokens == []
    _patch_email.assert_not_called()
