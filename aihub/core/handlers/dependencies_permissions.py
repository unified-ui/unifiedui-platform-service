"""Dependency injection for permission handler."""
from functools import lru_cache

from aihub.core.handlers.permissions import PermissionHandler
from aihub.database.dependencies import get_db_client


@lru_cache()
def get_permission_handler() -> PermissionHandler:
    """
    Get a singleton instance of the permission handler.
    
    Returns:
        PermissionHandler: Singleton permission handler instance
    """
    db_client = get_db_client()
    return PermissionHandler(db_client)
