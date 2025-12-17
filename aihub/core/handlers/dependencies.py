"""FastAPI dependencies for handlers."""
from fastapi import Depends

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.config import DatabaseConfig
from aihub.core.handlers.tenants import TenantHandler
from aihub.caching.client import CacheClient

# Global SQLAlchemy client instance
_db_client: SQLAlchemyClient | None = None
_cache_client: CacheClient | None = None


def get_db_client() -> SQLAlchemyClient:
    """
    Get the global SQLAlchemy client instance.
    
    Returns:
        SQLAlchemyClient instance
    """
    global _db_client
    if _db_client is None:
        config = DatabaseConfig.from_env()
        _db_client = SQLAlchemyClient(config=config)
    return _db_client


def get_cache_client() -> CacheClient | None:
    """
    Get the global cache client instance.
    
    Returns:
        CacheClient instance or None
    """
    global _cache_client
    if _cache_client is None:
        try:
            from aihub.caching.client import CacheClientFactory
            _cache_client = CacheClientFactory.create()
        except Exception as e:
            # If cache initialization fails, log and return None
            from aihub.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Failed to initialize cache client: {e}")
            return None
    return _cache_client


def get_tenant_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: CacheClient | None = Depends(get_cache_client)
) -> TenantHandler:
    """
    Get a TenantHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        
    Returns:
        TenantHandler instance
    """
    return TenantHandler(db_client, cache_client)
