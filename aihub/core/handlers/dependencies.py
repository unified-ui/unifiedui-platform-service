"""FastAPI dependencies for handlers."""
from fastapi import Depends

from aihub.database.client import DatabaseClient
from aihub.database.dependencies import get_db_client
from aihub.core.handlers.tenants import TenantHandler


def get_tenant_handler(
    db_client: DatabaseClient = Depends(get_db_client)
) -> TenantHandler:
    """
    Get a TenantHandler instance as a dependency.
    
    Args:
        db_client: Database client dependency
        
    Returns:
        TenantHandler instance
    """
    return TenantHandler(db_client)
