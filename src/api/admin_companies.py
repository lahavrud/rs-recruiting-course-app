"""Admin endpoints for company approval workflow."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.models import User
from src.schemas import (
    ActiveCompanyRead,
    ApprovedCompanyRead,
    InviteTokenCreate,
    InviteTokenRead,
    PendingCompanyRead,
)
from src.services.admin_companies import (
    approve_company,
    delete_active_company,
    list_active_companies,
    list_pending_companies,
    reject_company,
)
from src.services.admin_invites import (
    create_invite,
    list_invites,
    resend_invite,
    revoke_invite,
)
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
    EmailAlreadyExistsError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/companies/invite",
    response_model=InviteTokenRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_invite(
    data: InviteTokenCreate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> InviteTokenRead:
    """Generate a single-use invite token and send it via email."""
    assert current_admin.id is not None
    try:
        result = await create_invite(current_admin.id, data, session)
        await session.commit()
        return result
    except (InvitePendingForEmailError, EmailAlreadyExistsError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/companies/invites",
    response_model=list[InviteTokenRead],
)
async def get_company_invites(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[InviteTokenRead]:
    """List all invite tokens with their current status."""
    result = await list_invites(session)
    await session.commit()
    return result


@router.delete(
    "/companies/invites/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_company_invite(
    token_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke a pending invite token."""
    try:
        await revoke_invite(token_id, session)
        await session.commit()
    except (InviteNotFoundError, InviteAlreadyRevokedError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.post(
    "/companies/invites/{token_id}/resend",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def resend_company_invite(
    token_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Regenerate and resend an invite email for an existing invite record."""
    try:
        await resend_invite(token_id, session)
        await session.commit()
    except (InviteNotFoundError, InviteAlreadyRevokedError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/companies",
    response_model=list[ActiveCompanyRead],
)
async def get_active_companies(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ActiveCompanyRead]:
    """List all active companies."""
    return await list_active_companies(session)


@router.delete(
    "/companies/{company_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_company(
    company_user_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a company and all its jobs and applications."""
    try:
        await delete_active_company(company_user_id, session)
        await session.commit()
    except CompanyNotFoundError as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/companies/pending",
    response_model=list[PendingCompanyRead],
)
async def get_pending_companies(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[PendingCompanyRead]:
    """List all pending company registrations."""
    companies = await list_pending_companies(session)
    return [PendingCompanyRead.model_validate(c) for c in companies]


@router.post(
    "/companies/{company_user_id}/approve",
    response_model=ApprovedCompanyRead,
    status_code=status.HTTP_200_OK,
)
async def approve_company_registration(
    company_user_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> ApprovedCompanyRead:
    """Approve a company registration."""
    try:
        result = await approve_company(company_user_id, session)
        await session.commit()
        return ApprovedCompanyRead.model_validate(result)
    except (CompanyNotFoundError, CompanyNotPendingError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.post(
    "/companies/{company_user_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reject_company_registration(
    company_user_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Reject a company registration."""
    try:
        await reject_company(company_user_id, session)
        await session.commit()
    except (CompanyNotFoundError, CompanyNotPendingError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise
