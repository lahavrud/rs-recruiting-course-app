"""Public endpoints (no authentication required)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, CursorPage
from src.schemas import JobPublicRead
from src.services.exceptions import JobNotFoundError
from src.services.jobs_public import get_published_job, list_published_jobs

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/jobs", response_model=CursorPage[JobPublicRead])
async def get_public_jobs(
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    session: AsyncSession = Depends(get_session),
) -> CursorPage[JobPublicRead]:
    """List published jobs for the public job board, cursor-paginated."""
    return await list_published_jobs(session, cursor=cursor, limit=limit)


@router.get(
    "/jobs/{job_id}",
    response_model=JobPublicRead,
)
async def get_public_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> JobPublicRead:
    """Get a specific published job posting.

    No authentication required. Only returns jobs with PUBLISHED status.

    Args:
        job_id: ID of the job to retrieve
        session: Database session

    Returns:
        Job as JobPublicRead schema

    Raises:
        HTTPException: If job not found or not published
    """
    try:
        job = await get_published_job(job_id, session)
        return job
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e
