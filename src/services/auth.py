"""Authentication service layer for business logic."""

import base64
import logging
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import (
    blacklist_access_token,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.services.file_validation import validate_image_magic_bytes
from src.core.services.storage import get_storage_provider
from src.core.tasks import enqueue_email_task
from src.enums import InviteTokenStatus, UserRole
from src.models import ActivationToken, CompanyProfile, InviteToken, RefreshToken, User
from src.schemas import CompanyProfileRead, UserCreate, UserRead, UserWithCompanyRead
from src.services.admin_companies import get_all_admin_emails
from src.services.exceptions import (
    AccountLockedError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    PendingActivationError,
    PendingApprovalError,
)
from src.templates.email import build_new_registration_html

logger = logging.getLogger(__name__)

_ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5 MB

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


_MAX_SIGNATURE_SIZE = 2 * 1024 * 1024  # 2 MB decoded


def _decode_signature(agreement_signature: str) -> bytes:
    if not agreement_signature.strip():
        raise ValueError("Agreement signature is required")
    try:
        sig_bytes = base64.b64decode(agreement_signature, validate=True)
    except Exception as exc:
        raise ValueError("Invalid signature data") from exc
    if not sig_bytes:
        raise ValueError("Agreement signature is required")
    if len(sig_bytes) > _MAX_SIGNATURE_SIZE:
        raise ValueError("Signature image exceeds maximum allowed size")
    if not sig_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Signature must be a PNG image")
    return sig_bytes


async def _notify_admins_new_registration(
    profile: "CompanyProfile",
    email: str,
    sig_bytes: bytes,
    signed_at: "datetime",
    admin_emails: list[str],
) -> None:
    from src.core.infrastructure.config import settings

    admin_url = f"{settings.frontend_base_url}/admin/companies"
    html = build_new_registration_html(
        company_name=profile.name or "",
        company_id=profile.company_id or "—",
        address=profile.address or "—",
        contact_name=f"{profile.contact_first_name} {profile.contact_last_name}",
        email=email,
        mobile=profile.contact_mobile_phone or "—",
        admin_url=admin_url,
    )
    pdf_bytes: bytes | None = None
    try:
        from src.services.contract_pdf import generate_signed_contract

        pdf_bytes = await generate_signed_contract(
            company_name=profile.name or "",
            company_id=profile.company_id or "",
            address=profile.address or "",
            signed_at=signed_at,
            company_signature_png_bytes=sig_bytes,
        )
    except Exception:
        logger.exception("Failed to generate contract PDF for %s", email)
    attachments = [("חוזה-RS.pdf", pdf_bytes, "application/pdf")] if pdf_bytes else None
    await enqueue_email_task(
        to=admin_emails,
        subject="בקשת הרשמה חדשה ממתינה לאישור – RS Recruiting",
        body=f"חברה חדשה '{profile.name}' נרשמה וממתינה לאישור.\nכתובת: {admin_url}",
        html_body=html,
        attachments=attachments,
    )


async def register_company_user(
    user_data: UserCreate,
    session: AsyncSession,
    logo_content: bytes,
    logo_filename: str,
    logo_content_type: str | None = None,
    agreement_signature: str = "",
    privacy_accepted: bool = False,
) -> UserWithCompanyRead:
    """Register a new company user with associated company profile."""
    if logo_content_type and logo_content_type not in _ALLOWED_LOGO_TYPES:
        raise ValueError("Logo must be an image file (JPEG, PNG, GIF, or WebP)")
    if len(logo_content) > _MAX_LOGO_SIZE:
        raise ValueError("Logo file size exceeds 5 MB limit")
    if logo_content_type and not validate_image_magic_bytes(
        logo_content, logo_content_type
    ):
        raise ValueError("Logo file content does not match the declared image type")

    sig_bytes = _decode_signature(agreement_signature)

    result = await session.execute(
        select(User).where(User.email == user_data.email)  # pyright: ignore[reportArgumentType]
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise EmailAlreadyExistsError(user_data.email)

    storage = get_storage_provider()
    logo_identifier = await storage.upload_file(
        logo_content, f"logos/{logo_filename}", logo_content_type
    )
    sig_filename = f"{user_data.company_profile.company_id}_agreement.png"
    sig_identifier = await storage.upload_file(
        sig_bytes, f"signatures/{sig_filename}", "image/png"
    )

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        role=UserRole.COMPANY,
        is_active=False,
    )
    session.add(new_user)
    await session.flush()

    profile = user_data.company_profile
    now = datetime.now(timezone.utc)
    new_company_profile = CompanyProfile(
        user_id=new_user.id,
        name=profile.name,
        logo_url=logo_identifier,
        company_id=profile.company_id,
        address=profile.address,
        contact_first_name=profile.contact_first_name,
        contact_last_name=profile.contact_last_name,
        contact_mobile_phone=profile.contact_mobile_phone,
        contact_landline_phone=profile.contact_landline_phone,
        agreement_signature_url=sig_identifier,
        agreement_signed_at=now,
        privacy_accepted_at=now if privacy_accepted else None,
    )
    session.add(new_company_profile)
    await session.flush()

    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        defer_after_commit(
            lambda: _notify_admins_new_registration(
                new_company_profile, new_user.email, sig_bytes, now, admin_emails
            )
        )

    return UserWithCompanyRead(
        user=UserRead.model_validate(new_user),
        company_profile=CompanyProfileRead.model_validate(new_company_profile),
    )


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

    # Revoke the used token
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
