"""Invite token schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from rs_shared.enums import InviteTokenStatus


class InviteTokenCreate(BaseModel):
    """Admin input for creating an invite — email only."""

    email: EmailStr = Field(..., max_length=255)


class InviteTokenRead(BaseModel):
    """Full invite record returned to admin."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token_hash: str
    email: str
    company_name: str | None
    contact_first_name: str | None
    contact_last_name: str | None
    note: str | None
    status: InviteTokenStatus
    created_by_admin_id: int
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None


class InviteMetadataPublic(BaseModel):
    """Safe pre-fill data returned to the registration page."""

    model_config = ConfigDict(from_attributes=True)

    email: str
