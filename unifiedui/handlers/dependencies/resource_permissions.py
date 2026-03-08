"""Dependency for ResourcePermissionsHandler."""

from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler


def get_resource_permissions_handler() -> ResourcePermissionsHandler:
    """Get ResourcePermissionsHandler instance."""
    return ResourcePermissionsHandler(db_client=get_db_client(), cache_client=get_cache_client())
