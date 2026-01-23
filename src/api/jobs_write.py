"""Job write endpoints (POST, PUT, DELETE operations)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_company
from src.core.infrastructure.error_handling import service_exception_to_http
from src.models import CompanyProfile, User
from src.schemas import JobCreate, JobRead, JobUpdate
from src.services.exceptions import (
    CompanyNotFoundError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
)
from src.services.jobs import create_job, delete_job, update_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post(
    "/",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_posting(
    job_data: JobCreate,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Create a new job posting.

    Jobs are created with PENDING_APPROVAL status and require admin approval.
    Requires company authentication.

    Args:
        job_data: Job creation data
        current_company: Current authenticated company user and profile
        session: Database session

    Returns:
        Created job as JobRead schema

    Raises:
        HTTPException: If company not found
    """
    user, company_profile = current_company
    try:
        result = await create_job(job_data, company_profile.id, session)
        await session.commit()
        return result
    except (CompanyNotFoundError, JobNotFoundError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.put(
    "/{job_id}",
    response_model=JobRead,
    status_code=status.HTTP_200_OK,
)
async def update_job_posting(
    job_id: int,
    job_data: JobUpdate,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Update a job posting.

    Only the company owner can update their jobs.
    Jobs can only be updated if status is PENDING_APPROVAL or PUBLISHED.
    Requires company authentication.

    Args:
        job_id: ID of the job to update
        job_data: Job update data
        current_company: Current authenticated company user and profile
        session: Database session

    Returns:
        Updated job as JobRead schema

    Raises:
        HTTPException: If job not found, not owned by company, or cannot be updated
    """
    user, company_profile = current_company
    try:
        result = await update_job(job_id, job_data, company_profile.id, session)
        await session.commit()
        return result
    except (JobNotFoundError, JobNotOwnedByCompanyError, JobCannotBeUpdatedError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_job_posting(
    job_id: int,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a job posting.

    Only the company owner can delete their jobs.
    Jobs can only be deleted if status is PENDING_APPROVAL.
    Requires company authentication.

    Args:
        job_id: ID of the job to delete
        current_company: Current authenticated company user and profile
        session: Database session

    Raises:
        HTTPException: If job not found, not owned by company, or cannot be deleted
    """
    user, company_profile = current_company
    try:
        await delete_job(job_id, company_profile.id, session)
        await session.commit()
    except (JobNotFoundError, JobNotOwnedByCompanyError, JobCannotBeDeletedError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise
