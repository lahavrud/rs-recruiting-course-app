"""Unit tests for authentication service layer."""

import base64
import typing

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from src.core.infrastructure.security import verify_password
from src.enums import UserRole
from src.models import CompanyProfile, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth import authenticate_user, register_company_user
from src.services.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    PendingApprovalError,
)
from tests.conftest import enable_sqlite_foreign_keys

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
enable_sqlite_foreign_keys(test_engine)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

FAKE_LOGO = b"fake-image-bytes"
FAKE_LOGO_NAME = "logo.png"
FAKE_LOGO_TYPE = "image/png"
FAKE_SIGNATURE_B64 = base64.b64encode(b"fake-png-signature-bytes").decode()


def _make_user_create(email: str = "company@example.com") -> UserCreate:
    return UserCreate(
        email=email,
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Test Company",
            company_id="123456789",
            address="רח׳ הדוגמה 1, תל אביב",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )


@pytest.fixture(scope="function")
async def test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
async def session(test_db) -> typing.AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_register_company_user_full_data(session: AsyncSession):
    """Test successful company user registration with all fields."""
    user_data = _make_user_create()
    result = await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        FAKE_LOGO_TYPE,
        FAKE_SIGNATURE_B64,
    )
    await session.commit()

    assert result.user.email == "company@example.com"
    assert result.user.role == UserRole.COMPANY
    assert result.user.is_active is False
    assert result.company_profile.name == "Test Company"
    assert result.company_profile.company_id == "123456789"
    assert result.company_profile.contact_first_name == "ישראל"
    assert result.company_profile.contact_last_name == "ישראלי"
    assert result.company_profile.contact_mobile_phone == "0501234567"
    assert result.company_profile.logo_url is not None

    db_result = await session.execute(
        select(User).where(User.email == "company@example.com")  # pyright: ignore[reportArgumentType]
    )
    db_user = db_result.scalar_one()
    assert verify_password("SecurePass1!", db_user.hashed_password)

    db_profile_result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.user_id == db_user.id)  # pyright: ignore[reportArgumentType]
    )
    db_profile = db_profile_result.scalar_one()
    assert db_profile.name == "Test Company"
    assert db_profile.company_id == "123456789"


@pytest.mark.asyncio
async def test_register_company_user_duplicate_email(session: AsyncSession):
    """Test registration fails when email already exists."""
    user_data = _make_user_create("duplicate@example.com")

    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    with pytest.raises(EmailAlreadyExistsError) as exc_info:
        await register_company_user(
            user_data,
            session,
            FAKE_LOGO,
            FAKE_LOGO_NAME,
            agreement_signature=FAKE_SIGNATURE_B64,
        )
    assert "duplicate@example.com" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_logo_type_rejected(session: AsyncSession):
    """Test registration fails for non-image logo content-type."""
    user_data = _make_user_create("typeerr@example.com")
    with pytest.raises(ValueError, match="image"):
        await register_company_user(
            user_data, session, b"pdf-bytes", "doc.pdf", "application/pdf"
        )


@pytest.mark.asyncio
async def test_register_logo_too_large(session: AsyncSession):
    """Test registration fails when logo exceeds 5 MB."""
    user_data = _make_user_create("toolarge@example.com")
    big_logo = b"x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="5 MB"):
        await register_company_user(
            user_data, session, big_logo, "logo.png", "image/png"
        )


@pytest.mark.asyncio
async def test_authenticate_user_success(session: AsyncSession):
    """Test successful user authentication."""
    user_data = _make_user_create("login@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    result = await session.execute(
        select(User).where(User.email == "login@example.com")  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    authenticated_user = await authenticate_user(
        "login@example.com", "SecurePass1!", session
    )
    assert authenticated_user.email == "login@example.com"
    assert authenticated_user.is_active is True


@pytest.mark.asyncio
async def test_authenticate_user_invalid_email(session: AsyncSession):
    """Test authentication fails with unknown email."""
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user("nonexistent@example.com", "somepassword", session)


@pytest.mark.asyncio
async def test_authenticate_user_invalid_password(session: AsyncSession):
    """Test authentication fails with wrong password."""
    user_data = _make_user_create("wrongpass@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    result = await session.execute(
        select(User).where(User.email == "wrongpass@example.com")  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await authenticate_user("wrongpass@example.com", "wrongpassword", session)


@pytest.mark.asyncio
async def test_authenticate_user_inactive(session: AsyncSession):
    """Test authentication fails for inactive users."""
    user_data = _make_user_create("inactive@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    with pytest.raises(PendingApprovalError):
        await authenticate_user("inactive@example.com", "SecurePass1!", session)
