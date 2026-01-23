"""Job read endpoints (GET operations)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_company
from src.core.infrastructure.error_handling import service_exception_to_http
from src.models import CompanyProfile, User
from src.schemas import JobRead
from src.services.exceptions import JobNotFoundError
from src.services.jobs import get_job, list_company_jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get(
    "/",
    response_model=list[JobRead],
)
async def get_company_jobs(
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> list[JobRead]:
    """List all jobs for the current company.

    Requires company authentication.

    Args:
        current_company: Current authenticated company user and profile
        session: Database session

    Returns:
        List of jobs as JobRead schemas
    """
    user, company_profile = current_company
    jobs = await list_company_jobs(company_profile.id, session)
    return jobs


@router.get(
    "/{job_id}",
    response_model=JobRead,
)
async def get_job_posting(
    job_id: int,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Get a specific job posting.

    Only returns jobs owned by the current company.
    Requires company authentication.

    Args:
        job_id: ID of the job to retrieve
        current_company: Current authenticated company user and profile
        session: Database session

    Returns:
        Job as JobRead schema

    Raises:
        HTTPException: If job not found or not owned by company
    """
    user, company_profile = current_company
    try:
        job = await get_job(job_id, session)
        # Verify ownership
        if job.company_id != company_profile.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )
        return job
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e
