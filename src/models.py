from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "ADMIN"
    COMPANY = "COMPANY"


class User(SQLModel, table=True):
    """Authenticated user entity (Admins & Companies).

    Users authenticate and log in. Candidates do NOT use this model.
    """

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole
    is_active: bool = Field(default=False, description="False until Admin approves")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationship to CompanyProfile (optional, only for COMPANY role)
    # Note: ADMIN users don't have CompanyProfile, so this can be None
    company_profile: CompanyProfile = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False},
    )


class CompanyProfile(SQLModel, table=True):
    """Company profile linked to a User.

    One-to-one relationship with User (for COMPANY role users).
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    name: str
    logo_url: str | None = None
    contact_person: str | None = None
    contact_phone: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationship to User
    user: User = Relationship(back_populates="company_profile")
