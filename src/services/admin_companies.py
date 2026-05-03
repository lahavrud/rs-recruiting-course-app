"""Admin service layer for company management."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.services.storage import get_storage_provider
from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.models import ActivationToken, Application, CompanyProfile, Job, User
from src.schemas import ActiveCompanyRead, CompanyProfileRead, UserRead
from src.services.contract_pdf import generate_signed_contract
from src.services.email_templates import build_approval_html, build_rejection_html
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
    InvalidActivationTokenError,
)

_ACTIVATION_TTL_HOURS = 48


async def get_all_admin_emails(session: AsyncSession) -> list[str]:
    """Get email addresses of all active admin users."""
    result = await session.execute(
        select(User.email).where(  # pyright: ignore[reportArgumentType]
            User.role == UserRole.ADMIN,
            User.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def list_pending_companies(session: AsyncSession) -> list[dict]:
    """List all pending company registrations (inactive COMPANY users)."""
    result = await session.execute(
        select(User, CompanyProfile)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.role == UserRole.COMPANY, User.is_active == False)  # noqa: E712
        .order_by(User.created_at)
    )
    return [
        {
            "user": UserRead.model_validate(user),
            "company_profile": CompanyProfileRead.model_validate(cp),
        }
        for user, cp in result.all()
    ]


async def approve_company(company_user_id: int, session: AsyncSession) -> dict:
    """Approve a pending company registration.

    Generates an activation token, builds the signed contract PDF, and emails
    the company an activation link with the PDF attached.  The account is NOT
    activated here — the company must click the link.

    Raises:
        CompanyNotFoundError: If company user not found
        CompanyNotPendingError: If already approved or not a COMPANY user
    """
    result = await session.execute(
        select(User).where(User.id == company_user_id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if not user:
        raise CompanyNotFoundError(f"Company user with ID {company_user_id} not found")
    if user.role != UserRole.COMPANY:
        raise CompanyNotPendingError(
            f"User {company_user_id} is not a COMPANY user (role: {user.role})"
        )
    if user.is_active:
        raise CompanyNotPendingError(
            f"Company user {company_user_id} is already approved (active)"
        )

    # Revoke any previous (unused, possibly expired) activation token before
    # issuing a new one.  This allows re-approval after a token expires or after
    # the admin rejects and later changes their mind.
    stale_result = await session.execute(
        select(ActivationToken).where(
            ActivationToken.company_user_id == company_user_id,  # type: ignore[arg-type]
            ActivationToken.used == False,  # noqa: E712
        )
    )
    stale = stale_result.scalar_one_or_none()
    if stale is not None:
        await session.delete(stale)
        await session.flush()

    result = await session.execute(
        select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
            CompanyProfile.user_id == company_user_id
        )
    )
    company_profile = result.scalar_one()

    # Generate activation token
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_ACTIVATION_TTL_HOURS)
    activation = ActivationToken(
        token=raw_token,
        company_user_id=company_user_id,
        expires_at=expires_at,
    )
    session.add(activation)
    await session.flush()

    activation_url = f"{settings.frontend_base_url}/activate?token={raw_token}"

    # Fetch company signature bytes for PDF
    pdf_bytes: bytes | None = None
    try:
        storage = get_storage_provider()
        if company_profile.agreement_signature_url:
            sig_bytes = await storage.download_file(
                company_profile.agreement_signature_url
            )
            signed_at = company_profile.agreement_signed_at or datetime.now(
                timezone.utc
            )
            pdf_bytes = await generate_signed_contract(
                company_name=company_profile.name or "",
                company_id=company_profile.company_id or "",
                address=company_profile.address or "",
                signed_at=signed_at,
                company_signature_png_bytes=sig_bytes,
            )
    except Exception:
        # PDF generation is best-effort — email is still sent without attachment
        import logging

        logging.getLogger(__name__).exception(
            "Failed to generate signed contract for company %s", company_user_id
        )

    plain = (
        f"שלום,\n\n"
        f"בקשת ההרשמה של {company_profile.name} אושרה.\n\n"
        f"לחצו על הקישור להפעלת החשבון:\n{activation_url}\n\n"
        "בברכה,\nצוות RS Recruiting"
    )
    html = build_approval_html(company_profile.name or "", activation_url)
    attachments = [("חוזה-RS.pdf", pdf_bytes, "application/pdf")] if pdf_bytes else None
    await enqueue_email_task(
        to=user.email,
        subject="בקשת ההרשמה שלכם אושרה – RS Recruiting",
        body=plain,
        html_body=html,
        attachments=attachments,
    )

    return {
        "user": UserRead.model_validate(user),
        "company_profile": CompanyProfileRead.model_validate(company_profile),
    }


async def activate_company(token: str, session: AsyncSession) -> User:
    """Activate a company account using the one-time activation token.

    Raises:
        InvalidActivationTokenError: If the token is invalid, expired, or already used.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(ActivationToken).where(
            ActivationToken.token == token  # type: ignore[arg-type]
        )
    )
    activation = result.scalar_one_or_none()

    if activation is None or activation.used:
        raise InvalidActivationTokenError("הקישור אינו תקף או שכבר נעשה בו שימוש")
    if activation.expires_at.replace(tzinfo=timezone.utc) < now:
        raise InvalidActivationTokenError("פג תוקף הקישור")

    user_result = await session.execute(
        select(User).where(User.id == activation.company_user_id)  # pyright: ignore[reportArgumentType]
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise InvalidActivationTokenError("המשתמש לא נמצא")

    user.is_active = True
    activation.used = True
    return user


async def reject_company(company_user_id: int, session: AsyncSession) -> None:
    """Reject a company registration by deleting the user and company profile.

    Raises:
        CompanyNotFoundError: If company user not found
        CompanyNotPendingError: If already approved or not a COMPANY user
    """
    result = await session.execute(
        select(User).where(User.id == company_user_id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if not user:
        raise CompanyNotFoundError(f"Company user with ID {company_user_id} not found")
    if user.role != UserRole.COMPANY:
        raise CompanyNotPendingError(
            f"User {company_user_id} is not a COMPANY user (role: {user.role})"
        )
    if user.is_active:
        raise CompanyNotPendingError(
            f"Company user {company_user_id} is already approved (active)"
        )

    # Revoke any outstanding activation token (admin may reject after approving).
    token_result = await session.execute(
        select(ActivationToken).where(
            ActivationToken.company_user_id == company_user_id,  # type: ignore[arg-type]
            ActivationToken.used == False,  # noqa: E712
        )
    )
    token_to_revoke = token_result.scalar_one_or_none()
    if token_to_revoke is not None:
        await session.delete(token_to_revoke)
        await session.flush()

    result = await session.execute(
        select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
            CompanyProfile.user_id == company_user_id
        )
    )
    company_profile = result.scalar_one()

    rejected_plain = (
        f"בקשת ההרשמה של '{company_profile.name}' נדחתה. "
        "אם לדעתכם מדובר בטעות, אנא צרו קשר עם support@rs-recruiting.com"
    )
    await enqueue_email_task(
        to=user.email,
        subject="בקשת ההרשמה נדחתה – RS Recruiting",
        body=rejected_plain,
        html_body=build_rejection_html(company_profile.name or ""),
    )

    await session.delete(company_profile)
    await session.flush()
    await session.delete(user)
    await session.flush()


async def list_active_companies(session: AsyncSession) -> list[ActiveCompanyRead]:
    """List all approved (active) companies, newest first."""
    result = await session.execute(
        select(User, CompanyProfile)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.role == UserRole.COMPANY, User.is_active == True)  # noqa: E712
        .order_by(User.created_at.desc())
    )
    return [
        ActiveCompanyRead(
            user=UserRead.model_validate(user),
            company_profile=CompanyProfileRead.model_validate(cp),
        )
        for user, cp in result.all()
    ]


async def delete_active_company(company_user_id: int, session: AsyncSession) -> None:
    """Hard-delete a company and cascade through its jobs and applications.

    Delete order: Applications → Jobs → CompanyProfile → User.

    Raises:
        CompanyNotFoundError: If no COMPANY user with that ID exists
    """
    result = await session.execute(
        select(User, CompanyProfile)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.id == company_user_id, User.role == UserRole.COMPANY)
    )
    row = result.one_or_none()
    if not row:
        raise CompanyNotFoundError(f"Company user with ID {company_user_id} not found")
    user, cp = row

    job_ids_result = await session.execute(
        select(Job.id).where(Job.company_id == cp.id)  # pyright: ignore[reportArgumentType]
    )
    job_ids = [r[0] for r in job_ids_result.all()]
    if job_ids:
        await session.execute(
            delete(Application).where(Application.job_id.in_(job_ids))  # pyright: ignore[reportAttributeAccessIssue]
        )
        await session.execute(
            delete(Job).where(Job.id.in_(job_ids))  # pyright: ignore[reportAttributeAccessIssue]
        )
        await session.flush()

    await session.delete(cp)
    await session.flush()
    await session.delete(user)
    await session.flush()
