"""Async database query helpers to reduce boilerplate in service functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

T = TypeVar("T", bound=SQLModel)


async def get_by_id(
    session: AsyncSession,
    model: type[T],
    pk: int,
) -> T | None:
    """Fetch a single row by primary key; return None if not found."""
    result = await session.execute(
        select(model).where(model.id == pk)  # pyright: ignore[reportAttributeAccessIssue]
    )
    return result.scalar_one_or_none()


async def get_by_id_or_raise(
    session: AsyncSession,
    model: type[T],
    pk: int,
    exc_factory: Callable[[int], Exception],
) -> T:
    """Fetch a single row by primary key; raise exc_factory(pk) if not found."""
    obj = await get_by_id(session, model, pk)
    if obj is None:
        raise exc_factory(pk)
    return obj
