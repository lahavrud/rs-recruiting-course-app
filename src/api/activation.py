"""Company account activation endpoint."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.transactions import transactional
from src.services.activation import activate_company
from src.services.exceptions import InvalidActivationTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/activate", status_code=status.HTTP_200_OK)
async def activate(
    token: str = Query(
        ..., description="One-time activation token from approval email"
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Activate a company account using the one-time token from the approval email."""
    try:
        async with transactional(session):
            await activate_company(token, session)
    except InvalidActivationTokenError as e:
        raise service_exception_to_http(e) from e
    return {"message": "החשבון הופעל בהצלחה"}
