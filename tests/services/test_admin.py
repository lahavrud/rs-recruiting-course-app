"""Unit tests for admin service layer."""

import base64
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import CompanyProfile, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.admin import (
    approve_company,
    get_all_admin_emails,
    list_pending_companies,
    reject_company,
)
from src.services.auth import register_company_user
from src.services.exceptions import CompanyNotFoundError, CompanyNotPendingError


@pytest.mark.asyncio
async def test_get_all_admin_emails(session: AsyncSession):
    """Test getting all admin email addresses."""
    # Create admin users
    admin1 = User(
        email="admin1@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    admin2 = User(
        email="admin2@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    # Create inactive admin (should not be included)
    admin3 = User(
        email="admin3@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    # Create company user (should not be included)
    company = User(
        email="company@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )

    session.add_all([admin1, admin2, admin3, company])
    await session.commit()

    emails = await get_all_admin_emails(session)
    assert len(emails) == 2
    assert "admin1@example.com" in emails
    assert "admin2@example.com" in emails
    assert "admin3@example.com" not in emails
    assert "company@example.com" not in emails


@pytest.mark.asyncio
async def test_list_pending_companies_empty(session: AsyncSession):
    """Test listing pending companies when none exist."""
    companies = await list_pending_companies(session)
    assert companies == []


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_list_pending_companies(mock_enqueue_email, session: AsyncSession):
    """Test listing pending company registrations."""
    mock_enqueue_email.return_value = "test-job-id"
    # Create pending companies
    user_data1 = UserCreate(
        email="pending1@example.com",
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Pending Company 1",
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )
    user_data2 = UserCreate(
        email="pending2@example.com",
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Pending Company 2",
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )
    _sig = base64.b64encode(b"fake-sig").decode()
    await register_company_user(
        user_data1, session, b"fake-logo", "logo.png", "image/png", _sig
    )
    await register_company_user(
        user_data2, session, b"fake-logo", "logo.png", "image/png", _sig
    )
    await session.commit()

    # Create an approved company (should not appear)
    user_data3 = UserCreate(
        email="approved@example.com",
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Approved Company",
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )
    await register_company_user(
        user_data3,
        session,
        b"fake-logo",
        "logo.png",
        "image/png",
        base64.b64encode(b"fake-sig").decode(),
    )
    await session.commit()

    # Activate the approved company
    result = await session.execute(
        select(User).where(User.email == "approved@example.com")  # pyright: ignore[reportArgumentType]
    )
    approved_user = result.scalar_one()
    approved_user.is_active = True
    await session.commit()

    companies = await list_pending_companies(session)
    assert len(companies) == 2

    # Check first company
    assert companies[0]["user"].email in [
        "pending1@example.com",
        "pending2@example.com",
    ]
    assert companies[0]["user"].is_active is False
    assert companies[0]["company_profile"].name in [
        "Pending Company 1",
        "Pending Company 2",
    ]

    # Check second company
    assert companies[1]["user"].email in [
        "pending1@example.com",
        "pending2@example.com",
    ]
    assert companies[1]["user"].email != companies[0]["user"].email


@pytest.mark.asyncio
@patch("src.services.admin.enqueue_email_task")
async def test_approve_company_success(mock_enqueue_email, session: AsyncSession):
    """Test successfully approving a company."""
    mock_enqueue_email.return_value = "test-job-id"
    # Create a pending company
    user_data = UserCreate(
        email="toapprove@example.com",
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="To Approve Company",
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )
    result = await register_company_user(
        user_data,
        session,
        b"fake-logo",
        "logo.png",
        "image/png",
        base64.b64encode(b"fake-sig").decode(),
    )
    await session.commit()

    company_user_id = result.user.id
    assert result.user.is_active is False

    # Approve the company
    approved = await approve_company(company_user_id, session)
    await session.commit()

    assert approved["user"].is_active is True
    assert approved["user"].email == "toapprove@example.com"
    assert approved["company_profile"].name == "To Approve Company"

    # Verify in database
    db_result = await session.execute(
        select(User).where(User.id == company_user_id)  # pyright: ignore[reportArgumentType]
    )
    db_user = db_result.scalar_one()
    assert db_user.is_active is True


@pytest.mark.asyncio
async def test_approve_company_not_found(session: AsyncSession):
    """Test approving a non-existent company raises error."""
    with pytest.raises(CompanyNotFoundError) as exc_info:
        await approve_company(99999, session)
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_approve_company_already_approved(session: AsyncSession):
    """Test approving an already approved company raises error."""
    # Create and approve a company
    user_data = UserCreate(
        email="alreadyapproved@example.com",
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Already Approved",
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )
    result = await register_company_user(
        user_data,
        session,
        b"fake-logo",
        "logo.png",
        "image/png",
        base64.b64encode(b"fake-sig").decode(),
    )
    await session.commit()

    # Manually activate
    result = await session.execute(
        select(User).where(User.id == result.user.id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    # Try to approve again
    with pytest.raises(CompanyNotPendingError) as exc_info:
        await approve_company(user.id, session)
    assert "already approved" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_approve_company_not_company_role(session: AsyncSession):
    """Test approving a non-company user raises error."""
    # Create an admin user
    admin = User(
        email="admin@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    session.add(admin)
    await session.commit()

    # Try to approve admin as company
    with pytest.raises(CompanyNotPendingError) as exc_info:
        await approve_company(admin.id, session)
    assert "not a company user" in str(exc_info.value).lower()


@pytest.mark.asyncio
@patch("src.services.admin.enqueue_email_task")
async def test_reject_company_success(mock_enqueue_email, session: AsyncSession):
    """Test successfully rejecting a company."""
    mock_enqueue_email.return_value = "test-job-id"
    # Create a pending company
    user_data = UserCreate(
        email="toreject@example.com",
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="To Reject Company",
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )
    result = await register_company_user(
        user_data,
        session,
        b"fake-logo",
        "logo.png",
        "image/png",
        base64.b64encode(b"fake-sig").decode(),
    )
    await session.commit()

    company_user_id = result.user.id
    company_profile_id = result.company_profile.id

    # Reject the company
    await reject_company(company_user_id, session)
    await session.commit()

    # Verify user is deleted
    result = await session.execute(
        select(User).where(User.id == company_user_id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    assert user is None

    # Verify company profile is deleted
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_profile_id)  # pyright: ignore[reportArgumentType]
    )
    profile = result.scalar_one_or_none()
    assert profile is None


@pytest.mark.asyncio
async def test_reject_company_not_found(session: AsyncSession):
    """Test rejecting a non-existent company raises error."""
    with pytest.raises(CompanyNotFoundError) as exc_info:
        await reject_company(99999, session)
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_reject_company_already_approved(session: AsyncSession):
    """Test rejecting an already approved company raises error."""
    # Create and approve a company
    user_data = UserCreate(
        email="alreadyapproved2@example.com",
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Already Approved 2",
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )
    result = await register_company_user(
        user_data,
        session,
        b"fake-logo",
        "logo.png",
        "image/png",
        base64.b64encode(b"fake-sig").decode(),
    )
    await session.commit()

    # Manually activate
    result = await session.execute(
        select(User).where(User.id == result.user.id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    # Try to reject
    with pytest.raises(CompanyNotPendingError) as exc_info:
        await reject_company(user.id, session)
    assert "already approved" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_reject_company_not_company_role(session: AsyncSession):
    """Test rejecting a non-company user raises error."""
    # Create an admin user
    admin = User(
        email="admin2@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    session.add(admin)
    await session.commit()

    # Try to reject admin as company
    with pytest.raises(CompanyNotPendingError) as exc_info:
        await reject_company(admin.id, session)
    assert "not a company user" in str(exc_info.value).lower()
