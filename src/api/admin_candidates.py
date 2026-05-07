"""Admin endpoints for candidate management."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, MAX_LIMIT, CursorPage
from src.core.infrastructure.transactions import transactional
from src.models import User
from src.schemas import CandidateProfileRead, CandidateProfileUpdate
from src.services.candidates_admin import (
    delete_candidate,
    get_candidate,
    list_candidates,
    update_candidate,
)
from src.services.exceptions import CandidateNotFoundError, InvalidCursorError

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/candidates", response_model=CursorPage[CandidateProfileRead])
async def get_candidates(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[CandidateProfileRead]:
    """List candidate profiles, newest first, cursor-paginated."""
    try:
        return await list_candidates(session, cursor=cursor, limit=limit)
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.get("/candidates/{candidate_id}", response_model=CandidateProfileRead)
async def get_candidate_endpoint(
    candidate_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileRead:
    """Fetch a single candidate profile by id."""
    try:
        return await get_candidate(candidate_id, session)
    except CandidateNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.put("/candidates/{candidate_id}", response_model=CandidateProfileRead)
async def update_candidate_endpoint(
    candidate_id: int,
    data: CandidateProfileUpdate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileRead:
    """Partially update a candidate profile."""
    try:
        async with transactional(session):
            return await update_candidate(candidate_id, data, session)
    except CandidateNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_endpoint(
    candidate_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a candidate and cascade through their applications."""
    try:
        async with transactional(session):
            await delete_candidate(candidate_id, session)
    except CandidateNotFoundError as e:
        raise service_exception_to_http(e) from e
