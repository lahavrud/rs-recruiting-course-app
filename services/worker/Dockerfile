# Worker image — consumes the SQS task queue and dispatches via TASK_REGISTRY.
#
# FROM the shared base; installs ONLY the worker member
# (rs-recruiting-worker -> rs-recruiting-shared). The FastAPI / uvicorn / slowapi
# web stack is therefore never present — enforced by
# tests/test_domain_is_framework_free.py.
#
# Multi-stage: the builder resolves + installs into a self-contained venv; the
# runtime copies only that venv, so uv's wheel cache (kept in the builder stage)
# never bloats the shipped image. Works on the legacy Docker builder — no
# BuildKit required. Build (after the base), from the repo root:
#   docker build -f docker/base.Dockerfile -t rs-recruiting-base:local .
#   docker build -f services/worker/Dockerfile -t rs-recruiting-worker:local .
ARG BASE_IMAGE=rs-recruiting-base:local

# ---------- builder: resolve deps + install into /app/.venv ----------
FROM ${BASE_IMAGE} AS builder

# Dependency layer — Docker-layer-cached until uv.lock or a manifest changes.
# All member manifests are copied so uv can resolve the workspace; only the
# worker's closure is installed.
COPY pyproject.toml uv.lock ./
COPY libs/shared/pyproject.toml libs/shared/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/worker/pyproject.toml services/worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package rs-recruiting-worker

# Source + install workspace packages as wheels (--no-editable) so /app/.venv is
# fully self-contained (package data — email templates, logo — ships inside it).
COPY libs/shared/ libs/shared/
COPY services/worker/ services/worker/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package rs-recruiting-worker

# ---------- runtime: ship only the venv ----------
FROM ${BASE_IMAGE} AS runtime
COPY --from=builder /app/.venv /app/.venv

# The entrypoint fixes /app/data perms (if mounted) and drops to appuser via
# gosu, preserving signal forwarding so SIGTERM reaches the worker loop.
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown root:root /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
# Graceful SIGTERM (finish in-flight batch, then exit) lives in
# rs_worker.worker:main. `rs-worker` is the console script declared by the member.
CMD ["rs-worker"]
