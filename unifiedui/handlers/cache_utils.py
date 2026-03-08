"""Cache invalidation utilities for resource handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient

logger = get_logger(__name__)


class ResourceCacheInvalidator:
    """Reusable cache invalidation for resource handlers.

    Centralizes the standard list/detail/permissions cache invalidation
    pattern used across multiple resource handlers.

    Args:
        cache_client: Optional CacheClient wrapper instance.
        prefix: Cache key prefix (e.g. ``"chat_agents"``, ``"tools"``).
        resource_key: Short key used in detail/permissions cache keys
            (e.g. ``"chat_agent"``, ``"tool"``).
    """

    def __init__(
        self,
        cache_client: CacheClient | None,
        prefix: str,
        resource_key: str,
    ) -> None:
        self._cache_client = cache_client
        self._prefix = prefix
        self._resource_key = resource_key

    def invalidate_list(self, tenant_id: str) -> None:
        """Invalidate all list cache entries for a tenant."""
        if self._cache_client:
            self._cache_client.client.delete_pattern(f"{self._prefix}:list:tenant:{tenant_id}:*")

    def invalidate_detail(self, tenant_id: str, resource_id: str) -> None:
        """Invalidate the detail cache entry for a specific resource."""
        if self._cache_client:
            cache_key = f"{self._prefix}:detail:tenant:{tenant_id}:{self._resource_key}:{resource_id}"
            self._cache_client.client.delete(cache_key)

    def invalidate_permissions(self, tenant_id: str, resource_id: str) -> None:
        """Invalidate all permissions cache entries for a specific resource."""
        if self._cache_client:
            self._cache_client.client.delete_pattern(
                f"{self._prefix}:permissions:tenant:{tenant_id}:{self._resource_key}:{resource_id}:*"
            )
