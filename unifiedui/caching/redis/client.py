"""Redis cache client implementation."""

from unifiedui.caching.redis.cache import RedisCache
from unifiedui.core.caching.cache import BaseCache
from unifiedui.core.caching.client import BaseCacheClient
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class RedisCacheClient(BaseCacheClient):
    """Redis implementation of cache client."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        default_ttl: int = 3600,
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
        self._cache = RedisCache(host=host, port=port, db=db, password=password, default_ttl=default_ttl)
        logger.info("Redis cache client initialized")

    def get_cache(self) -> BaseCache:
        """Get the underlying Redis cache instance."""
        return self._cache
