"""Admin service layer for company management."""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.services.storage import get_storage_provider
from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.models import ActivationToken, Application, CompanyProfile, Job, User
from src.schemas import (
    ActiveCompanyRead,
    CompanyProfileRead,
    PendingCompanyRead,
    UserRead,
)
from src.services.admin_company_approval import approve_company  # re-exported
from src.services.audit import record_audit_event
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
)
from src.templates.email import build_rejection_html

__all__ = [
    "approve_company",
    "delete_active_company",
    "get_all_admin_emails",
    "list_active_companies",
    "list_pending_companies",
    "reject_company",
]

_logger = logging.getLogger(__name__)


async def _delete_company_files(company_profile: CompanyProfile) -> None:
    """Delete all S3 files associated with a company profile (best-effort)."""
    storage = get_storage_provider()
    for key in [
        company_profile.logo_url,
        company_profile.agreement_signature_url,
        company_profile.contract_pdf_url,
    ]:
        if key:
            try:
                await storage.delete_file(key)
            except Exception:
                _logger.exception("Failed to delete storage file %s", key)


async def get_all_admin_emails(session: AsyncSession) -> list[str]:
    """Get email addresses of all active admin users."""
    result = await session.execute(
        select(User.email).where(  # pyright: ignore[reportArgumentType]
            User.role == UserRole.ADMIN,
            User.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def list_pending_companies(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[PendingCompanyRead]:
    """One page of pending companies (inactive COMPANY users), newest first."""
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(User, CompanyProfile)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)
        .where(User.role == UserRole.COMPANY, User.is_active == False),  # noqa: E712
        sort_col=User.created_at,  # pyright: ignore[reportArgumentType]
        id_col=User.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).all())
    return build_cursor_page(
        rows,
        serializer=lambda row: PendingCompanyRead(
            user=UserRead.model_validate(row[0]),
            company_profile=CompanyProfileRead.model_validate(row[1]),
        ),
        cursor_key=lambda row: (row[0].created_at, row[0].id),
        limit=page_size,
    )


async def reject_company(
    company_user_id: int,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> None:
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

    _rejection_email = user.email
    _company_name_for_email = company_profile.name or ""
    _rejected_plain = (
        f"בקשת ההרשמה של '{_company_name_for_email}' נדחתה. "
        "אם לדעתכם מדובר בטעות, אנא צרו קשר עם support@rs-recruiting.com"
    )
    _rejection_html = build_rejection_html(_company_name_for_email)
    defer_after_commit(
        lambda: enqueue_email_task(
            to=_rejection_email,
            subject="בקשת ההרשמה נדחתה – RS Recruiting",
            body=_rejected_plain,
            html_body=_rejection_html,
        )
    )

    await _delete_company_files(company_profile)

    rejected_target_id = company_profile.id

    await session.delete(company_profile)
    await session.flush()
    await session.delete(user)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="company.reject",
        target_type="CompanyProfile",
        target_id=rejected_target_id,
        ip_address=ip_address,
    )


async def list_active_companies(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[ActiveCompanyRead]:
    """One page of approved (active) companies, newest first."""
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(User, CompanyProfile)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)
        .where(User.role == UserRole.COMPANY, User.is_active == True),  # noqa: E712
        sort_col=User.created_at,  # pyright: ignore[reportArgumentType]
        id_col=User.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).all())
    return build_cursor_page(
        rows,
        serializer=lambda row: ActiveCompanyRead(
            user=UserRead.model_validate(row[0]),
            company_profile=CompanyProfileRead.model_validate(row[1]),
        ),
        cursor_key=lambda row: (row[0].created_at, row[0].id),
        limit=page_size,
    )


async def delete_active_company(
    company_user_id: int,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> None:
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
    cp_id = cp.id

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

    await _delete_company_files(cp)

    await session.delete(cp)
    await session.flush()
    await session.delete(user)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="company.delete",
        target_type="CompanyProfile",
        target_id=cp_id,
        ip_address=ip_address,
    )
