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

# Install Python dependencies directly
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi>=0.124.0 \
    redis>=7.1.0 \
    requests>=2.32.5 \
    uvicorn>=0.38.0 \
    sqlalchemy>=2.0.0 \
    alembic>=1.13.0 \
    psycopg2-binary>=2.9.9 \
    hvac>=2.4.0 \
    azure-keyvault>=4.2.0 \
    pytest-asyncio>=1.3.0 \
    pydantic>=2.0.0 \
    pydantic-settings>=2.0.0 \
    fakeredis>=2.33.0 \
    pyjwt>=2.8.0 \
    azure-identity>=1.25.1 \
    pymongo>=4.0.0 \
    watchfiles

# The source code will be mounted as a volume for hot reload
# No COPY of source code here - we mount it instead

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/healthcheck || exit 1

# Run uvicorn with hot reload
CMD ["uvicorn", "unifiedui.app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
