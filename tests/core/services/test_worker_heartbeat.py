"""Tests for the worker version heartbeat (record + read of the singleton row)."""

from sqlalchemy import text

from rs_shared.core.services.worker_heartbeat import (
    read_worker_version,
    record_heartbeat,
)


async def test_read_returns_none_before_any_heartbeat(session):
    assert await read_worker_version(session) is None


async def test_record_then_read_roundtrips(session):
    await record_heartbeat(session, "v1.4.0")
    assert await read_worker_version(session) == "v1.4.0"


async def test_record_upserts_the_single_row(session):
    await record_heartbeat(session, "v1.4.0")
    await record_heartbeat(session, "v1.5.0")

    assert await read_worker_version(session) == "v1.5.0"
    count = (
        await session.execute(text("SELECT COUNT(*) FROM worker_heartbeat"))
    ).scalar_one()
    assert count == 1
