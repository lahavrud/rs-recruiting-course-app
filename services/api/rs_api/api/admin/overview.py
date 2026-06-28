"""Admin overview endpoint — aggregated counts for inbox and stats."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import get_current_admin
from rs_shared.core.infrastructure.database import get_session
from rs_shared.models import User
from rs_shared.schemas.admin_overview import AdminOverviewRead
from rs_shared.services.admin.overview import get_overview

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewRead)
async def get_admin_overview(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminOverviewRead:
    """Aggregated counts for the admin dashboard inbox and stats panels."""
    data = await get_overview(session)
    return AdminOverviewRead.model_validate(data)
