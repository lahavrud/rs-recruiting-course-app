"""Admin service layer for company management."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.models import Application, CompanyProfile, Job, User
from src.schemas import ActiveCompanyRead, CompanyProfileRead, UserRead
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
)


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
    """Approve a company registration by activating the user.

    Raises:
        CompanyNotFoundError: If company user not found
        CompanyNotPendingError: If company is already approved or not a COMPANY user
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

    user.is_active = True
    await session.flush()

    result = await session.execute(
        select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
            CompanyProfile.user_id == company_user_id
        )
    )
    company_profile = result.scalar_one()

    approved_body = (
        f"Your company registration for '{company_profile.name}' has been approved. "
        "You can now log in and start posting jobs."
    )
    await enqueue_email_task(
        to=user.email,
        subject="Company Registration Approved",
        body=approved_body,
    )

    return {
        "user": UserRead.model_validate(user),
        "company_profile": CompanyProfileRead.model_validate(company_profile),
    }


async def reject_company(company_user_id: int, session: AsyncSession) -> None:
    """Reject a company registration by deleting the user and company profile.

    Raises:
        CompanyNotFoundError: If company user not found
        CompanyNotPendingError: If company is already approved or not a COMPANY user
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

    result = await session.execute(
        select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
            CompanyProfile.user_id == company_user_id
        )
    )
    company_profile = result.scalar_one()

    rejected_body = (
        f"Your company registration for '{company_profile.name}' has been rejected. "
        "If you believe this is an error, please contact support."
    )
    await enqueue_email_task(
        to=user.email,
        subject="Company Registration Rejected",
        body=rejected_body,
    )

    await session.delete(company_profile)
    await session.flush()
    await session.delete(user)


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
