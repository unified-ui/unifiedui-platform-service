"""Redis implementation for Tenants cache collection."""
from typing import Optional, List
from urllib.parse import quote

from aihub.core.caching.collections.tenants import TenantsCacheCollection
from aihub.caching.redis.cache import RedisCache
from aihub.schema.responses.tenants import TenantResponse
from aihub.logger import get_logger

logger = get_logger(__name__)


class RedisTenantsCacheCollection(TenantsCacheCollection):
    """Redis implementation for Tenants cache."""

    def __init__(self, cache: RedisCache):
        """
        Initialize Redis tenants cache collection.
        
        Args:
            cache: Redis cache instance
        """
        self.cache = cache

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
        """Get a single tenant from cache."""
        key = self.build_key(tenant_id, user_id, route)
        data = self.cache.get(key)
        
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
        """Cache a single tenant."""
        key = self.build_key(tenant_id, user_id, route)
        data = tenant.model_dump()
        self.cache.set(key, data, ttl)

    def get_tenant_list(
        self,
        user_id: str,
        route: str
    ) -> Optional[List[TenantResponse]]:
        """Get tenant list from cache."""
        key = self.build_key(None, user_id, route)
        data = self.cache.get(key)
        
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
        """Cache a tenant list."""
        key = self.build_key(None, user_id, route)
        data = [tenant.model_dump() for tenant in tenants]
        self.cache.set(key, data, ttl)

    def invalidate_tenant(
        self,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> int:
        """Invalidate all cache entries for a specific tenant."""
        if user_id:
            # Invalidate specific user's cache for this tenant
            pattern = f"tenant:{tenant_id}:user:{user_id}:*"
        else:
            # Invalidate all users' cache for this tenant
            pattern = f"tenant:{tenant_id}:*"
        
        deleted = self.cache.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted} cache entries for tenant {tenant_id}")
        return deleted

    def invalidate_user(
        self,
        user_id: str
    ) -> int:
        """Invalidate all cache entries for a specific user."""
        pattern = f"tenant:*:user:{user_id}:*"
        deleted = self.cache.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted} cache entries for user {user_id}")
        return deleted

    def invalidate_all(self) -> int:
        """Invalidate all tenant cache entries."""
        pattern = "tenant:*"
        deleted = self.cache.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted} tenant cache entries")
        return deleted