"""Job write endpoints (POST, PUT, DELETE operations)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_company
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.transactions import transactional
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


@router.post("/", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job_posting(
    job_data: JobCreate,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Create a new job posting (PENDING_APPROVAL). Requires company auth."""
    _, company_profile = current_company
    try:
        async with transactional(session):
            return await create_job(job_data, company_profile.id, session)
    except (CompanyNotFoundError, JobNotFoundError) as e:
        raise service_exception_to_http(e) from e


@router.put("/{job_id}", response_model=JobRead, status_code=status.HTTP_200_OK)
async def update_job_posting(
    job_id: int,
    job_data: JobUpdate,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Update a job posting. Company owner only; PENDING_APPROVAL or PUBLISHED."""
    _, company_profile = current_company
    try:
        async with transactional(session):
            return await update_job(job_id, job_data, company_profile.id, session)
    except (JobNotFoundError, JobNotOwnedByCompanyError, JobCannotBeUpdatedError) as e:
        raise service_exception_to_http(e) from e


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_posting(
    job_id: int,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a job posting. Company owner only; PENDING_APPROVAL only."""
    _, company_profile = current_company
    try:
        async with transactional(session):
            await delete_job(job_id, company_profile.id, session)
    except (JobNotFoundError, JobNotOwnedByCompanyError, JobCannotBeDeletedError) as e:
        raise service_exception_to_http(e) from e
