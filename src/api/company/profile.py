"""Company self-service endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_company
from src.core.services.storage import get_storage_provider
from src.models import CompanyProfile, User
from src.schemas import CompanyDataExport
from src.services.company.profile import export_company_data

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/me/export", response_model=CompanyDataExport)
async def export_my_company_data(
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> CompanyDataExport:
    """Right-to-data-portability export for the authenticated company."""
    user, profile = current_company
    return await export_company_data(user, profile, session, get_storage_provider())
