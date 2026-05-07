"""Admin endpoints for direct job CRUD.

Separate from `admin_jobs.py` (approval workflow) — these endpoints let
an admin manage any job in any status, including creating jobs directly
on behalf of a company.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, MAX_LIMIT, CursorPage
from src.core.infrastructure.transactions import transactional
from src.enums import JobStatus
from src.models import User
from src.schemas import JobAdminCreate, JobRead, JobUpdate
from src.services.exceptions import (
    CompanyNotFoundError,
    InvalidCursorError,
    JobNotFoundError,
)
from src.services.jobs_admin_crud import (
    admin_create_job,
    delete_job,
    get_job,
    list_jobs,
    update_job,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/jobs", response_model=CursorPage[JobRead])
async def get_jobs(
    status: JobStatus | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[JobRead]:
    """List jobs across all statuses, newest first, cursor-paginated."""
    try:
        return await list_jobs(session, status=status, cursor=cursor, limit=limit)
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobAdminCreate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Create a job directly under an existing company profile.

    Status defaults to PUBLISHED — admin-created jobs skip the approval flow.
    """
    try:
        async with transactional(session):
            return await admin_create_job(data, session)
    except CompanyNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.get("/jobs/{job_id}", response_model=JobRead)
async def get_job_endpoint(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Fetch a single job by id, regardless of status."""
    try:
        return await get_job(job_id, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.put("/jobs/{job_id}", response_model=JobRead)
async def update_job_endpoint(
    job_id: int,
    data: JobUpdate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Partially update any field on a job at any status."""
    try:
        async with transactional(session):
            return await update_job(job_id, data, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_endpoint(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a job and cascade through its applications."""
    try:
        async with transactional(session):
            await delete_job(job_id, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e
