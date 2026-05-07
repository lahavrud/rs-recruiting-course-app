"""Tests for CompanyProfile model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import CompanyProfile, User


@pytest.mark.asyncio
async def test_company_profile_creation_with_required_fields(session: AsyncSession):
    """Test CompanyProfile creation with required fields."""
    user = User(
        email="company@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None

    company = CompanyProfile(
        user_id=user.id,
        name="Test Company",
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)

    assert company.id is not None
    assert company.user_id == user.id
    assert company.name == "Test Company"
    assert company.logo_url is None
    assert company.company_id is None
    assert company.contact_first_name is None
    assert company.contact_last_name is None
    assert company.contact_mobile_phone is None
    assert company.contact_landline_phone is None
    assert company.created_at is not None


@pytest.mark.asyncio
async def test_company_profile_default_values(session: AsyncSession):
    """Test CompanyProfile default values."""
    user = User(
        email="defaults@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None

    company = CompanyProfile(
        user_id=user.id,
        name="Defaults Company",
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)

    assert company.created_at is not None


@pytest.mark.asyncio
async def test_company_profile_allows_null_user_id(session: AsyncSession):
    """Admin-created companies can exist without a linked user."""
    company = CompanyProfile(name="Admin-Only Company")
    session.add(company)
    await session.commit()
    await session.refresh(company)

    assert company.id is not None
    assert company.user_id is None
    assert company.name == "Admin-Only Company"
