"""Redis cache client implementation."""
from typing import Optional, Any

from aihub.core.caching.client import BaseCacheClient
from aihub.caching.redis.cache import RedisCache
from aihub.caching.redis.collections.tenants import RedisTenantsCacheCollection
from aihub.core.caching.collections.tenants import TenantsCacheCollection
from aihub.logger import get_logger

logger = get_logger(__name__)


class RedisCacheClient(BaseCacheClient):
    """Redis implementation of cache client."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600
    ):
        """
        Initialize Redis cache client.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            default_ttl: Default TTL in seconds
        """
        self._cache = RedisCache(
            host=host,
            port=port,
            db=db,
            password=password,
            default_ttl=default_ttl
        )
        self._tenants_cache = RedisTenantsCacheCollection(self._cache)
        logger.info("Redis cache client initialized")

    def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis cache by key."""
        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in Redis cache with an optional TTL."""
        self._cache.set(key, value, ttl=ttl)

    def tenants(self) -> TenantsCacheCollection:
        """Get the tenants cache collection."""
        return self._tenants_cache

    def close(self) -> None:
        """Close Redis connection."""
        self._cache.close()

    def ping(self) -> bool:
        """Check if Redis connection is alive."""
        return self._cache.ping()