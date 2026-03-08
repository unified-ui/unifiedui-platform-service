from abc import ABC, abstractmethod
from typing import Any


class BaseCache(ABC):
    """Abstract base class for caching mechanisms."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Retrieve a value from the cache by key.

        Args:
            key (str): The key to look up in the cache.
        Returns:
            Optional[Any]: The value associated with the key, or None if not found.

        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in the cache with an optional time-to-live.

        Args:
            key (str): The key under which to store the value.
            value (Any): The value to store in the cache.
            ttl (Optional[int]): Time-to-live in seconds. If None, the value does not expire.

        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a key from the cache.

        Args:
            key (str): The key to delete.
        Returns:
            bool: True if deleted, False otherwise.

        """
        pass

    @abstractmethod
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern (str): Key pattern (e.g., "tenant:*").
        Returns:
            int: Number of keys deleted.

        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """Check if cache connection is alive.

        Returns:
            bool: True if connected, False otherwise.

        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the cache client connection."""
        pass
