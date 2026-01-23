"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.security import create_access_token
from src.schemas import LoginRequest, TokenResponse, UserCreate, UserWithCompanyRead
from src.services.auth import authenticate_user, register_company_user
from src.services.exceptions import (
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
)

limiter = get_limiter()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserWithCompanyRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/hour")
async def register(
    request: Request,
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserWithCompanyRead:
    """Register a new company user.

    Creates a User with COMPANY role and associated CompanyProfile.
    User is inactive until Admin approves (is_active=False).
    """
    try:
        result = await register_company_user(user_data, session)
        await session.commit()
        return result
    except EmailAlreadyExistsError as e:
        await session.rollback()
        raise service_exception_to_http(e) from e
    except sqlalchemy_exc.IntegrityError as e:
        await session.rollback()
        # Check if it's a unique constraint violation on email
        error_str = str(e.orig) if e.orig else str(e)
        if "email" in error_str.lower() or "unique" in error_str.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email '{user_data.email}' already exists.",
            ) from e
        # Re-raise for other integrity errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred during registration",
        ) from e
    except Exception:
        await session.rollback()
        raise


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Login and receive JWT access token.

    Validates email and password, returns JWT token if credentials are correct.
    """
    try:
        user = await authenticate_user(login_data.email, login_data.password, session)
    except (InvalidCredentialsError, InactiveUserError) as e:
        raise service_exception_to_http(e) from e

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )

    return TokenResponse(access_token=access_token)
