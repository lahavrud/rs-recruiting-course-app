# Shared base/builder image for all RS Recruitment services.
#
# Provides the Python runtime, uv, gosu, and a non-root app user — but installs
# NO project dependencies. Each service Dockerfile (services/<svc>/Dockerfile)
# builds FROM this and runs its own lean `uv sync --package <member>`, so the
# per-service images stay minimal and their dependency closures don't overlap
# (the worker image never installs the FastAPI/uvicorn/slowapi web stack).
#
# Why deps are NOT synced here: the api and worker have different (lean) closures,
# and removing files in a later layer doesn't shrink an image. Installing per
# service in its own layers is what actually keeps each image small. This base is
# the shared *toolchain* layer; uv's download cache is what's reused across builds.
#
# Build first, from the repo root:
#   docker build -f docker/base.Dockerfile -t rs-recruiting-base:local .
FROM python:3.12-slim

# uv for dependency management (pinned; matches the tooling behind uv.lock).
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /usr/local/bin/uv

# gosu lets the entrypoint drop from root to the app user with correct signal
# forwarding (needed for the worker's graceful SIGTERM handling).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user. UID/GID overridable via build args to match the host.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -r -g ${APP_GID} appuser \
    && useradd -r -u ${APP_UID} -g appuser -d /app -s /bin/bash appuser

WORKDIR /app

# uv: copy into the image layer (no hardlinks across mounts), precompile bytecode
# for faster cold starts, and never fetch a managed Python — use the slim image's.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
