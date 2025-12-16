"""Abstract base class for cache client."""
from abc import ABC, abstractmethod
from typing import Any, Optional

from aihub.core.caching.collections.tenants import TenantsCacheCollection


class BaseCacheClient(ABC):
    """
    Abstract base class for cache client.
    Provides access to collection-specific cache interfaces.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache by key.
        
        Args:
            key: Cache key
        Returns:
            Cached value or None if not found
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Set a value in the cache with an optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (optional)
        """
        pass

    @abstractmethod
    def tenants(self) -> TenantsCacheCollection:
        """
        Get the tenants cache collection.
        
        Returns:
            TenantsCacheCollection instance
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the cache client connection.
        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """
        Check if cache connection is alive.
        
        Returns:
            True if connected, False otherwise
        """
        pass