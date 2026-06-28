"""Public endpoints (no authentication required)."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import get_current_user_optional
from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.pagination import DEFAULT_LIMIT, CursorPage
from rs_shared.models import User
from rs_shared.schemas import JobPublicRead
from rs_shared.services.exceptions import JobNotFoundError
from rs_shared.services.public.jobs import get_published_job, list_published_jobs

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/jobs", response_model=CursorPage[JobPublicRead])
async def get_public_jobs(
    response: Response,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    session: AsyncSession = Depends(get_session),
) -> CursorPage[JobPublicRead]:
    """List published jobs for the public job board, cursor-paginated."""
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return await list_published_jobs(session, cursor=cursor, limit=limit)


@router.get(
    "/jobs/{job_id}",
    response_model=JobPublicRead,
)
async def get_public_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> JobPublicRead:
    """Get a specific published job posting.

    No authentication required. Only returns jobs with PUBLISHED status.
    When called with a candidate JWT the response includes ``my_application``
    summarizing the candidate's own non-WITHDRAWN application for this job.
    """
    try:
        return await get_published_job(job_id, session, current_user=current_user)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e
