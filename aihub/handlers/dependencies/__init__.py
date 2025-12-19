"""FastAPI dependencies for handlers.

This package provides dependency injection functions for:
- Database clients (required)
- Cache clients (optional)
- Handler instances (TenantHandler, CustomGroupHandler, etc.)

All dependencies are initialized lazily and cached globally.
"""

# Database dependencies
from aihub.core.handlers.dependencies.database import get_db_client

# Cache dependencies
from aihub.core.handlers.dependencies.cache import get_cache_client

# Handler dependencies
from aihub.core.handlers.dependencies.tenants import get_tenant_handler
from aihub.core.handlers.dependencies.custom_groups import get_custom_group_handler

__all__ = [
    # Database
    "get_db_client",
    # Cache
    "get_cache_client",
    # Handlers
    "get_tenant_handler",
    "get_custom_group_handler",
]
