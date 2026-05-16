"""Authentication endpoints."""

import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip, get_token_payload
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.invite_tokens import (
    consume_invite_token,
    validate_invite_token,
)
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.transactions import transactional
from src.schemas import (
    CompanyProfileCreate,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserWithCompanyRead,
)
from src.services.auth import (
    authenticate_user,
    create_user_tokens,
    logout_user,
    mark_invite_used,
    refresh_user_tokens,
)
from src.services.auth_register import register_company_user
from src.services.exceptions import (
    AccountLockedError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidInviteTokenError,
    PendingActivationError,
    PendingApprovalError,
    RedisUnavailableError,
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
    token: str = Query(..., description="Single-use invite token issued by an admin"),
    email: str = Form(...),
    password: str = Form(...),
    company_name: str = Form(...),
    company_id: str = Form(...),
    address: str = Form(...),
    contact_first_name: str = Form(...),
    contact_last_name: str = Form(...),
    contact_mobile_phone: str = Form(...),
    contact_landline_phone: str | None = Form(None),
    agreement_signature: str = Form(...),
    privacy_accepted: bool = Form(...),
    terms_accepted: bool = Form(...),
    logo: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UserWithCompanyRead:
    """Register a new company user with a valid single-use invite token."""
    if not privacy_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="יש לאשר את מדיניות הפרטיות",
        )
    if not terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="יש לאשר את תנאי השימוש",
        )
    try:
        profile_data = CompanyProfileCreate(
            name=company_name,
            company_id=company_id,
            address=address,
            contact_first_name=contact_first_name,
            contact_last_name=contact_last_name,
            contact_mobile_phone=contact_mobile_phone,
            contact_landline_phone=contact_landline_phone,
        )
        user_create = UserCreate(
            email=email, password=password, company_profile=profile_data
        )
    except PydanticValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(exc.json()),
        ) from exc

    logo_content = await logo.read()
    logo_filename = logo.filename or "logo"
    logo_content_type = logo.content_type

    try:
        async with transactional(session):
            await validate_invite_token(token)
            result = await register_company_user(
                user_create,
                session,
                logo_content,
                logo_filename,
                logo_content_type,
                agreement_signature,
                privacy_accepted=privacy_accepted,
                terms_accepted=terms_accepted,
                acceptance_ip=client_ip(request),
                acceptance_user_agent=request.headers.get("user-agent"),
            )
            await mark_invite_used(token, session)
    except (InvalidInviteTokenError, EmailAlreadyExistsError) as e:
        raise service_exception_to_http(e) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except sqlalchemy_exc.IntegrityError as e:
        pgcode = getattr(e.orig, "pgcode", None)
        if pgcode == "23505":  # unique_violation
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{email}' already exists.",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred during registration",
        ) from e

    await consume_invite_token(token)
    return result


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Login and receive JWT access + refresh tokens."""
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

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        async with transactional(session):
            access_token, new_refresh_token = await refresh_user_tokens(
                body.refresh_token, session
            )
    except InvalidCredentialsError as e:
        raise service_exception_to_http(e) from e

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest | None = None,
    payload: dict = Depends(get_token_payload),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke the current session (blacklist JTI, revoke refresh token)."""
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        raw_refresh = body.refresh_token if body else None
        try:
            async with transactional(session):
                await logout_user(jti, int(exp), raw_refresh, session)
        except RedisUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable",
            )
