"""Unit tests for admin_invites service layer."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import InviteTokenStatus, UserRole
from src.models import InviteToken, User
from src.schemas import InviteTokenCreate
from src.services.admin_invites import (
    create_invite,
    list_invites,
    resend_invite,
    revoke_invite,
)
from src.services.exceptions import (
    EmailAlreadyExistsError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
)


async def _make_admin(session: AsyncSession) -> int:
    admin = User(
        email="inviteadmin@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    assert admin.id is not None
    return admin.id


def _invite_data(email: str, **kwargs: object) -> InviteTokenCreate:
    return InviteTokenCreate(
        email=email,
        company_name=None,
        contact_first_name=None,
        contact_last_name=None,
        note=None,
        **kwargs,  # type: ignore[arg-type]
    )


# ── create_invite ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invite_success(session: AsyncSession):
    admin_id = await _make_admin(session)
    data = InviteTokenCreate(
        email="invite@example.com",
        company_name="Test Co",
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        note=None,
    )
    result = await create_invite(admin_user_id=admin_id, data=data, session=session)
    await session.commit()

    assert result.email == "invite@example.com"
    assert result.company_name == "Test Co"
    assert result.status == InviteTokenStatus.PENDING

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.email == "invite@example.com")  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    assert db.status == InviteTokenStatus.PENDING


@pytest.mark.asyncio
async def test_create_invite_duplicate_pending_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    data = _invite_data("dup@example.com")
    await create_invite(admin_user_id=admin_id, data=data, session=session)
    await session.commit()

    with pytest.raises(InvitePendingForEmailError):
        await create_invite(admin_user_id=admin_id, data=data, session=session)


@pytest.mark.asyncio
async def test_create_invite_existing_user_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    user = User(
        email="existing@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.commit()

    with pytest.raises(EmailAlreadyExistsError):
        await create_invite(
            admin_user_id=admin_id,
            data=_invite_data("existing@example.com"),
            session=session,
        )


# ── list_invites ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_invites_empty(session: AsyncSession):
    assert await list_invites(session) == []


@pytest.mark.asyncio
async def test_list_invites_returns_all(session: AsyncSession):
    admin_id = await _make_admin(session)
    _exp = datetime(2099, 1, 1, tzinfo=timezone.utc)
    tokens = [("token-aaa", _exp), ("token-bbb", _exp)]
    with patch(
        "src.services.admin_invites.generate_invite_token",
        new_callable=AsyncMock,
        side_effect=tokens,
    ):
        for email in ["a@example.com", "b@example.com"]:
            await create_invite(
                admin_user_id=admin_id, data=_invite_data(email), session=session
            )
    await session.commit()

    invites = await list_invites(session)
    assert len(invites) == 2
    assert {i.email for i in invites} == {"a@example.com", "b@example.com"}


# ── revoke_invite ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_invite_success(session: AsyncSession):
    admin_id = await _make_admin(session)
    created = await create_invite(
        admin_user_id=admin_id, data=_invite_data("revoke@example.com"), session=session
    )
    await session.commit()

    await revoke_invite(created.id, session)
    await session.commit()

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.id == created.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    assert db.status == InviteTokenStatus.REVOKED


@pytest.mark.asyncio
async def test_revoke_invite_not_found(session: AsyncSession):
    with pytest.raises(InviteNotFoundError):
        await revoke_invite(99999, session)


@pytest.mark.asyncio
async def test_revoke_invite_already_revoked_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    created = await create_invite(
        admin_user_id=admin_id,
        data=_invite_data("revoked2@example.com"),
        session=session,
    )
    await session.commit()

    await revoke_invite(created.id, session)
    await session.commit()

    with pytest.raises(InviteAlreadyRevokedError):
        await revoke_invite(created.id, session)


# ── resend_invite ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_invite_success(session: AsyncSession):
    admin_id = await _make_admin(session)
    _exp = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with patch(
        "src.services.admin_invites.generate_invite_token",
        new_callable=AsyncMock,
        side_effect=[("original-token", _exp), ("new-token", _exp)],
    ):
        created = await create_invite(
            admin_user_id=admin_id,
            data=_invite_data("resend@example.com"),
            session=session,
        )
        await session.commit()

        await resend_invite(created.id, session)
        await session.commit()

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.id == created.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    assert db.status == InviteTokenStatus.PENDING
    assert db.token == "new-token"


@pytest.mark.asyncio
async def test_resend_invite_not_found(session: AsyncSession):
    with pytest.raises(InviteNotFoundError):
        await resend_invite(99999, session)


@pytest.mark.asyncio
async def test_resend_used_invite_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    created = await create_invite(
        admin_user_id=admin_id, data=_invite_data("used@example.com"), session=session
    )
    await session.commit()

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.id == created.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    db.status = InviteTokenStatus.USED
    await session.commit()

    with pytest.raises(InviteAlreadyRevokedError):
        await resend_invite(created.id, session)
