"""FastAPI dependencies for authentication and authorization."""

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.security import (
    decode_access_token,
    is_access_token_blacklisted,
)
from src.enums import UserRole
from src.models import CompanyProfile, User
from src.services.exceptions import RedisUnavailableError

security = HTTPBearer()


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Decode and validate an access token, returning the payload.

    Raises 401 if the token is invalid or blacklisted.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    try:
        if jti and await is_access_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except RedisUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        )

    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(get_token_payload),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get current authenticated user from the validated JWT payload."""
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(
        select(User).where(User.id == user_id_int)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current authenticated admin user.

    This dependency ensures the current user has ADMIN role.
    Use this for admin-only endpoints.

    Args:
        current_user: Current authenticated user (from get_current_user)

    Returns:
        User with ADMIN role

    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_company(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[User, CompanyProfile]:
    """Get current authenticated company user and their company profile.

    This dependency ensures the current user has COMPANY role and is active.
    Returns both the user and their company profile for convenience.

    Args:
        current_user: Current authenticated user (from get_current_user)
        session: Database session

    Returns:
        Tuple of (User, CompanyProfile)

    Raises:
        HTTPException: If user is not a company or company profile not found
    """
    if current_user.role != UserRole.COMPANY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company access required",
        )

    # Get company profile
    result = await session.execute(
        select(CompanyProfile).where(
            CompanyProfile.user_id == current_user.id  # type: ignore[comparison-overlap]
        )
    )
    company_profile = result.scalar_one_or_none()
    if not company_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    # Validate company profile has an ID
    if company_profile.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Company profile ID is missing",
        )

    return (current_user, company_profile)


def client_ip(request: Request) -> str | None:
    """Best-effort client IP, honoring X-Forwarded-For from a trusted proxy.

    Returns the leftmost entry of `X-Forwarded-For` if present (most trustworthy
    when terminating TLS at a single reverse proxy), otherwise the direct peer
    address. None if neither is available.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or None
    return request.client.host if request.client else None
