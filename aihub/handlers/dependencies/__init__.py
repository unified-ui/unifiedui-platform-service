"""FastAPI dependencies for handlers.

This package provides dependency injection functions for:
- Database clients (required)
- Cache clients (optional)
- Vault clients (optional)
- Handler instances (TenantHandler, CustomGroupHandler, CredentialHandler, etc.)

All dependencies are initialized lazily and cached globally.
"""

# Database dependencies
from aihub.handlers.dependencies.database import get_db_client

# Cache dependencies
from aihub.handlers.dependencies.cache import get_cache_client

# Vault dependencies
from aihub.handlers.dependencies.vault import get_vault_client

# Handler dependencies
from aihub.handlers.dependencies.tenants import get_tenant_handler
from aihub.handlers.dependencies.custom_groups import get_custom_group_handler
from aihub.handlers.dependencies.credentials import get_credential_handler

__all__ = [
    # Database
    "get_db_client",
    # Cache
    "get_cache_client",
    # Vault
    "get_vault_client",
    # Handlers
    "get_tenant_handler",
    "get_custom_group_handler",
    "get_credential_handler",
]

