"""Tenants cache collection implementation."""
from typing import Optional, List
from urllib.parse import quote

from aihub.schema.responses.tenants import TenantResponse
from aihub.logger import get_logger
from aihub.core.caching.client import BaseCacheClient

logger = get_logger(__name__)


class TenantsCacheCollection:
    """
    Tenants cache operations.
    Handles caching of tenant data per user and route.
    """

    def __init__(self, cache_client: "BaseCacheClient"):
        """
        Initialize Tenants cache collection.
        
        Args:
            cache_client: Cache client instance providing get/set/delete operations
        """
        self.cache_client = cache_client

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
        key = self.build_key(tenant_id, user_id, route)
        data = self.cache_client.get(key)
        
        if data:
            try:
                return TenantResponse(**data)
            except Exception as e:
                logger.warning(f"Failed to deserialize cached tenant: {e}")
                return None
        return None

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
        key = self.build_key(tenant_id, user_id, route)
        data = tenant.model_dump()
        self.cache_client.set(key, data, ttl)

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
        key = self.build_key(None, user_id, route)
        data = self.cache_client.get(key)
        
        if data:
            try:
                return [TenantResponse(**item) for item in data]
            except Exception as e:
                logger.warning(f"Failed to deserialize cached tenant list: {e}")
                return None
        return None

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
        key = self.build_key(None, user_id, route)
        data = [tenant.model_dump() for tenant in tenants]
        self.cache_client.set(key, data, ttl)

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
        if user_id:
            # Invalidate specific user's cache for this tenant
            pattern = f"tenant:{tenant_id}:user:{user_id}:*"
        else:
            # Invalidate all users' cache for this tenant
            pattern = f"tenant:{tenant_id}:*"
        
        deleted = self.cache_client.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted} cache entries for tenant {tenant_id}")
        return deleted

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
        pattern = f"tenant:*:user:{user_id}:*"
        deleted = self.cache_client.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted} cache entries for user {user_id}")
        return deleted

    def invalidate_all(self) -> int:
        """
        Invalidate all tenant cache entries.
        
        Returns:
            Number of keys deleted
        """
        pattern = "tenant:*"
        deleted = self.cache_client.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted} tenant cache entries")
        return deleted