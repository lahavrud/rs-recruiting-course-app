"""Authentication endpoints — login, refresh, logout."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip, get_token_payload
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.transactions import transactional
from src.enums import UserRole
from src.schemas import AccessTokenResponse, LoginRequest
from src.services.auth.session import (
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
)
from src.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)
limiter = get_limiter()
router = APIRouter(prefix="/auth", tags=["auth"])


_REFRESH_COOKIE = "refresh_token"
_REFRESH_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, matches RefreshToken lifetime in config


def _refresh_cookie_secure() -> bool:
    """Default the refresh cookie's ``Secure`` flag to True everywhere
    except the test suite (issue #650).

    Was ``environment == "production"`` — which left development and any
    future staging environment shipping the cookie over plain HTTP.
    httpx in our tests hits the API at ``http://test/``, which isn't
    localhost from the cookie-store's perspective, so secure cookies are
    silently dropped — ``settings.testing`` is the documented opt-out
    for that one consumer.
    """
    return not settings.testing


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=_refresh_cookie_secure(),
        samesite="strict",
        max_age=_REFRESH_MAX_AGE,
        path="/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/auth",
        httponly=True,
        secure=_refresh_cookie_secure(),
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
    ip = client_ip(request)
    try:
        user = await authenticate_user(
            login_data.email, login_data.password, session, client_ip=ip
        )
    except (
        InvalidCredentialsError,
        InactiveUserError,
        PendingApprovalError,
        PendingActivationError,
        AccountLockedError,
    ) as e:
        raise service_exception_to_http(e) from e

    logger.info(
        "login_success",
        extra={"user_id": str(user.id), "role": user.role.value, "ip": ip},
    )

    async with transactional(session):
        access_token, refresh_token = await create_user_tokens(user, session)
        if user.role == UserRole.ADMIN:
            await record_audit_event(
                session,
                actor_user_id=user.id,
                action="admin_login",
                target_type="user",
                target_id=user.id,
            )

    _set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/refresh", response_model=AccessTokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AccessTokenResponse:
    """Exchange the refresh-token cookie for a new access token + rotated cookie.

    Rate-limited (30/minute per IP) — normal browser sessions only need a
    handful of refreshes per minute even with parallel tabs, but a stolen
    refresh token replayed in a loop was previously unthrottled
    (issue #643).
    """
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
    """Revoke the current session: delete the refresh-token row."""
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    async with transactional(session):
        await logout_user(raw_refresh, session)
    _clear_refresh_cookie(response)
