FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies using uv (much faster than pip)
RUN uv pip install --system --no-cache -r requirements.txt

# Install gosu for switching to non-root user in entrypoint
RUN apt-get update && \
    apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Copy entrypoint script and make it executable and secure
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chown root:root /usr/local/bin/docker-entrypoint.sh

# Create non-root user for running the application
# UID/GID can be overridden via build args to match host user
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -r -g ${APP_GID} appuser && \
    useradd -r -u ${APP_UID} -g appuser -d /app -s /bin/bash appuser

# Create data directory for SQLite database and set permissions
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app/data && \
    chmod 755 /app/data

EXPOSE 8000

# Use entrypoint script to fix permissions at runtime and switch to non-root user
# The entrypoint runs as root to fix permissions, then switches to appuser
ENTRYPOINT ["docker-entrypoint.sh"]

# --proxy-headers: Trust X-Forwarded-* headers from reverse proxy (Docker, nginx, etc.)
# This ensures rate limiting uses the real client IP, not the proxy IP
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
