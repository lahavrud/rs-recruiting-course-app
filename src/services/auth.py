"""Authentication service layer for business logic."""

import base64
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
from src.core.services.storage import get_storage_provider
from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.models import CompanyProfile, RefreshToken, User
from src.schemas import CompanyProfileRead, UserCreate, UserRead, UserWithCompanyRead
from src.services.admin import get_all_admin_emails
from src.services.exceptions import (
    AccountLockedError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
)

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
    """Raise AccountLockedError if the email is currently locked out."""
    from src.core.tasks import get_redis_pool

    redis = await get_redis_pool()
    ttl = await redis.ttl(_lockout_key(email))
    if ttl > 0:
        raise AccountLockedError(minutes_remaining=math.ceil(ttl / 60))


async def _record_failed_attempt(email: str) -> None:
    """Increment the failure counter; lock the account after threshold."""
    from src.core.tasks import get_redis_pool

    redis = await get_redis_pool()
    key = _attempts_key(email)
    count = await redis.incr(key)
    # Reset attempts TTL on each failure (sliding window)
    await redis.expire(key, _LOCKOUT_SECONDS)
    if count >= _MAX_FAILED_ATTEMPTS:
        await redis.set(_lockout_key(email), "1", ex=_LOCKOUT_SECONDS)
        await redis.delete(key)


async def _clear_failed_attempts(email: str) -> None:
    """Clear the failure counter after a successful login."""
    from src.core.tasks import get_redis_pool

    redis = await get_redis_pool()
    await redis.delete(_attempts_key(email))
    await redis.delete(_lockout_key(email))


_MAX_SIGNATURE_SIZE = 2 * 1024 * 1024  # 2 MB decoded


def _decode_signature(agreement_signature: str) -> bytes:
    """Decode and validate a base64 PNG signature string."""
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
    return sig_bytes


async def register_company_user(
    user_data: UserCreate,
    session: AsyncSession,
    logo_content: bytes,
    logo_filename: str,
    logo_content_type: str | None = None,
    agreement_signature: str = "",
) -> UserWithCompanyRead:
    """Register a new company user with associated company profile."""
    if logo_content_type and logo_content_type not in _ALLOWED_LOGO_TYPES:
        raise ValueError("Logo must be an image file (JPEG, PNG, GIF, or WebP)")
    if len(logo_content) > _MAX_LOGO_SIZE:
        raise ValueError("Logo file size exceeds 5 MB limit")

    sig_bytes = _decode_signature(agreement_signature)

    result = await session.execute(
        select(User).where(User.email == user_data.email)  # pyright: ignore[reportArgumentType]
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise EmailAlreadyExistsError(user_data.email)

    storage = get_storage_provider()
    logo_identifier = await storage.upload_file(
        logo_content, logo_filename, logo_content_type
    )
    sig_filename = f"{user_data.company_profile.company_id}_agreement.png"
    sig_identifier = await storage.upload_file(sig_bytes, sig_filename, "image/png")

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
    new_company_profile = CompanyProfile(
        user_id=new_user.id,
        name=profile.name,
        logo_url=logo_identifier,
        company_id=profile.company_id,
        contact_first_name=profile.contact_first_name,
        contact_last_name=profile.contact_last_name,
        contact_mobile_phone=profile.contact_mobile_phone,
        contact_landline_phone=profile.contact_landline_phone,
        agreement_signature_url=sig_identifier,
        agreement_signed_at=datetime.now(timezone.utc),
    )
    session.add(new_company_profile)
    await session.flush()

    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        contact_name = (
            f"{new_company_profile.contact_first_name} "
            f"{new_company_profile.contact_last_name}"
        )
        company_info = (
            f"A new company '{new_company_profile.name}' has registered "
            "and is pending approval.\n\n"
            f"Company: {new_company_profile.name}\n"
            f"ח.פ: {new_company_profile.company_id}\n"
            f"Contact: {contact_name}\n"
            f"Email: {new_user.email}\n"
            f"Mobile: {new_company_profile.contact_mobile_phone or 'N/A'}\n\n"
            "Please review and approve or reject the registration."
        )
        await enqueue_email_task(
            to=admin_emails,
            subject="New Company Registration Pending Approval",
            body=company_info,
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
        raise InactiveUserError("Account is inactive. Please wait for admin approval.")

    await _clear_failed_attempts(email)
    return user


async def create_user_tokens(user: User, session: AsyncSession) -> tuple[str, str]:
    """Issue a new access + refresh token pair for the given user.

    Returns:
        (access_token, raw_refresh_token)
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
    """Validate a refresh token and issue a rotated pair.

    The old refresh token is revoked on use (single-use rotation).

    Returns:
        (new_access_token, new_raw_refresh_token)

    Raises:
        InvalidCredentialsError: If the token is missing, expired, or revoked.
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
            session.add(db_token)
