"""Abstract base class for cache client."""
from abc import ABC, abstractmethod

from aihub.core.caching.collections.tenants import TenantsCacheCollection


class BaseCacheClient(ABC):
    """
    Abstract base class for cache client.
    Provides access to collection-specific cache interfaces.
    """

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