"""Admin endpoints for company approval workflow."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.models import User
from src.schemas import ApprovedCompanyRead, PendingCompanyRead
from src.services.admin import approve_company, list_pending_companies, reject_company
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/companies/pending",
    response_model=list[PendingCompanyRead],
    status_code=status.HTTP_200_OK,
)
async def get_pending_companies(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[PendingCompanyRead]:
    """List all pending company registrations.

    Returns inactive COMPANY users with their associated company profiles.
    Requires admin authentication.

    Args:
        current_admin: Current authenticated admin user (from dependency)
        session: Database session

    Returns:
        List of pending company registrations
    """
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
    """Approve a company registration.

    Activates the company user (sets is_active=True) and sends email notification.
    Requires admin authentication.

    Args:
        company_user_id: ID of the company user to approve
        current_admin: Current authenticated admin user (from dependency)
        session: Database session

    Returns:
        Approved company with user and profile information

    Raises:
        HTTPException: If company not found or not pending
    """
    try:
        result = await approve_company(company_user_id, session)
        await session.commit()
        return ApprovedCompanyRead.model_validate(result)
    except CompanyNotFoundError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CompanyNotPendingError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
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
    """Reject a company registration.

    Deletes the company user and profile, and sends email notification.
    Requires admin authentication.

    Args:
        company_user_id: ID of the company user to reject
        current_admin: Current authenticated admin user (from dependency)
        session: Database session

    Raises:
        HTTPException: If company not found or not pending
    """
    try:
        await reject_company(company_user_id, session)
        await session.commit()
    except CompanyNotFoundError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CompanyNotPendingError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception:
        await session.rollback()
        raise
