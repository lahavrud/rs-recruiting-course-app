"""Core module for cross-cutting infrastructure concerns.

Structure:
- `core/infrastructure/` - Pure infrastructure (config, database, security,
  limiter, dependencies)
- `core/services/` - Infrastructure services for external systems (email, storage)

NOTE: this barrel deliberately does NOT re-export the FastAPI/slowapi-coupled
modules (`infrastructure.dependencies`, `infrastructure.limiter`). Python runs
this `__init__` on *any* `rs_shared.core.*` import, so re-exporting them here would
drag the whole web stack into the worker process. Import those from their
submodules in the API layer instead.
"""

# Re-export infrastructure modules for backward compatibility
from rs_shared.core.infrastructure.config import (
    Settings,
    get_jwt_secret_key,
    settings,
    validate_settings,
)
from rs_shared.core.infrastructure.database import (
    DATABASE_URL,
    async_session,
    engine,
    get_session,
    init_db,
)
from rs_shared.core.infrastructure.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    is_password_valid,
)

# Re-export infrastructure services
from rs_shared.core.services.email import (
    EmailProvider,
    SESEmailProvider,
    SMTPEmailProvider,
    get_email_provider,
)
from rs_shared.core.services.storage import StorageProvider, get_storage_provider
from rs_shared.core.services.storage_local import LocalStorageProvider
from rs_shared.core.services.storage_s3 import S3StorageProvider

__all__ = [
    # Config
    "Settings",
    "settings",
    "get_jwt_secret_key",
    "validate_settings",
    # Database
    "DATABASE_URL",
    "engine",
    "async_session",
    "get_session",
    "init_db",
    # Security
    "create_access_token",
    "decode_access_token",
    "get_password_hash",
    "is_password_valid",
    # Email
    "EmailProvider",
    "SESEmailProvider",
    "SMTPEmailProvider",
    "get_email_provider",
    # Storage
    "StorageProvider",
    "LocalStorageProvider",
    "S3StorageProvider",
    "get_storage_provider",
]
