"""Tests for User model."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash, verify_password
from src.enums import UserRole
from src.models import CompanyProfile, User


@pytest.mark.asyncio
async def test_user_creation_with_required_fields(session: AsyncSession):
    """Test User creation with required fields."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.COMPANY,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.role == UserRole.COMPANY
    assert user.is_active is False  # Default value
    assert user.created_at is not None

    # Verify password is hashed
    assert verify_password("password123", user.hashed_password)


@pytest.mark.asyncio
async def test_user_creation_with_all_fields(session: AsyncSession):
    """Test User creation with all fields."""
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.email == "admin@example.com"
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_user_default_values(session: AsyncSession):
    """Test User default values."""
    user = User(
        email="default@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Default values
    assert user.is_active is False
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_user_email_uniqueness(session: AsyncSession):
    """Test that duplicate email raises IntegrityError."""
    user1 = User(
        email="duplicate@example.com",
        hashed_password=get_password_hash("password1"),
        role=UserRole.COMPANY,
    )
    session.add(user1)
    await session.commit()

    # Try to create another user with same email
    user2 = User(
        email="duplicate@example.com",
        hashed_password=get_password_hash("password2"),
        role=UserRole.ADMIN,
    )
    session.add(user2)

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_user_unique_emails_allowed(session: AsyncSession):
    """Test that unique emails are allowed."""
    user1 = User(
        email="user1@example.com",
        hashed_password=get_password_hash("password1"),
        role=UserRole.COMPANY,
    )
    user2 = User(
        email="user2@example.com",
        hashed_password=get_password_hash("password2"),
        role=UserRole.ADMIN,
    )
    session.add(user1)
    session.add(user2)
    await session.commit()

    assert user1.id is not None
    assert user2.id is not None
    assert user1.email != user2.email


@pytest.mark.asyncio
async def test_user_role_enum_validation(session: AsyncSession):
    """Test User role enum validation."""
    # Test ADMIN role
    admin_user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
    )
    session.add(admin_user)
    await session.commit()
    await session.refresh(admin_user)

    assert admin_user.role == UserRole.ADMIN

    # Test COMPANY role
    company_user = User(
        email="company@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
    )
    session.add(company_user)
    await session.commit()
    await session.refresh(company_user)

    assert company_user.role == UserRole.COMPANY


@pytest.mark.asyncio
async def test_user_company_profile_relationship(session: AsyncSession):
    """Test User-CompanyProfile 1:1 relationship."""
    user = User(
        email="company_user@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None
    user_id = user.id

    company_profile = CompanyProfile(
        user_id=user_id,
        name="Test Company",
    )
    session.add(company_profile)
    await session.commit()
    await session.refresh(user)
    await session.refresh(company_profile)
    assert company_profile.id is not None
    company_id = company_profile.id

    # Test relationship access - need to explicitly load relationships
    # SQLModel relationships require eager loading in async context
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # Query to load the relationship with eager loading
    result = await session.execute(
        select(User)
        .options(selectinload(User.company_profile))  # pyright: ignore[reportArgumentType]
        .where(User.id == user_id)  # pyright: ignore[reportArgumentType]
    )
    loaded_user = result.scalar_one()
    assert loaded_user.company_profile is not None
    assert loaded_user.company_profile.id == company_profile.id
    assert loaded_user.company_profile.name == "Test Company"

    result = await session.execute(
        select(CompanyProfile)
        .options(selectinload(CompanyProfile.user))  # pyright: ignore[reportArgumentType]
        .where(CompanyProfile.id == company_id)  # pyright: ignore[reportArgumentType]
    )
    loaded_company = result.scalar_one()
    assert loaded_company.user.id == user_id


@pytest.mark.asyncio
async def test_user_company_profile_foreign_key_constraint(session: AsyncSession):
    """Test foreign key constraint for User-CompanyProfile relationship."""
    # Try to create CompanyProfile with non-existent user_id
    company_profile = CompanyProfile(
        user_id=9999,  # Non-existent user
        name="Test Company",
    )
    session.add(company_profile)

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_user_password_hashing(session: AsyncSession):
    """Test that password is hashed (not stored plaintext)."""
    plain_password = "my_secret_password"
    user = User(
        email="password_test@example.com",
        hashed_password=get_password_hash(plain_password),
        role=UserRole.COMPANY,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Password should be hashed, not plaintext
    assert user.hashed_password != plain_password
    assert len(user.hashed_password) == 60  # Bcrypt hash length
    assert user.hashed_password.startswith("$2")  # Bcrypt prefix

    # But should verify correctly
    assert verify_password(plain_password, user.hashed_password)
    assert not verify_password("wrong_password", user.hashed_password)


@pytest.mark.asyncio
async def test_user_password_verification(session: AsyncSession):
    """Test password verification works correctly."""
    password = "test_password_123"
    user = User(
        email="verify@example.com",
        hashed_password=get_password_hash(password),
        role=UserRole.COMPANY,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Correct password should verify
    assert verify_password(password, user.hashed_password)

    # Wrong password should not verify
    assert not verify_password("wrong_password", user.hashed_password)
    assert not verify_password("", user.hashed_password)


@pytest.mark.asyncio
async def test_user_admin_no_company_profile(session: AsyncSession):
    """Test that ADMIN users don't require CompanyProfile."""
    admin_user = User(
        email="admin_only@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin_user)
    await session.commit()
    await session.refresh(admin_user)

    # Admin user should not have company_profile
    # Accessing it should return None or raise AttributeError depending on
    # SQLModel behavior. In SQLModel, accessing a relationship that doesn't
    # exist may return None or require a query. For this test, we just verify
    # the user exists.
    assert admin_user.id is not None
    assert admin_user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_user_query_by_email(session: AsyncSession):
    """Test querying User by email (indexed field)."""
    user = User(
        email="query_test@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
    )
    session.add(user)
    await session.commit()

    # Query by email
    result = await session.execute(
        select(User).where(User.email == "query_test@example.com")  # pyright: ignore[reportArgumentType]
    )
    found_user = result.scalar_one_or_none()

    assert found_user is not None
    assert found_user.id == user.id
    assert found_user.email == "query_test@example.com"
