"""Tests for the transactional() async context manager."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.transactions import transactional
from src.models import User


@pytest.mark.asyncio
async def test_transactional_commits_on_success(session: AsyncSession):
    """Changes are committed when the body completes without error."""
    async with transactional(session):
        user = User(email="tx_commit@test.com", hashed_password="x", role="ADMIN")
        session.add(user)

    # Verify the row persists in a new query on the same session
    from sqlalchemy import select

    result = await session.execute(
        select(User).where(User.email == "tx_commit@test.com")  # pyright: ignore[reportArgumentType]
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_transactional_rolls_back_on_exception(session: AsyncSession):
    """Changes are rolled back and the exception is re-raised on error."""
    with pytest.raises(ValueError, match="intentional"):
        async with transactional(session):
            user = User(email="tx_rollback@test.com", hashed_password="x", role="ADMIN")
            session.add(user)
            raise ValueError("intentional")

    from sqlalchemy import select

    result = await session.execute(
        select(User).where(User.email == "tx_rollback@test.com")  # pyright: ignore[reportArgumentType]
    )
    assert result.scalar_one_or_none() is None
