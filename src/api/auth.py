"""Authentication endpoints — login, refresh, logout."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_token_payload
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.transactions import transactional
from src.schemas import AccessTokenResponse, LoginRequest
from src.services.auth import (
    authenticate_user,
    create_user_tokens,
    logout_user,
    refresh_user_tokens,
)
from src.services.exceptions import (
    AccountLockedError,
    InactiveUserError,
    InvalidCredentialsError,
    PendingActivationError,
    PendingApprovalError,
    RedisUnavailableError,
)

limiter = get_limiter()
router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_REFRESH_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, matches RefreshToken lifetime in config


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=_REFRESH_MAX_AGE,
        path="/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/auth",
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
    )


@router.post("/login", response_model=AccessTokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> AccessTokenResponse:
    """Login — access token in body, refresh token in HttpOnly cookie."""
    try:
        user = await authenticate_user(login_data.email, login_data.password, session)
    except (
        InvalidCredentialsError,
        InactiveUserError,
        PendingApprovalError,
        PendingActivationError,
        AccountLockedError,
    ) as e:
        raise service_exception_to_http(e) from e

    async with transactional(session):
        access_token, refresh_token = await create_user_tokens(user, session)

    _set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AccessTokenResponse:
    """Exchange the refresh-token cookie for a new access token + rotated cookie."""
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )
    try:
        async with transactional(session):
            access_token, new_refresh_token = await refresh_user_tokens(
                raw_refresh, session
            )
    except InvalidCredentialsError as e:
        raise service_exception_to_http(e) from e

    _set_refresh_cookie(response, new_refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    payload: dict = Depends(get_token_payload),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke the current session (blacklist JTI, revoke refresh token cookie)."""
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        raw_refresh = request.cookies.get(_REFRESH_COOKIE)
        try:
            async with transactional(session):
                await logout_user(jti, int(exp), raw_refresh, session)
        except RedisUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable",
            )
    _clear_refresh_cookie(response)
