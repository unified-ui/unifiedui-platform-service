"""Cache dependencies for dependency injection."""

from functools import lru_cache

from unifiedui.caching.client import CacheClient
from unifiedui.caching.client import get_cache_client as create_cache_client
from unifiedui.core.config import settings
from unifiedui.logger import get_logger

logger = get_logger(__name__)


# Global cache client instance
_cache_client: CacheClient | None = None


@lru_cache
def get_cache_client() -> CacheClient | None:
    """
    Get or create a singleton cache client instance.
    Returns None if caching is disabled.

    This function is cached to ensure only one cache connection
    is created and reused across the application.

    Returns:
        CacheClient instance or None
    """
    global _cache_client

    if not settings.cache_enabled:
        logger.info("Cache is disabled")
        return None

    if _cache_client is None:
        try:
            _cache_client = create_cache_client()
            logger.info("Cache client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cache client: {e}")
            return None

    return _cache_client


def close_cache_client() -> None:
    """
    Close the cache client connection.
    Should be called on application shutdown.
    """
    global _cache_client

    if _cache_client is not None:
        try:
            _cache_client.close()
            logger.info("Cache client closed")
        except Exception as e:
            logger.error(f"Error closing cache client: {e}")
        finally:
            _cache_client = None
            # Clear the lru cache
            get_cache_client.cache_clear()
