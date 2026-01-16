FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies using uv (much faster than pip)
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

# --proxy-headers: Trust X-Forwarded-* headers from reverse proxy (Docker, nginx, etc.)
# This ensures rate limiting uses the real client IP, not the proxy IP
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]