"""Cache dependency for FastAPI handlers."""

import os

from unifiedui.caching.client import CacheClient, CacheClientFactory
from unifiedui.logger import get_logger

logger = get_logger(__name__)

# Global cache client instance
_cache_client: CacheClient | None = None
_cache_initialized: bool = False


def get_cache_client() -> CacheClient | None:
    """
    Get the global cache client instance.

    Cache is optional - returns None if not configured.
    Reads configuration from environment variables:
    - CACHE_ENABLED (true/false) - if false or missing, returns None
    - CACHE_BACKEND (REDIS, etc.)
    - Redis specific: REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, CACHE_DEFAULT_TTL

    Returns:
        CacheClient instance or None if cache is not enabled/configured
    """
    global _cache_client, _cache_initialized

    # Only try initialization once
    if _cache_initialized:
        return _cache_client

    _cache_initialized = True

    # Check if cache is enabled
    cache_enabled = os.getenv("CACHE_ENABLED", "false").lower() in ("true", "1", "yes")

    if not cache_enabled:
        logger.info("Cache is disabled (CACHE_ENABLED not set to true)")
        return None

    # Check if cache backend is configured
    cache_backend = os.getenv("CACHE_BACKEND")
    if not cache_backend:
        logger.warning("Cache is enabled but CACHE_BACKEND is not configured")
        return None

    try:
        _cache_client = CacheClientFactory.create()
        logger.info("Cache client initialized successfully (%s)", cache_backend)
    except Exception as e:
        logger.warning("Failed to initialize cache client: %s. Continuing without cache.", e)
        _cache_client = None

    return _cache_client
