"""Admin endpoint for querying the audit log."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, MAX_LIMIT, CursorPage
from src.models import User
from src.schemas import AuditLogRead
from src.services.exceptions import InvalidCursorError
from src.services.utils.audit import list_audit_events

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-log", response_model=CursorPage[AuditLogRead])
async def get_audit_log(
    target_type: str | None = None,
    actor_user_id: int | None = None,
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[AuditLogRead]:
    """List audit events, newest first, cursor-paginated."""
    try:
        return await list_audit_events(
            session,
            target_type=target_type,
            actor_user_id=actor_user_id,
            from_dt=from_dt,
            to_dt=to_dt,
            cursor=cursor,
            limit=limit,
        )
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc
