"""Tests for admin company approval endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models import User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth import register_company_user
from tests.conftest import TestSessionLocal
from tests.factories import FAKE_LOGO, FAKE_SIG_B64


@pytest.mark.asyncio
async def test_get_pending_companies_empty(admin_client: AsyncClient):
    """Test getting pending companies when none exist."""
    response = await admin_client.get("/api/admin/companies/pending")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_get_pending_companies(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test getting list of pending companies."""
    mock_enqueue_email.return_value = "test-job-id"
    # Create another pending company
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company2@test.com",
            password="SecurePass1!",
            company_profile=CompanyProfileCreate(
                name="Company 2",
                company_id="123456789",
                address="רח׳ הדוגמה 1, תל אביב",
                contact_first_name="ישראל",
                contact_last_name="ישראלי",
                contact_mobile_phone="0501234567",
            ),
        )
        await register_company_user(
            user_data,
            session,
            FAKE_LOGO,
            "logo.png",
            "image/png",
            FAKE_SIG_B64,
        )
        await session.commit()

    response = await admin_client.get("/api/admin/companies/pending")
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
@patch("src.services.admin_companies.enqueue_email_task")
async def test_approve_company_success(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test successfully approving a company."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["user"]["id"] == company_user.id
    # Approval creates an ActivationToken but does NOT set is_active=True yet
    assert data["user"]["is_active"] is False
    assert data["company_profile"]["name"] == "Test Company"

    # Verify in database — still inactive until company clicks the link
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == company_user.id)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        assert user.is_active is False


@pytest.mark.asyncio
async def test_approve_company_not_found(admin_client: AsyncClient):
    """Test approving a non-existent company returns 404."""
    response = await admin_client.post("/api/admin/companies/99999/approve")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("src.services.admin_companies.enqueue_email_task")
async def test_approve_company_already_approved(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test re-approving revokes the previous token and issues a fresh one (200)."""
    mock_enqueue_email.return_value = "test-job-id"
    response1 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response1.status_code == 200

    # Second approve revokes old token and sends a fresh activation email
    response2 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response2.status_code == 200


@pytest.mark.asyncio
@patch("src.services.admin_companies.enqueue_email_task")
async def test_reject_company_success(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test successfully rejecting a company."""
    mock_enqueue_email.return_value = "test-job-id"
    company_id = company_user.id

    response = await admin_client.post(f"/api/admin/companies/{company_id}/reject")
    assert response.status_code == 204

    # Verify user is deleted
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == company_id)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one_or_none()
        assert user is None


@pytest.mark.asyncio
async def test_reject_company_not_found(admin_client: AsyncClient):
    """Test rejecting a non-existent company returns 404."""
    response = await admin_client.post("/api/admin/companies/99999/reject")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("src.services.admin_companies.enqueue_email_task")
async def test_reject_company_already_approved(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test rejecting after approval revokes the token and rejects the company (204)."""
    mock_enqueue_email.return_value = "test-job-id"
    response1 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response1.status_code == 200

    # Rejection after approval now succeeds — revokes the activation token
    response2 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/reject"
    )
    assert response2.status_code == 204


@pytest.mark.asyncio
async def test_admin_company_endpoints_require_auth(test_db):
    """Test that admin company endpoints require authentication."""
    from httpx import ASGITransport, AsyncClient

    from src.core.infrastructure.database import get_session
    from src.main import app
    from tests.conftest import override_get_session

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
async def test_admin_company_endpoints_require_admin_role(mock_enqueue_email, test_db):
    """Test that admin company endpoints require admin role."""
    from httpx import ASGITransport, AsyncClient

    from src.core.infrastructure.database import get_session
    from src.core.infrastructure.dependencies import get_current_user
    from src.main import app
    from tests.conftest import override_get_session

    app.dependency_overrides.clear()

    mock_enqueue_email.return_value = "test-job-id"
    # Create a company user (not admin)
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password="SecurePass1!",
            company_profile=CompanyProfileCreate(
                name="Company",
                company_id="123456789",
                address="רח׳ הדוגמה 1, תל אביב",
                contact_first_name="ישראל",
                contact_last_name="ישראלי",
                contact_mobile_phone="0501234567",
            ),
        )
        result = await register_company_user(
            user_data,
            session,
            FAKE_LOGO,
            "logo.png",
            "image/png",
            FAKE_SIG_B64,
        )
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


@pytest.mark.asyncio
async def test_generate_invite_token_returns_token(admin_client: AsyncClient):
    """Test that admin can generate an invite token."""
    response = await admin_client.post(
        "/api/admin/companies/invite",
        json={"email": "invite@example.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert (
        data["token"] == "test-invite-token-abc123"
    )  # value set by mock_invite_tokens fixture


@pytest.mark.asyncio
async def test_generate_invite_token_requires_admin(public_client: AsyncClient):
    """Test that the invite endpoint requires admin authentication."""
    response = await public_client.post("/api/admin/companies/invite")
    assert response.status_code == 401
