"""Service-level tests for activation token consumption."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash, hash_token
from rs_shared.enums import UserRole
from rs_shared.models import ActivationToken, CandidateProfile, User
from rs_shared.services.auth.activation import activate_company, activate_user
from rs_shared.services.exceptions import InvalidActivationTokenError
from rs_shared.services.utils.legal import CURRENT_PRIVACY_POLICY_VERSION


async def _make_pending_user(
    session: AsyncSession, email: str = "company@test.com"
) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("SecurePass1!"),
        role=UserRole.COMPANY,
        is_active=False,
    )
    session.add(user)
    await session.flush()
    return user


def _make_token(user_id: int, *, used: bool = False, expired: bool = False) -> str:
    return f"token-{user_id}-{used}-{expired}"


@pytest.mark.asyncio
async def test_activate_company_marks_user_active_and_token_used(
    session: AsyncSession,
):
    user = await _make_pending_user(session)
    token = _make_token(user.id)
    session.add(
        ActivationToken(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    await session.commit()

    activated = await activate_company(token, session)
    await session.commit()

    assert activated.id == user.id
    assert activated.is_active is True


@pytest.mark.asyncio
async def test_activate_company_rejects_unknown_token(session: AsyncSession):
    with pytest.raises(InvalidActivationTokenError):
        await activate_company("does-not-exist", session)


@pytest.mark.asyncio
async def test_activate_company_rejects_used_token(session: AsyncSession):
    user = await _make_pending_user(session, email="used@test.com")
    token = _make_token(user.id, used=True)
    session.add(
        ActivationToken(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used=True,
        )
    )
    await session.commit()

    with pytest.raises(InvalidActivationTokenError):
        await activate_company(token, session)


@pytest.mark.asyncio
async def test_activate_company_rejects_expired_token(session: AsyncSession):
    user = await _make_pending_user(session, email="expired@test.com")
    token = _make_token(user.id, expired=True)
    session.add(
        ActivationToken(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    await session.commit()

    with pytest.raises(InvalidActivationTokenError):
        await activate_company(token, session)


# --------------------------------------------------------------------------
# Sprint 11 / #605 — candidate activation branch
# --------------------------------------------------------------------------


async def _make_pending_candidate(
    session: AsyncSession,
    email: str = "cand@test.com",
) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("SecurePass1!"),
        role=UserRole.CANDIDATE,
        is_active=False,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_activate_candidate_creates_profile_and_writes_consent(
    session: AsyncSession,
):
    user = await _make_pending_candidate(session)
    raw_token = "candidate-fresh-token"
    session.add(
        ActivationToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            consent_policy_version=CURRENT_PRIVACY_POLICY_VERSION,
        )
    )
    await session.commit()

    activated = await activate_user(
        raw_token,
        session,
        ip_address="203.0.113.7",
        user_agent="vitest/1.0",
    )
    await session.commit()

    assert activated.id == user.id
    assert activated.is_active is True

    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.user_id == user.id  # type: ignore[arg-type]
        )
    )
    profile = result.scalar_one()
    assert profile.email == user.email
    assert profile.consent_ip == "203.0.113.7"
    assert profile.consent_user_agent == "vitest/1.0"
    assert profile.consent_policy_version == CURRENT_PRIVACY_POLICY_VERSION
    assert profile.consent_given_at is not None


@pytest.mark.asyncio
async def test_activate_candidate_links_existing_anonymous_lead(
    session: AsyncSession,
):
    """If a CandidateProfile already exists for the email (e.g. they
    applied anonymously before registering), activation must LINK that
    profile to the new user instead of creating a duplicate."""
    user = await _make_pending_candidate(session, email="anon@test.com")
    lead = CandidateProfile(
        full_name="Anonymous Lead",
        email="anon@test.com",
        phone="050-000-0000",
    )
    session.add(lead)
    await session.flush()

    raw_token = "candidate-link-token"
    session.add(
        ActivationToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            consent_policy_version=CURRENT_PRIVACY_POLICY_VERSION,
        )
    )
    await session.commit()

    await activate_user(raw_token, session, ip_address=None, user_agent=None)
    await session.commit()

    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.email == "anon@test.com"  # type: ignore[arg-type]
        )
    )
    profiles = result.scalars().all()
    assert len(profiles) == 1
    assert profiles[0].id == lead.id
    assert profiles[0].user_id == user.id
    assert profiles[0].full_name == "Anonymous Lead"
