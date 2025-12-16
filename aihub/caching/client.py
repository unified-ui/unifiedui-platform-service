"""Cache client wrapper and factory for dependency injection."""
import os
from typing import Optional

from aihub.core.caching.client import BaseCacheClient
from aihub.core.caching.collections.tenants import TenantsCacheCollection
from aihub.caching.enums import CacheTypeEnum
from aihub.caching.redis.client import RedisCacheClient


class CacheClient:
    """
    Wrapper class for cache client.
    Provides a consistent interface regardless of the underlying cache implementation.
    """

    def __init__(self, cache_client: BaseCacheClient):
        """
        Initialize cache client wrapper.
        
        Args:
            cache_client: Underlying cache client implementation (e.g., RedisCacheClient)
        """
        self._client = cache_client

    @property
    def tenants(self) -> TenantsCacheCollection:
        """Get the tenants cache collection."""
        return self._client.tenants()

    def close(self) -> None:
        """Close cache client connection."""
        self._client.close()

    def ping(self) -> bool:
        """Check if cache connection is alive."""
        return self._client.ping()


class CacheClientFactory:
    """
    Factory class for creating cache clients based on the cache type.
    Currently supports Redis.
    """

    @staticmethod
    def create(
        cache_type: Optional[CacheTypeEnum] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        default_ttl: Optional[int] = None
    ) -> CacheClient:
        """
        Create a cache client based on the specified type.
        
        Args:
            cache_type: Type of cache (REDIS).
                        If not provided, reads from CACHE_BACKEND env var.
            host: Cache server host.
                  If not provided, reads from environment variables.
            port: Cache server port.
                  If not provided, reads from environment variables.
            db: Database number (for Redis).
                If not provided, reads from environment variables.
            password: Cache server password.
                      If not provided, reads from environment variables.
            default_ttl: Default time-to-live in seconds.
                         If not provided, reads from environment variables.
        
        Returns:
            An instance of CacheClient wrapping the specific implementation.
        
        Raises:
            ValueError: If cache_type is invalid or not supported.
            RuntimeError: If required configuration is missing.
        """
        # Determine cache type
        if cache_type is None:
            cache_type_str = os.getenv("CACHE_BACKEND", "REDIS")
            try:
                cache_type = CacheTypeEnum(cache_type_str)
            except ValueError:
                raise ValueError(
                    f"Invalid CACHE_BACKEND value: {cache_type_str}. "
                    f"Valid values are: {', '.join([e.value for e in CacheTypeEnum])}"
                )

        # Create underlying client based on type
        if cache_type == CacheTypeEnum.REDIS:
            underlying_client = CacheClientFactory._create_redis_client(
                host, port, db, password, default_ttl
            )
        else:
            raise ValueError(f"Unsupported cache type: {cache_type}")
        
        # Wrap in CacheClient
        return CacheClient(underlying_client)

    @staticmethod
    def _create_redis_client(
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        default_ttl: Optional[int] = None
    ) -> RedisCacheClient:
        """Create a Redis client with the given configuration."""
        # Get host
        if host is None:
            host = os.getenv("REDIS_HOST", "localhost")

        # Get port
        if port is None:
            port = int(os.getenv("REDIS_PORT", "6379"))

        # Get database number
        if db is None:
            db = int(os.getenv("REDIS_DB", "0"))

        # Get password
        if password is None:
            password = os.getenv("REDIS_PASSWORD")

        # Get default TTL
        if default_ttl is None:
            default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))

        client = RedisCacheClient(
            host=host,
            port=port,
            db=db,
            password=password,
            default_ttl=default_ttl
        )
        
        return client


# Convenience function for creating a cache client
def get_cache_client(
    cache_type: Optional[CacheTypeEnum] = None
) -> CacheClient:
    """
    Convenience function to create and return a cache client.
    
    Usage:
        # Using environment variables
        cache_client = get_cache_client()
        
        # Explicitly specifying type
        cache_client = get_cache_client(CacheTypeEnum.REDIS)
    """
    return CacheClientFactory.create(cache_type=cache_type)
