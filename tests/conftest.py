"""Shared pytest fixtures for all tests."""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from src.core.infrastructure.config import settings


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


# Use file-based SQLite for tests (faster than in-memory for multiple tests)
# Using a temporary file that gets cleaned up
_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
_test_db_file.close()
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_file.name}"

# Create test engine and session factory
test_engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, future=True, pool_pre_ping=True
)
# Enable FK constraints for SQLite to match PostgreSQL behavior
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
    # Ensure JWT_SECRET_KEY is set for tests
    os.environ.setdefault(
        "JWT_SECRET_KEY", "test_secret_key_min_32_chars_long_for_testing"
    )
    yield
    # Cleanup
    settings.testing = False
    os.environ.pop("TESTING", None)


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
    # Fast cleanup: delete all data from tables (much faster than drop/create)
    async with TestSessionLocal() as cleanup_session:
        # Delete in reverse order of foreign key dependencies
        await cleanup_session.execute(text("DELETE FROM application"))
        await cleanup_session.execute(text("DELETE FROM job"))
        await cleanup_session.execute(text("DELETE FROM candidateprofile"))
        await cleanup_session.execute(text("DELETE FROM companyprofile"))
        await cleanup_session.execute(text("DELETE FROM user"))
        await cleanup_session.commit()
        await cleanup_session.close()


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
