import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import json as jsonlogger

from src.api import sentry_tunnel, seo
from src.api.admin import (
    applications as admin_applications,
)
from src.api.admin import (
    audit as admin_audit,
)
from src.api.admin import (
    candidates as admin_candidates,
)
from src.api.admin import (
    companies as admin_companies,
)
from src.api.admin import (
    invites as admin_invites,
)
from src.api.admin import (
    jobs as admin_jobs,
)
from src.api.auth import (
    activation,
    invites,
    password_reset,
    registration,
)
from src.api.auth import (
    login as auth,
)
from src.api.company import jobs as company_jobs
from src.api.company import profile as companies
from src.api.company import resumes
from src.api.public import applications as candidates
from src.api.public import jobs as public
from src.core.infrastructure.config import settings, validate_settings
from src.core.infrastructure.database import init_db
from src.core.infrastructure.middleware import RequestIdFilter, RequestMiddleware
from src.core.tasks import close_redis_pool

if settings.sentry_dsn:
    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            release=os.environ.get("SENTRY_RELEASE"),
            traces_sample_rate=0.0,
            send_default_pii=False,
        )
    except Exception as _sentry_err:
        # A misconfigured DSN must never crash the server.
        import logging as _logging

        _logging.getLogger(__name__).error(
            "Sentry init failed (check SENTRY_DSN in SSM): %s", _sentry_err
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup/shutdown events."""
    validate_settings()
    await init_db()
    # Note: Redis pool is initialized lazily when first task is enqueued
    # This allows the app to start even if Redis is temporarily unavailable
    yield
    # Cleanup Redis connection pool on shutdown
    await close_redis_pool()


def _configure_logging() -> None:
    """Set up JSON structured logging on the root logger.

    In production, every log line is a JSON object so CloudWatch Logs Insights
    can parse fields natively (filter level="ERROR", stats by endpoint, etc.).
    In development the same JSON format is used for consistency; pipe through
    `jq` locally if you prefer pretty output.
    """
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())


_configure_logging()


class _HealthCheckLogFilter(logging.Filter):
    # Route 53 polls /health every 30s, which would otherwise add ~2.8k
    # GET /health 200 lines/day to CloudWatch — pure noise that crowds out
    # real signal during incident triage.
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_HealthCheckLogFilter())
logging.getLogger().addFilter(RequestIdFilter())


app = FastAPI(title="RS Recruitment API", lifespan=lifespan)
app.add_middleware(RequestMiddleware)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(auth.router)
app.include_router(registration.router)
app.include_router(activation.router)
app.include_router(password_reset.router)
app.include_router(invites.router)
app.include_router(admin_companies.router)
app.include_router(admin_invites.router)
app.include_router(admin_jobs.router)
app.include_router(admin_applications.router)
app.include_router(admin_audit.router)
app.include_router(admin_candidates.router)
app.include_router(companies.router)
app.include_router(company_jobs.router)
app.include_router(public.router)
app.include_router(candidates.router)
app.include_router(candidates.jobs_apply_router)
app.include_router(resumes.router)
app.include_router(sentry_tunnel.router)
app.include_router(seo.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    from src.core.tasks import get_redis_pool

    redis_status = "ok"
    try:
        redis = await get_redis_pool()
        await redis.ping()
    except Exception:
        redis_status = "unavailable"

    overall = "ok" if redis_status == "ok" else "degraded"
    return {
        "status": overall,
        "environment": settings.environment,
        "redis": redis_status,
    }
