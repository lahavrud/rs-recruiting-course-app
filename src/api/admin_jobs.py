"""Admin endpoints for job approval workflow."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.models import User
from src.schemas import JobRead
from src.services.exceptions import JobNotFoundError, JobNotPendingError
from src.services.jobs_admin import approve_job, list_pending_jobs, reject_job

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/jobs/pending",
    response_model=list[JobRead],
)
async def get_pending_jobs(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[JobRead]:
    """List all pending job postings.

    Returns jobs with PENDING_APPROVAL status.
    Requires admin authentication.

    Args:
        current_admin: Current authenticated admin user (from dependency)
        session: Database session

    Returns:
        List of pending job postings
    """
    jobs = await list_pending_jobs(session)
    return jobs


@router.post(
    "/jobs/{job_id}/approve",
    response_model=JobRead,
    status_code=status.HTTP_200_OK,
)
async def approve_job_posting(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Approve a job posting.

    Changes job status to PUBLISHED and sends email notification to the company.
    Requires admin authentication.

    Args:
        job_id: ID of the job to approve
        current_admin: Current authenticated admin user (from dependency)
        session: Database session

    Returns:
        Approved job as JobRead schema

    Raises:
        HTTPException: If job not found or not pending
    """
    try:
        result = await approve_job(job_id, session)
        await session.commit()
        return result
    except (JobNotFoundError, JobNotPendingError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise


@router.post(
    "/jobs/{job_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reject_job_posting(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Reject a job posting.

    Changes job status to CLOSED and sends email notification to the company.
    Requires admin authentication.

    Args:
        job_id: ID of the job to reject
        current_admin: Current authenticated admin user (from dependency)
        session: Database session

    Raises:
        HTTPException: If job not found or not pending
    """
    try:
        await reject_job(job_id, session)
        await session.commit()
    except (JobNotFoundError, JobNotPendingError) as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except Exception:
        await session.rollback()
        raise
