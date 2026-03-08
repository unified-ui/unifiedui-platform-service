'''
"""
Database client dependencies for FastAPI.
Provides a singleton instance of the database client to avoid multiple connections.
"""
from typing import Optional
from functools import lru_cache

from unifiedui.docdatabase.client import DatabaseClient, get_database_client


_db_client: Optional[DatabaseClient] = None


@lru_cache()
def get_db_client() -> DatabaseClient:
    """
    Get or create a singleton database client instance.

    This function is cached to ensure only one database connection
    is created and reused across the application.

    Returns:
        DatabaseClient: The database client instance
    """
    global _db_client

    if _db_client is None:
        _db_client = get_database_client()

    return _db_client


def close_db_client() -> None:
    """
    Close the database client connection.
    Should be called on application shutdown.
    """
    global _db_client

    if _db_client is not None:
        _db_client.disconnect()
        _db_client = None
        # Clear the cache
        get_db_client.cache_clear()
'''
