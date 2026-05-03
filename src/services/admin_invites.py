"""Admin service layer for invite token management."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.invite_tokens import (
    generate_invite_token,
    revoke_invite_token,
)
from src.core.tasks import enqueue_email_task
from src.enums import InviteTokenStatus
from src.models import InviteToken, User
from src.schemas import InviteTokenCreate, InviteTokenRead
from src.services.exceptions import (
    EmailAlreadyExistsError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
)


def _build_invite_email(
    contact_name: str | None,
    company_name: str | None,
    note: str | None,
    registration_url: str,
) -> str:
    lines: list[str] = []
    greeting = f"שלום {contact_name}," if contact_name else "שלום,"
    lines.append(greeting)
    lines.append("")
    if company_name:
        lines.append(
            f"הוזמנת להירשם לפלטפורמת RS Recruiting עבור החברה: {company_name}"
        )
    else:
        lines.append("הוזמנת להירשם לפלטפורמת RS Recruiting.")
    lines.append("")
    lines.append("לחצו על הקישור הבא להשלמת תהליך ההרשמה:")
    lines.append("")
    lines.append(registration_url)
    lines.append("")
    if note:
        lines.append(f"הודעה אישית: {note}")
        lines.append("")
    lines.append("שימו לב: הקישור תקף ל-48 שעות בלבד.")
    lines.append("")
    lines.append("בברכה,")
    lines.append("צוות RS Recruiting")
    return "\n".join(lines)


async def create_invite(
    admin_user_id: int,
    data: InviteTokenCreate,
    session: AsyncSession,
) -> InviteTokenRead:
    """Generate a token, store metadata in DB, send invite email."""
    existing_user = await session.execute(select(User).where(User.email == data.email))
    if existing_user.scalar_one_or_none() is not None:
        raise EmailAlreadyExistsError(data.email)

    pending_invite = await session.execute(
        select(InviteToken).where(
            InviteToken.email == data.email,
            InviteToken.status == InviteTokenStatus.PENDING,  # type: ignore[arg-type]
        )
    )
    if pending_invite.scalar_one_or_none() is not None:
        raise InvitePendingForEmailError(data.email)

    token, expires_at = await generate_invite_token()

    record = InviteToken(
        token=token,
        email=data.email,
        company_name=data.company_name,
        contact_first_name=data.contact_first_name,
        contact_last_name=data.contact_last_name,
        note=data.note,
        status=InviteTokenStatus.PENDING,
        created_by_admin_id=admin_user_id,
        expires_at=expires_at,
    )
    session.add(record)
    await session.flush()

    registration_url = f"{settings.frontend_base_url}/register?token={token}"
    contact_name = (
        " ".join(filter(None, [data.contact_first_name, data.contact_last_name]))
        or None
    )
    email_body = _build_invite_email(
        contact_name, data.company_name, data.note, registration_url
    )

    await enqueue_email_task(
        to=data.email,
        subject="הזמנה להרשמה ל-RS Recruiting",
        body=email_body,
    )

    return InviteTokenRead.model_validate(record)


async def list_invites(session: AsyncSession) -> list[InviteTokenRead]:
    """Return all invite records, marking expired ones in bulk first."""
    now = datetime.now(timezone.utc)
    await session.execute(
        update(InviteToken)
        .where(
            InviteToken.status == InviteTokenStatus.PENDING,  # type: ignore[arg-type]
            InviteToken.expires_at < now,  # type: ignore[operator]
        )
        .values(status=InviteTokenStatus.EXPIRED)
    )

    result = await session.execute(
        select(InviteToken).order_by(InviteToken.created_at.desc())  # type: ignore[arg-type]
    )
    records = result.scalars().all()
    return [InviteTokenRead.model_validate(r) for r in records]


async def revoke_invite(token_id: int, session: AsyncSession) -> None:
    """Revoke a pending invite: delete from Redis and mark as revoked in DB."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.id == token_id)  # type: ignore[arg-type]
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise InviteNotFoundError(f"Invite token with ID {token_id} not found")
    if record.status != InviteTokenStatus.PENDING:
        raise InviteAlreadyRevokedError(
            f"Invite {token_id} cannot be revoked (status: {record.status})"
        )

    await revoke_invite_token(record.token)
    record.status = InviteTokenStatus.REVOKED
    await session.flush()


async def resend_invite(token_id: int, session: AsyncSession) -> None:
    """Generate a fresh token for an existing invite and resend the email."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.id == token_id)  # type: ignore[arg-type]
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise InviteNotFoundError(f"Invite token with ID {token_id} not found")
    if record.status == InviteTokenStatus.USED:
        raise InviteAlreadyRevokedError(
            f"Invite {token_id} has already been used and cannot be resent"
        )

    await revoke_invite_token(record.token)
    new_token, new_expires_at = await generate_invite_token()
    record.token = new_token
    record.expires_at = new_expires_at
    record.status = InviteTokenStatus.PENDING
    await session.flush()

    registration_url = f"{settings.frontend_base_url}/register?token={new_token}"
    contact_name = (
        " ".join(filter(None, [record.contact_first_name, record.contact_last_name]))
        or None
    )
    email_body = _build_invite_email(
        contact_name, record.company_name, record.note, registration_url
    )

    await enqueue_email_task(
        to=record.email,
        subject="הזמנה להרשמה ל-RS Recruiting",
        body=email_body,
    )
