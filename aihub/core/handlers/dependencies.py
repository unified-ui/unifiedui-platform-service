"""FastAPI dependencies for handlers."""
from typing import Optional
from fastapi import Depends

from aihub.database.client import DatabaseClient
from aihub.database.dependencies import get_db_client
from aihub.caching.client import CacheClient
from aihub.caching.dependencies import get_cache_client
from aihub.core.handlers.tenants import TenantHandler


def get_tenant_handler(
    db_client: DatabaseClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> TenantHandler:
    """
    Get a TenantHandler instance as a dependency.
    
    Args:
        db_client: Database client dependency
        cache_client: Cache client dependency (optional)
        
    Returns:
        TenantHandler instance
    """
    return TenantHandler(db_client, cache_client)
