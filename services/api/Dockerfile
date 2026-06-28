# API image — the FastAPI HTTP service.
#
# FROM the shared base; installs the api member (rs-recruiting-api ->
# rs-recruiting-shared) plus the web stack (fastapi, uvicorn, slowapi, ...).
#
# Multi-stage: the builder resolves + installs into a self-contained venv; the
# runtime copies only that venv, so uv's wheel cache (kept in the builder stage)
# never bloats the shipped image. Works on the legacy Docker builder — no
# BuildKit required. Build (after the base), from the repo root:
#   docker build -f docker/base.Dockerfile -t rs-recruiting-base:local .
#   docker build -f services/api/Dockerfile -t rs-recruiting-api:local .
ARG BASE_IMAGE=rs-recruiting-base:local

# ---------- builder: resolve deps + install into /app/.venv ----------
FROM ${BASE_IMAGE} AS builder

# Dependency layer — Docker-layer-cached until uv.lock or a manifest changes.
COPY pyproject.toml uv.lock ./
COPY libs/shared/pyproject.toml libs/shared/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/worker/pyproject.toml services/worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package rs-recruiting-api

# Source + install workspace packages as wheels (--no-editable) so /app/.venv is
# fully self-contained (no source tree needed at runtime).
COPY libs/shared/ libs/shared/
COPY services/api/ services/api/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package rs-recruiting-api

# ---------- runtime: venv + migrations + ops scripts + article content ----------
FROM ${BASE_IMAGE} AS runtime
COPY --from=builder /app/.venv /app/.venv

# The API image runs `alembic upgrade` at deploy time; alembic (in the venv)
# reads alembic.ini + alembic/ and imports rs_shared from the installed venv.
COPY alembic/ alembic/
COPY alembic.ini ./
COPY scripts/ scripts/

# The SEO prerender renders the same article markdown the SPA builds from.
# Copy it to /app/articles (see rs_api/api/seo/_articles.py — _DOCKER_PATH).
COPY frontend/src/content/articles/ /app/articles/

# Local storage / sqlite data dir, writable by the non-root app user.
RUN mkdir -p /app/data \
    && chown -R appuser:appuser /app/data \
    && chmod 755 /app/data

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown root:root /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
# --proxy-headers: honour X-Forwarded-* from the reverse proxy. Set
# FORWARDED_ALLOW_IPS to the LB's private CIDR in prod so rate limiting and IP
# audit see the real client IP, not the proxy's (see core dependencies.client_ip).
CMD ["uvicorn", "rs_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
