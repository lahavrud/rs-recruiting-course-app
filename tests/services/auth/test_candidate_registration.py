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
from src.models import ActivationToken, User
from src.services.auth.candidate_registration import (
    _CANDIDATE_ACTIVATION_TTL_HOURS,
    register_candidate,
    resend_candidate_activation,
)
from src.services.exceptions import EmailAlreadyExistsError


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
    # Sprint 11 / candidate-activation-followups: the supplied name is
    # snapshotted on the token so activation can prefill CandidateProfile.
    assert token.full_name == "TTL Check"


@pytest.mark.asyncio
async def test_resend_carries_full_name_from_prior_token(
    session: AsyncSession, _patch_email, _mock_redis
):
    """A resend after the original token was lost must reuse the same name."""
    from src.services.auth.candidate_registration import (
        resend_candidate_activation,
    )

    await register_candidate(
        "resend-name@test.com",
        "SecurePass1!",  # pragma: allowlist secret
        "Resend Name",
        privacy_accepted=True,
        terms_accepted=True,
        session=session,
    )
    await session.commit()

    await resend_candidate_activation(
        "resend-name@test.com",
        session=session,
    )
    await session.commit()

    tokens = (
        (
            await session.execute(
                select(ActivationToken)
                .join(User, User.id == ActivationToken.user_id)  # type: ignore[arg-type]
                .where(User.email == "resend-name@test.com")  # type: ignore[arg-type]
            )
        )
        .scalars()
        .all()
    )
    assert len(tokens) == 1, "resend must keep exactly one live token"
    assert tokens[0].full_name == "Resend Name"


@pytest.mark.asyncio
async def test_register_candidate_rejects_active_email(
    session: AsyncSession, _patch_email
):
    """Active-email collision raises EmailAlreadyExistsError so the router
    can surface 409 to the UI."""
    session.add(
        User(
            email="active@test.com",
            hashed_password=get_password_hash("Existing1!"),  # pragma: allowlist secret
            role=UserRole.CANDIDATE,
            is_active=True,
        )
    )
    await session.commit()

    with pytest.raises(EmailAlreadyExistsError):
        await register_candidate(
            "active@test.com",
            "AnotherPass1!",  # pragma: allowlist secret
            "Hijack Attempt",
            privacy_accepted=True,
            terms_accepted=True,
            session=session,
        )


@pytest.mark.asyncio
async def test_register_candidate_rejects_pending_non_candidate(
    session: AsyncSession, _patch_email
):
    """Pending company user with the same email must not be hijacked."""
    session.add(
        User(
            email="pending-company@test.com",
            hashed_password=get_password_hash("Pending1!"),  # pragma: allowlist secret
            role=UserRole.COMPANY,
            is_active=False,
        )
    )
    await session.commit()

    with pytest.raises(EmailAlreadyExistsError):
        await register_candidate(
            "pending-company@test.com",
            "Other1!",  # pragma: allowlist secret
            "Other",
            privacy_accepted=True,
            terms_accepted=True,
            session=session,
        )


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
