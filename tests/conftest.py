# ruff: noqa: E402  -- env var must be set before src imports (see _TEST_JWT_SECRET below)
"""Shared pytest fixtures for all tests."""

import asyncio
import base64
import os
import tempfile
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

# Single source of truth for the test JWT secret.
# Set with os.environ[] (not setdefault) so it always wins over any value that
# might already be in the environment, and so every xdist worker process gets
# the same predictable value at import time — before settings is loaded.
_TEST_JWT_SECRET = "test-secret-key-min-32-chars-for-testing!"
os.environ["JWT_SECRET_KEY"] = _TEST_JWT_SECRET

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import (
    get_current_admin,
    get_current_company,
    get_current_user,
)
from src.core.infrastructure.security import get_password_hash
from src.enums import ApplicationStatus, JobStatus, UserRole
from src.main import app
from src.models import Application, CandidateProfile, CompanyProfile, Job, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth import register_company_user

_EMAIL_TASK_TARGETS = [
    "src.services.auth.enqueue_email_task",
    "src.services.admin.enqueue_email_task",
    "src.services.jobs.enqueue_email_task",
    "src.services.jobs_admin.enqueue_email_task",
    "src.services.candidates.enqueue_email_task",
    # applications_admin no longer imports enqueue_email_task directly;
    # the router enqueues after commit — patch at the router level instead.
    "src.api.admin_applications.enqueue_email_task",
]


@pytest.fixture(autouse=True)
def mock_enqueue_email():
    """Patch enqueue_email_task in every service module for all tests.

    Prevents any test from trying to connect to Redis. Each service imports
    enqueue_email_task with 'from src.core.tasks import ...', creating a local
    binding, so each module must be patched individually.
    """
    patches = [patch(target, new_callable=AsyncMock) for target in _EMAIL_TASK_TARGETS]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def mock_auth_redis():
    """Patch Redis-backed auth helpers for all tests (no Redis in CI).

    Mocks:
    - lockout check / record / clear (no-ops — any login succeeds)
    - access token blacklist check (always returns False — no token is revoked)
    """
    with (
        patch("src.services.auth._check_lockout", new_callable=AsyncMock),
        patch("src.services.auth._record_failed_attempt", new_callable=AsyncMock),
        patch("src.services.auth._clear_failed_attempts", new_callable=AsyncMock),
        patch(
            "src.core.infrastructure.security.is_access_token_blacklisted",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_invite_tokens():
    """Patch invite token functions for all tests to prevent Redis connections.

    validate_invite_token is a no-op (any token is valid) and consume_invite_token
    is a no-op. Tests that want to test rejection pass the mock in via the fixture.
    """
    with (
        patch(
            "src.api.auth.validate_invite_token", new_callable=AsyncMock
        ) as mock_validate,
        patch("src.api.auth.consume_invite_token", new_callable=AsyncMock),
        patch(
            "src.api.admin_companies.generate_invite_token",
            new_callable=AsyncMock,
            return_value="test-invite-token-abc123",
        ),
    ):
        yield mock_validate


@pytest.fixture(autouse=True)
def mock_storage_provider():
    """Patch storage provider for all tests — prevents real S3/disk uploads."""
    mock = MagicMock()
    mock.upload_file = AsyncMock(return_value="logos/test-logo.png")
    with patch("src.services.auth.get_storage_provider", return_value=mock):
        yield mock


def enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    """Enable foreign key constraint enforcement for SQLite.

    This function should be called after creating a SQLite async engine to ensure
    foreign key constraints are enforced during tests, matching PostgreSQL
    behavior in production.

    Args:
        engine: SQLAlchemy AsyncEngine instance
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        """Execute PRAGMA foreign_keys=ON for each connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Use DATABASE_URL from the environment when it is a PostgreSQL URL (CI),
# otherwise fall back to a temporary SQLite file (local development).
# PostgreSQL tests run sequentially (-n 0) to avoid workers sharing one DB.
_env_db_url = os.environ.get("DATABASE_URL", "")

if _env_db_url.startswith("postgresql"):
    TEST_DATABASE_URL = _env_db_url
    test_engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, future=True, pool_pre_ping=True
    )
    # No SQLite FK pragma needed — PostgreSQL enforces FKs natively
else:
    # File-based SQLite: faster than :memory: for multiple tests, and each
    # xdist worker gets its own temp file (process-level isolation).
    _test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    _test_db_file.close()
    TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_file.name}"
    test_engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, future=True, pool_pre_ping=True
    )
    enable_sqlite_foreign_keys(test_engine)

TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async fixtures.

    This allows session-scoped async fixtures to work properly.
    Only used when session-scoped async fixtures are needed.

    Note: This triggers a deprecation warning from pytest-asyncio, which is suppressed
    in pyproject.toml filterwarnings. The warning is expected when using session-scoped
    async fixtures and will be addressed when pytest-asyncio provides better support.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_testing_environment():
    """Set up testing environment before all tests."""
    # Enable testing mode (disables rate limiting and config validation)
    settings.testing = True
    yield
    # Cleanup
    settings.testing = False


@pytest.fixture(scope="function", autouse=True)
async def test_db() -> AsyncGenerator[None, None]:
    """Create test database tables and clean up between tests.

    Optimized approach:
    1. Create tables once (first test)
    2. Use DELETE statements to clean data between tests (faster than DROP/CREATE)
    3. Drop tables only at the end
    """
    # Create tables if they don't exist (idempotent)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    # Dialect-agnostic cleanup using SQLModel metadata table references.
    # Avoids raw SQL with "user" which is a reserved word in PostgreSQL.
    # Reversed sorted_tables respects FK dependency order automatically.
    async with test_engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session.

    Each test gets a fresh session. Data is cleaned up via test_db fixture.
    """
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def mock_s3_bucket():
    """Fixture providing mock S3 bucket configuration.

    Can be reused across multiple test files.
    """
    return {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
    }


# ==================== User Fixtures ====================


def _make_company_profile_create(name: str) -> CompanyProfileCreate:
    return CompanyProfileCreate(
        name=name,
        company_id="123456789",
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )


_FAKE_LOGO = b"fake-logo-bytes"
_FAKE_SIGNATURE_B64 = base64.b64encode(b"fake-png-signature-bytes").decode()


_STRONG_PASSWORD = "SecurePass1!"


_STRONG_PASSWORD = "SecurePass1!"


@pytest.fixture
async def company_user(test_db) -> User:
    """Create a pending (inactive) company user for testing."""
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password=_STRONG_PASSWORD,
            company_profile=_make_company_profile_create("Test Company"),
        )
        result = await register_company_user(
            user_data, session, _FAKE_LOGO, "logo.png", "image/png", _FAKE_SIGNATURE_B64
        )
        await session.commit()
        return result.user


@pytest.fixture
async def approved_company_user(test_db) -> User:
    """Create an approved (active) company user for testing."""
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="approved@test.com",
            password=_STRONG_PASSWORD,
            company_profile=_make_company_profile_create("Approved Company"),
        )
        result = await register_company_user(
            user_data, session, _FAKE_LOGO, "logo.png", "image/png", _FAKE_SIGNATURE_B64
        )
        result.user.is_active = True
        await session.commit()
        return result.user


@pytest.fixture
async def company_profile(approved_company_user: User) -> CompanyProfile:
    """Get company profile for approved company user."""
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                CompanyProfile.user_id == approved_company_user.id
            )
        )
        return result.scalar_one()


@pytest.fixture
async def admin_user(test_db) -> User:
    """Create an admin user for testing."""
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


@pytest.fixture
async def company_with_user(session: AsyncSession) -> CompanyProfile:
    """Create a company user and profile for service layer testing."""
    user = User(
        email="company@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None

    company = CompanyProfile(
        user_id=user.id,
        name="Test Company",
        company_id="123456789",
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    assert company.id is not None
    return company


# ==================== Job Fixtures ====================


@pytest.fixture
async def job(company_profile: CompanyProfile) -> Job:
    """Create a pending job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            description="We are looking for a senior Python developer...",
            requirements="5+ years experience with Python, FastAPI, PostgreSQL",
            location="Tel Aviv, Israel",
            status=JobStatus.PENDING_APPROVAL,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def pending_job(company_profile: CompanyProfile) -> Job:
    """Create a pending job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            description="We are looking for a senior Python developer...",
            requirements="5+ years experience with Python, FastAPI, PostgreSQL",
            location="Tel Aviv, Israel",
            status=JobStatus.PENDING_APPROVAL,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def published_job(company_profile: CompanyProfile) -> Job:
    """Create a published job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            description="We are looking for a senior Python developer...",
            requirements="5+ years experience with Python, FastAPI, PostgreSQL",
            location="Tel Aviv, Israel",
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def closed_job(company_profile: CompanyProfile) -> Job:
    """Create a closed job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Closed Position",
            description="This position is closed",
            requirements="N/A",
            location="N/A",
            status=JobStatus.CLOSED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


# ==================== Application Fixtures ====================


@pytest.fixture
async def candidate_profile(test_db) -> CandidateProfile:
    """Create a candidate profile for testing."""
    async with TestSessionLocal() as session:
        candidate = CandidateProfile(
            full_name="Jane Candidate",
            email="jane@candidate.com",
            phone="555-1234",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return candidate


@pytest.fixture
async def application(
    published_job: Job, candidate_profile: CandidateProfile
) -> Application:
    """Create a NEW application linking a candidate to a published job."""
    async with TestSessionLocal() as session:
        app_obj = Application(
            job_id=published_job.id,
            candidate_id=candidate_profile.id,
            status=ApplicationStatus.NEW,
        )
        session.add(app_obj)
        await session.commit()
        await session.refresh(app_obj)
        return app_obj


# ==================== API Client Fixtures ====================


async def override_get_session():
    """Override get_session dependency for tests."""
    async with TestSessionLocal() as session:
        yield session


def setup_admin_overrides(admin_user: User):
    """Helper function to set up admin authentication overrides."""
    app.dependency_overrides[get_session] = override_get_session

    async def override_get_current_user(
        credentials=None,  # noqa: ARG001
        session=None,  # noqa: ARG001
    ):
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_admin] = override_get_current_user


@pytest.fixture
async def company_client(
    approved_company_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Create test client authenticated as a company user."""

    async def override_get_session():
        async with TestSessionLocal() as session:
            yield session

    async def override_get_current_company():
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == approved_company_user.id)  # pyright: ignore[reportArgumentType]
            )
            user = result.scalar_one()
            result = await session.execute(
                select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                    CompanyProfile.user_id == user.id
                )
            )
            company_profile = result.scalar_one()
            return (user, company_profile)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_company] = override_get_current_company

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(admin_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Create test client authenticated as an admin user."""
    setup_admin_overrides(admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def public_client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client without authentication (for public endpoints)."""
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# Legacy alias for backward compatibility
@pytest.fixture
async def client(company_client: AsyncClient) -> AsyncClient:
    """Legacy alias for company_client."""
    return company_client
