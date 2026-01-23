"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.security import decode_access_token
from src.enums import UserRole
from src.models import CompanyProfile, User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get current authenticated user from JWT token.

    This dependency extracts and validates the JWT token from the Authorization header,
    then fetches the corresponding User from the database.

    Args:
        credentials: HTTPBearer credentials containing the JWT token
        session: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException: If token is invalid, user not found, or user is inactive
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Convert user_id to int, handle invalid types
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
