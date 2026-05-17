"""Authentication and user schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.enums import UserRole


def _validate_password_complexity(v: str) -> str:
    """Enforce password complexity: min 8 chars, upper, lower, digit, special."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Password must contain at least one special character")
    return v


class UserRead(BaseModel):
    """Schema for reading user data (excludes sensitive fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str


class AccessTokenResponse(BaseModel):
    """Login/refresh response — refresh token delivered via HttpOnly cookie."""

    access_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Schema for requesting a new access token using a refresh token."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Schema for requesting a password reset email.

    `email` is a plain `str` (not `EmailStr`) so malformed addresses produce
    the same 200-OK as valid ones — Pydantic's 422 on `EmailStr` would
    distinguish "well-formed unknown email" from "malformed input" and leak
    a signal back to an attacker.
    """

    email: str = Field(..., max_length=255)


class ResetPasswordRequest(BaseModel):
    """Schema for completing a password reset with a token + new password."""

    token: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)
