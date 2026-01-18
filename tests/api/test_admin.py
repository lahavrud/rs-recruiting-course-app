"""Tests for admin endpoints."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlmodel import SQLModel

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin, get_current_user
from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.main import app
from src.models import User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth import register_company_user
from tests.conftest import TestSessionLocal, test_engine


async def override_get_session():
    """Override get_session dependency for tests."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
async def admin_user():
    """Create an admin user for authentication.

    Session-scoped fixture: same admin user reused across all tests in the session.
    This reduces database setup overhead significantly.

    Ensures database tables exist before creating the admin user.
    """
    # Ensure tables exist (idempotent)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with TestSessionLocal() as session:
        admin = User(
            email="admin@test.com",
            hashed_password=get_password_hash("adminpassword"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


@pytest.fixture(scope="function")
async def company_user(test_db):
    """Create a pending company user."""
    with patch("src.services.auth.enqueue_email_task") as mock_enqueue:
        mock_enqueue.return_value = "test-job-id"
        async with TestSessionLocal() as session:
            user_data = UserCreate(
                email="company@test.com",
                password="companypassword",
                company_profile=CompanyProfileCreate(name="Test Company"),
            )
            result = await register_company_user(user_data, session)
            await session.commit()
            return result.user


@pytest.fixture(scope="session")
async def client(admin_user):
    """Create test client with overridden dependencies.

    Session-scoped fixture: same client reused across all tests in the session.
    This reduces AsyncClient creation overhead significantly.
    """
    # Override database dependency
    app.dependency_overrides[get_session] = override_get_session

    # Override get_current_user to return admin_user directly (no DB query)
    async def override_get_current_user():
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_admin] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_pending_companies_empty(client: AsyncClient):
    """Test getting pending companies when none exist."""
    response = await client.get("/api/admin/companies/pending")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_get_pending_companies(
    mock_enqueue_email, client: AsyncClient, company_user
):
    """Test getting list of pending companies."""
    mock_enqueue_email.return_value = "test-job-id"
    # Create another pending company
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company2@test.com",
            password="password",
            company_profile=CompanyProfileCreate(name="Company 2"),
        )
        await register_company_user(user_data, session)
        await session.commit()

    response = await client.get("/api/admin/companies/pending")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2

    # Check structure
    for company in data:
        assert "user" in company
        assert "company_profile" in company
        assert company["user"]["is_active"] is False
        assert company["user"]["role"] == "COMPANY"


@pytest.mark.asyncio
@patch("src.services.admin.enqueue_email_task")
async def test_approve_company_success(
    mock_enqueue_email, client: AsyncClient, company_user
):
    """Test successfully approving a company."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await client.post(f"/api/admin/companies/{company_user.id}/approve")
    assert response.status_code == 200

    data = response.json()
    assert data["user"]["id"] == company_user.id
    assert data["user"]["is_active"] is True
    assert data["company_profile"]["name"] == "Test Company"

    # Verify in database
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == company_user.id)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        assert user.is_active is True


@pytest.mark.asyncio
async def test_approve_company_not_found(client: AsyncClient):
    """Test approving a non-existent company returns 404."""
    response = await client.post("/api/admin/companies/99999/approve")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_approve_company_already_approved(client: AsyncClient, company_user):
    """Test approving an already approved company returns 400."""
    # First approve
    response1 = await client.post(f"/api/admin/companies/{company_user.id}/approve")
    assert response1.status_code == 200

    # Try to approve again
    response2 = await client.post(f"/api/admin/companies/{company_user.id}/approve")
    assert response2.status_code == 400
    assert "already approved" in response2.json()["detail"].lower()


@pytest.mark.asyncio
@patch("src.services.admin.enqueue_email_task")
async def test_reject_company_success(
    mock_enqueue_email, client: AsyncClient, company_user
):
    """Test successfully rejecting a company."""
    mock_enqueue_email.return_value = "test-job-id"
    company_id = company_user.id

    response = await client.post(f"/api/admin/companies/{company_id}/reject")
    assert response.status_code == 204

    # Verify user is deleted
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == company_id)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one_or_none()
        assert user is None


@pytest.mark.asyncio
async def test_reject_company_not_found(client: AsyncClient):
    """Test rejecting a non-existent company returns 404."""
    response = await client.post("/api/admin/companies/99999/reject")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reject_company_already_approved(client: AsyncClient, company_user):
    """Test rejecting an already approved company returns 400."""
    # First approve
    response1 = await client.post(f"/api/admin/companies/{company_user.id}/approve")
    assert response1.status_code == 200

    # Try to reject
    response2 = await client.post(f"/api/admin/companies/{company_user.id}/reject")
    assert response2.status_code == 400
    assert "already approved" in response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_endpoints_require_auth(test_db):
    """Test that admin endpoints require authentication."""
    # Clear any existing overrides from session-scoped fixtures
    app.dependency_overrides.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Override only database, not auth
        app.dependency_overrides[get_session] = override_get_session

        response = await client.get("/api/admin/companies/pending")
        assert response.status_code == 401  # Unauthorized (no auth token)

        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_admin_endpoints_require_admin_role(mock_enqueue_email, test_db):
    """Test that admin endpoints require admin role."""
    # Clear any existing overrides from session-scoped fixtures
    app.dependency_overrides.clear()

    mock_enqueue_email.return_value = "test-job-id"
    # Create a company user (not admin)
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password="password",
            company_profile=CompanyProfileCreate(name="Company"),
        )
        result = await register_company_user(user_data, session)
        await session.commit()
        company_user = result.user

    # Override get_current_user to return company user
    async def override_get_current_company_user():
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == company_user.id)  # pyright: ignore[reportArgumentType]
            )
            return result.scalar_one()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_company_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/admin/companies/pending")
        assert response.status_code == 403  # Forbidden (not admin)
        assert "admin" in response.json()["detail"].lower()

    app.dependency_overrides.clear()
