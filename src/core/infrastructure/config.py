"""Application configuration."""

from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # JWT Configuration
    jwt_secret_key: Optional[str] = None  # Must be set via environment variable
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # CORS Configuration (infra8 requirement)
    # Can be set via ALLOWED_ORIGINS env var as comma-separated list
    # Example: ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
    allowed_origins: str = Field(default="http://localhost:3000")

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/rs_recruitment.db"
    database_echo: bool = False  # Enable SQL query logging (for debugging only)

    # Redis Configuration (for Arq task queue)
    redis_url: str = "redis://localhost:6379/0"

    # AWS Configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"

    # Storage Configuration
    storage_provider: Literal["s3", "local"] = "local"
    aws_s3_bucket_name: Optional[str] = None
    aws_s3_endpoint_url: Optional[str] = None  # For MinIO or S3-compatible services
    local_storage_path: str = "./data/storage"  # Use data directory

    # Email Configuration
    email_provider: Literal["ses", "smtp"] = "smtp"
    aws_ses_from_email: Optional[str] = None
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    smtp_from_email: Optional[str] = None

    # Environment
    environment: Literal["development", "production"] = "development"

    # Testing Configuration
    testing: bool = False  # Set to True in test environment to disable rate limiting

    @field_validator("allowed_origins")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> list[str]:
        """Parse allowed_origins from comma-separated string.

        Handles:
        - Comma-separated string from environment variable
        - Empty string (falls back to default)
        """
        if not v or not v.strip():
            # Use default if not provided
            return ["http://localhost:3000"]
        # Split by comma and strip whitespace, filter empty strings
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        return origins if origins else ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


def validate_settings() -> None:
    """Validate critical settings at startup.

    Raises:
        ValueError: If critical settings are invalid
    """
    # Skip validation in test environment
    if settings.testing:
        return

    # Validate JWT secret key
    if (
        not settings.jwt_secret_key
        or settings.jwt_secret_key
        == "your-secret-key-change-in-production"  # pragma: allowlist secret
    ):
        raise ValueError(
            "JWT_SECRET_KEY must be set to a secure value via environment variable. "
            "Generate one with: python -c 'import secrets; "
            "print(secrets.token_urlsafe(32))'"
        )
    if len(settings.jwt_secret_key) < 32:
        raise ValueError(
            f"JWT_SECRET_KEY must be at least 32 characters long for security "
            f"(current length: {len(settings.jwt_secret_key)})"
        )

    # Validate email provider config
    if settings.email_provider == "ses" and not settings.aws_ses_from_email:
        raise ValueError("AWS_SES_FROM_EMAIL must be set when EMAIL_PROVIDER=ses")


def get_jwt_secret_key() -> str:
    """Get JWT secret key (validated, guaranteed non-None).

    Should only be called after validate_settings().
    """
    # After validate_settings(), jwt_secret_key is guaranteed to be set
    assert settings.jwt_secret_key is not None, "JWT_SECRET_KEY must be set"
    return settings.jwt_secret_key
