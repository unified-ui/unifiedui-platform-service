"""Database dependency for FastAPI handlers."""

import os

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.config import DatabaseConfig

# Global SQLAlchemy client instance
_db_client: SQLAlchemyClient | None = None


def get_db_client() -> SQLAlchemyClient:
    """
    Get the global SQLAlchemy client instance.

    Reads configuration from environment variables:
    - DATABASE_URL (complete URL) OR
    - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

    Raises:
        RuntimeError: If database configuration is missing or invalid

    Returns:
        SQLAlchemyClient instance
    """
    global _db_client
    if _db_client is None:
        # Check if any database configuration exists
        database_url = os.getenv("DATABASE_URL")
        db_host = os.getenv("DB_HOST")

        if not database_url and not db_host:
            raise RuntimeError(
                "Database configuration is missing. Please set either "
                "DATABASE_URL or DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD "
                "environment variables."
            )

        try:
            config = DatabaseConfig.from_env()
            _db_client = SQLAlchemyClient(config=config)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database client: {e}") from e

    return _db_client
