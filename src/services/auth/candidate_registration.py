"""Candidate self-registration service (Sprint 11 / issue #605).

Two entry points:

* ``register_candidate`` — handles the public POST /auth/candidate/register
  form. Creates `User(role=CANDIDATE, is_active=False)` (or re-uses an
  existing unactivated row, replacing its password), kills any stale
  unused activation tokens, mints a fresh 2-hour token, and enqueues the
  activation email. The `CandidateProfile` itself is created at activation
  time (see `activate_user`), so failed registrations do not litter the
  admin candidate list.

* ``resend_candidate_activation`` — handles POST /auth/candidate/resend-activation.
  Silent 202 either way; mints a fresh token only when a candidate user
  exists with `is_active=False`. Both per-email and per-IP throttling are
  Redis-backed to prevent inbox flooding.

All audit + email enqueue calls go through the existing app infrastructure;
the rate-limit constants are colocated below so future tuning is one read.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.models import ActivationToken, User
from src.services.utils.audit import record_audit_event
from src.services.utils.legal import CURRENT_PRIVACY_POLICY_VERSION
from src.templates.email import build_candidate_activation_html

logger = logging.getLogger(__name__)

# Sprint 11 spec: candidates get a shorter window than companies (48h).
_CANDIDATE_ACTIVATION_TTL_HOURS = 2

# Per-email resend throttle. slowapi handles per-IP (5/hour) — this Redis
# counter prevents an attacker on multiple IPs from inbox-flooding a victim.
_RESEND_PER_EMAIL_LIMIT = 1
_RESEND_PER_EMAIL_WINDOW_SECONDS = 60 * 60  # 1 hour
_RESEND_PREFIX = "candidate:resend:"


def _resend_key(email: str) -> str:
    return f"{_RESEND_PREFIX}{email}"


async def _check_resend_rate_limit(email: str) -> bool:
    """Return True if the email is under its per-email resend quota.

    Mirrors the Redis-counter pattern from session._record_failed_attempt:
    INCR a TTL-bounded key, allow only `_RESEND_PER_EMAIL_LIMIT` hits per
    window. Redis-unavailable fails *open* (allows the resend) so a Redis
    outage doesn't break a legitimate candidate's recovery flow; per-IP
    slowapi limit still applies.
    """
    from src.core.tasks import get_redis_pool

    try:
        redis = await get_redis_pool()
        key = _resend_key(email)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, _RESEND_PER_EMAIL_WINDOW_SECONDS)
        return count <= _RESEND_PER_EMAIL_LIMIT
    except Exception:
        logger.error(
            "redis_unavailable",
            extra={"surface": "candidate_resend_rate_limit"},
        )
        return True


def _build_activation_url(raw_token: str) -> str:
    return f"{settings.frontend_base_url}/activate?token={raw_token}"


def _mint_activation_token(
    user_id: int,
    *,
    policy_version: str,
) -> tuple[str, ActivationToken]:
    """Generate a raw token + matching ActivationToken row (caller commits)."""
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=_CANDIDATE_ACTIVATION_TTL_HOURS
    )
    activation = ActivationToken(
        token_hash=hash_token(raw_token),
        user_id=user_id,
        expires_at=expires_at,
        consent_policy_version=policy_version,
    )
    return raw_token, activation


async def _delete_stale_tokens(user_id: int, session: AsyncSession) -> None:
    """Drop any prior unused ActivationToken rows for a user.

    Used by both re-registration (so the old link in the candidate's inbox
    stops working when they submit a new password) and resend-activation
    (mint-fresh semantics — only one valid token at a time).
    """
    stale_result = await session.execute(
        select(ActivationToken).where(
            ActivationToken.user_id == user_id,  # type: ignore[arg-type]
            ActivationToken.used == False,  # noqa: E712
        )
    )
    for stale in stale_result.scalars().all():
        await session.delete(stale)
    await session.flush()


def _send_activation_email_deferred(email: str, raw_token: str) -> None:
    """Schedule the activation email to fire after commit."""
    activation_url = _build_activation_url(raw_token)
    plain = (
        "שלום,\n\n"
        "תודה על ההרשמה ל-RS Recruiting.\n\n"
        f"להפעלת החשבון שלכם, לחצו על הקישור הבא בתוך שעתיים:\n{activation_url}\n\n"
        "אם לא התכוונתם להירשם, אפשר להתעלם מהמייל הזה.\n\n"
        "בברכה,\nצוות RS Recruiting"
    )
    html = build_candidate_activation_html(
        activation_url=activation_url,
        ttl_hours=_CANDIDATE_ACTIVATION_TTL_HOURS,
    )

    async def _send() -> None:
        try:
            await enqueue_email_task(
                to=email,
                subject="הפעלת חשבון מועמד – RS Recruiting",
                body=plain,
                html_body=html,
            )
        except Exception:
            logger.exception("Failed to enqueue candidate activation email")

    defer_after_commit(_send)


async def register_candidate(
    email: str,
    password: str,
    full_name: str,
    *,
    privacy_accepted: bool,
    terms_accepted: bool,
    session: AsyncSession,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Create or recycle a pending candidate user + send activation email.

    Silent in every collision case so the response shape can't be used to
    enumerate which emails already have accounts:

    * No matching user → create ``is_active=False`` row + mint a token +
      email it + write the audit row.
    * Email matches an ``is_active=False`` candidate → recycle: update
      password, drop stale tokens, mint fresh, email it, audit it.
    * Email matches an ``is_active=True`` user, OR an inactive non-candidate
      (e.g. a pending company) → no-op. We deliberately mint nothing, send
      nothing, and write no audit row — an audit row would let an
      authenticated admin enumerate accounts via the audit feed, undoing
      the externally-visible guarantee.

    Caller is responsible for the outer transaction (the router wraps this
    in ``transactional(session)``).
    """
    if not privacy_accepted or not terms_accepted:
        # Defense-in-depth — the router also enforces this on the API surface.
        raise ValueError("privacy_and_terms_required")

    normalized_email = email.lower().strip()

    result = await session.execute(
        select(User).where(User.email == normalized_email)  # type: ignore[arg-type]
    )
    existing = result.scalar_one_or_none()

    # Collision cases that previously raised EmailAlreadyExistsError. Now
    # we return silently so the HTTP response is indistinguishable from a
    # fresh registration. Crucially: no token mint, no email, no audit
    # row (an audit row would leak via the admin audit feed).
    if existing is not None and (
        existing.is_active or existing.role != UserRole.CANDIDATE
    ):
        logger.info(
            "candidate_register_silent_collision",
            extra={"email_prefix": normalized_email.split("@", 1)[0][:2] + "***"},
        )
        return

    if existing is None:
        user = User(
            email=normalized_email,
            hashed_password=get_password_hash(password),
            role=UserRole.CANDIDATE,
            is_active=False,
        )
        session.add(user)
        await session.flush()
    else:
        user = existing
        user.hashed_password = get_password_hash(password)
        await _delete_stale_tokens(user.id, session)

    assert user.id is not None
    raw_token, activation = _mint_activation_token(
        user.id, policy_version=CURRENT_PRIVACY_POLICY_VERSION
    )
    session.add(activation)
    await session.flush()

    # Stash full_name on the audit detail so it's recoverable if the
    # registration is abandoned and the User is later cleaned up by cron;
    # the canonical write to CandidateProfile.full_name happens at activation.
    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="candidate_register_requested",
        target_type="User",
        target_id=user.id,
        detail=(
            f"policy_version={CURRENT_PRIVACY_POLICY_VERSION};full_name={full_name}"
        ),
        ip_address=ip_address,
    )

    _send_activation_email_deferred(normalized_email, raw_token)


async def resend_candidate_activation(
    email: str,
    *,
    session: AsyncSession,
    ip_address: str | None = None,
) -> None:
    """Resend the candidate activation email if applicable.

    Silent in all branches — caller maps to 202 regardless. Mints a fresh
    token only when a candidate user exists with `is_active=False`.
    Per-email rate-limited via Redis (caller handles per-IP via slowapi).
    """
    normalized_email = email.lower().strip()

    if not await _check_resend_rate_limit(normalized_email):
        logger.warning(
            "candidate_resend_rate_limited",
            extra={"email_prefix": normalized_email.split("@", 1)[0][:2] + "***"},
        )
        return

    result = await session.execute(
        select(User).where(User.email == normalized_email)  # type: ignore[arg-type]
    )
    user = result.scalar_one_or_none()

    if user is None or user.role != UserRole.CANDIDATE or user.is_active:
        return

    assert user.id is not None
    await _delete_stale_tokens(user.id, session)
    raw_token, activation = _mint_activation_token(
        user.id, policy_version=CURRENT_PRIVACY_POLICY_VERSION
    )
    session.add(activation)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="candidate_resend_activation_requested",
        target_type="User",
        target_id=user.id,
        ip_address=ip_address,
    )

    _send_activation_email_deferred(normalized_email, raw_token)
