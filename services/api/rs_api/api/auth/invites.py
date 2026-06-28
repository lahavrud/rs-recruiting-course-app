"""Public invite token endpoints (no authentication required)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.invite_tokens import validate_invite_token
from rs_shared.schemas import InviteMetadataPublic
from rs_shared.services.auth.session import get_invite_by_hash
from rs_shared.services.exceptions import InvalidInviteTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/invite/{token}", response_model=InviteMetadataPublic)
async def get_invite_metadata(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> InviteMetadataPublic:
    """Return public pre-fill data for a valid invite token."""
    try:
        await validate_invite_token(token, session)
    except InvalidInviteTokenError as e:
        raise service_exception_to_http(e) from e
    record = await get_invite_by_hash(token, session)
    if record is None:
        raise service_exception_to_http(
            InvalidInviteTokenError(f"Invite token not found: {token}")
        )
    return InviteMetadataPublic.model_validate(record)
