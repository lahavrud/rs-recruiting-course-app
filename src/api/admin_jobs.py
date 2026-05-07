"""Admin endpoints for job approval workflow."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.transactions import transactional
from src.models import User
from src.schemas import JobContactEmailRequest, JobRead
from src.services.exceptions import JobNotFoundError, JobNotPendingError
from src.services.jobs_admin import (
    approve_job,
    contact_job,
    list_pending_jobs,
    reject_job,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/jobs/pending", response_model=list[JobRead])
async def get_pending_jobs(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[JobRead]:
    """List all PENDING_APPROVAL job postings."""
    return await list_pending_jobs(session)


@router.post(
    "/jobs/{job_id}/approve", response_model=JobRead, status_code=status.HTTP_200_OK
)
async def approve_job_posting(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Approve a pending job; sets status to PUBLISHED and notifies the company."""
    try:
        async with transactional(session):
            return await approve_job(job_id, session)
    except (JobNotFoundError, JobNotPendingError) as e:
        raise service_exception_to_http(e) from e


@router.post("/jobs/{job_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_job_posting(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Reject a pending job; sets status to CLOSED and notifies the company."""
    try:
        async with transactional(session):
            await reject_job(job_id, session)
    except (JobNotFoundError, JobNotPendingError) as e:
        raise service_exception_to_http(e) from e


@router.post("/jobs/{job_id}/contact", status_code=status.HTTP_204_NO_CONTENT)
async def contact_job_posting(
    job_id: int,
    body: JobContactEmailRequest,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Send a contextual email to the company that owns a job posting."""
    try:
        await contact_job(job_id, body.admin_note, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e
