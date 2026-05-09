import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import (
    activation,
    admin_applications,
    admin_audit,
    admin_candidates,
    admin_companies,
    admin_invites,
    admin_jobs,
    admin_jobs_crud,
    auth,
    candidates,
    companies,
    invites,
    jobs_read,
    jobs_write,
    public,
    resumes,
    seo,
)
from src.core.infrastructure.config import settings, validate_settings
from src.core.infrastructure.database import init_db
from src.core.tasks import close_redis_pool


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


class _HealthCheckLogFilter(logging.Filter):
    # Route 53 polls /health every 30s, which would otherwise add ~2.8k
    # GET /health 200 lines/day to CloudWatch — pure noise that crowds out
    # real signal during incident triage.
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_HealthCheckLogFilter())


app = FastAPI(title="RS Recruitment API", lifespan=lifespan)

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
app.include_router(activation.router)
app.include_router(invites.router)
app.include_router(admin_companies.router)
app.include_router(admin_invites.router)
app.include_router(admin_jobs.router)
app.include_router(admin_jobs_crud.router)
app.include_router(admin_applications.router)
app.include_router(admin_audit.router)
app.include_router(admin_candidates.router)
app.include_router(companies.router)
app.include_router(jobs_read.router)
app.include_router(jobs_write.router)
app.include_router(public.router)
app.include_router(candidates.router)
app.include_router(candidates.jobs_apply_router)
app.include_router(resumes.router)
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
