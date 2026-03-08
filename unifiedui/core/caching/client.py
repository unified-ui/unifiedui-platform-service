"""Abstract base class for cache client."""

from abc import ABC, abstractmethod
from typing import Any

from unifiedui.core.caching.cache import BaseCache


class BaseCacheClient(ABC):
    """
    Abstract base class for cache client.
    Provides low-level cache operations.
    """

    @abstractmethod
    def get_cache(self) -> BaseCache:
        """
        Get the underlying cache instance.

        Returns:
            BaseCache instance
        """
        pass

    def get(self, key: str) -> Any | None:
        """
        Get a value from the cache by key.

        Args:
            key: Cache key
        Returns:
            Cached value or None if not found
        """
        return self.get_cache().get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Set a value in the cache with an optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (optional)
        """
        self.get_cache().set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Args:
            key: Cache key
        Returns:
            True if deleted, False otherwise
        """
        return self.get_cache().delete(key)

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "tenant:*")
        Returns:
            Number of keys deleted
        """
        return self.get_cache().delete_pattern(pattern)

    def close(self) -> None:
        """
        Close the cache client connection.
        """
        self.get_cache().close()

    def ping(self) -> bool:
        """
        Check if cache connection is alive.

        Returns:
            True if connected, False otherwise
        """
        return self.get_cache().ping()
