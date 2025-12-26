# Dockerfile for local development with hot reload
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV
RUN uv sync --frozen --no-dev

# The source code will be mounted as a volume for hot reload
# No COPY of source code here - we mount it instead

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/healthcheck || exit 1

# Run uvicorn with hot reload using UV
CMD ["uv", "run", "uvicorn", "unifiedui.app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
