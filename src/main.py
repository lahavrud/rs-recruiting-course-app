from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import auth
from src.core.infrastructure.config import settings
from src.core.infrastructure.database import init_db
from src.core.tasks import close_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup/shutdown events."""
    # Initialize database on startup
    await init_db()
    # Note: Redis pool is initialized lazily when first task is enqueued
    # This allows the app to start even if Redis is temporarily unavailable
    yield
    # Cleanup Redis connection pool on shutdown
    await close_redis_pool()


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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
