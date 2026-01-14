"""Application configuration."""

from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # JWT Configuration
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/rs_recruitment.db"

    # AWS Configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"

    # Storage Configuration
    storage_provider: Literal["s3", "local"] = "local"
    aws_s3_bucket_name: Optional[str] = None
    aws_s3_endpoint_url: Optional[str] = None  # For MinIO or S3-compatible services
    local_storage_path: str = "./storage"

    # Email Configuration
    email_provider: Literal["ses", "smtp"] = "smtp"
    aws_ses_from_email: Optional[str] = None
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    smtp_from_email: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
