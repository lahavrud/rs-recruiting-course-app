"""Tests for the transactional() async context manager."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.transactions import (
    _post_commit_hooks,
    defer_after_commit,
    transactional,
)
from rs_shared.models import User


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


@pytest.mark.asyncio
async def test_deferred_hook_runs_after_commit(session: AsyncSession):
    """defer_after_commit() hook is called after a successful commit."""
    calls = []

    async def side_effect() -> None:
        calls.append("called")

    async with transactional(session):
        defer_after_commit(side_effect)

    assert calls == ["called"]


@pytest.mark.asyncio
async def test_deferred_hook_not_called_on_rollback(session: AsyncSession):
    """defer_after_commit() hook is discarded when the transaction rolls back."""
    calls = []

    async def side_effect() -> None:
        calls.append("called")

    with pytest.raises(ValueError):
        async with transactional(session):
            defer_after_commit(side_effect)
            raise ValueError("forced rollback")

    assert calls == []


@pytest.mark.asyncio
async def test_defer_after_commit_raises_outside_transaction():
    """defer_after_commit() raises RuntimeError when called outside transactional().

    Reset the contextvar set by the autouse `_provide_post_commit_hooks_context`
    fixture so we test the production contract: outside any transactional block
    the hooks list is None and defer_after_commit() must raise.
    """
    token = _post_commit_hooks.set(None)
    try:
        with pytest.raises(RuntimeError, match="outside of transactional"):
            defer_after_commit(lambda: None)  # type: ignore[arg-type]
    finally:
        _post_commit_hooks.reset(token)


@pytest.mark.asyncio
async def test_multiple_deferred_hooks_all_run(session: AsyncSession):
    """All registered hooks are called in registration order."""
    calls: list[int] = []

    async def hook(n: int) -> None:
        calls.append(n)

    async with transactional(session):
        defer_after_commit(lambda: hook(1))
        defer_after_commit(lambda: hook(2))
        defer_after_commit(lambda: hook(3))

    assert calls == [1, 2, 3]
