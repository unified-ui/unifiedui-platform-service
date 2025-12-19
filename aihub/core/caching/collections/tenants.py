"""Abstract interface for Tenants cache collection."""
from abc import ABC, abstractmethod
from typing import Optional, List
from urllib.parse import quote

from aihub.schema.responses.tenants import TenantResponse


class TenantsCacheCollection(ABC):
    """
    Abstract base class for Tenants cache operations.
    Handles caching of tenant data per user and route.
    """

    def build_key(
        self,
        tenant_id: Optional[str],
        user_id: str,
        route: str
    ) -> str:
        """
        Build cache key: tenant:{tenantID}:user:{userID}:route:{route}
        """
        # URL-encode route to handle query params
        encoded_route = quote(route, safe='')
        
        if tenant_id:
            return f"tenant:{tenant_id}:user:{user_id}:route:{encoded_route}"
        else:
            return f"tenant:list:user:{user_id}:route:{encoded_route}"

    @abstractmethod
    def get_tenant(
        self,
        tenant_id: str,
        user_id: str,
        route: str
    ) -> Optional[TenantResponse]:
        """
        Get a single tenant from cache.
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            route: Request route including query params
            
        Returns:
            Cached tenant or None
        """
        pass

    @abstractmethod
    def set_tenant(
        self,
        tenant_id: str,
        user_id: str,
        route: str,
        tenant: TenantResponse,
        ttl: Optional[int] = None
    ) -> None:
        """
        Cache a single tenant.
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            route: Request route including query params
            tenant: Tenant data to cache
            ttl: Time-to-live in seconds (None = default)
        """
        pass

    @abstractmethod
    def get_tenant_list(
        self,
        user_id: str,
        route: str
    ) -> Optional[List[TenantResponse]]:
        """
        Get tenant list from cache.
        
        Args:
            user_id: User ID
            route: Request route including query params
            
        Returns:
            Cached tenant list or None
        """
        pass

    @abstractmethod
    def set_tenant_list(
        self,
        user_id: str,
        route: str,
        tenants: List[TenantResponse],
        ttl: Optional[int] = None
    ) -> None:
        """
        Cache a tenant list.
        
        Args:
            user_id: User ID
            route: Request route including query params
            tenants: Tenant list to cache
            ttl: Time-to-live in seconds (None = default)
        """
        pass

    @abstractmethod
    def invalidate_tenant(
        self,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> int:
        """
        Invalidate all cache entries for a specific tenant.
        If user_id is provided, only invalidate for that user.
        
        Args:
            tenant_id: Tenant ID
            user_id: Optional user ID to limit invalidation
            
        Returns:
            Number of keys deleted
        """
        pass

    @abstractmethod
    def invalidate_user(
        self,
        user_id: str
    ) -> int:
        """
        Invalidate all cache entries for a specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of keys deleted
        """
        pass

    @abstractmethod
    def invalidate_all(self) -> int:
        """
        Invalidate all tenant cache entries.
        
        Returns:
            Number of keys deleted
        """
        pass