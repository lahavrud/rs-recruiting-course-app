"""Admin endpoint for querying the audit log."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import get_current_admin
from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    CursorPage,
)
from rs_shared.models import User
from rs_shared.schemas import AuditLogRead
from rs_shared.services.exceptions import InvalidCursorError
from rs_shared.services.utils.audit import list_audit_events

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
