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
from aihub.handlers.dependencies.applications import get_application_handler
from aihub.handlers.dependencies.conversations import get_conversation_handler
from aihub.handlers.dependencies.autonomous_agents import get_autonomous_agent_handler
from aihub.handlers.dependencies.development_platforms import get_development_platform_handler
from aihub.handlers.dependencies.chat_widgets import get_chat_widget_handler
from aihub.handlers.dependencies.tags import get_tag_handler
from aihub.handlers.dependencies.user_favorites import get_user_favorites_handler

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
    "get_application_handler",
    "get_conversation_handler",
    "get_autonomous_agent_handler",
    "get_development_platform_handler",
    "get_chat_widget_handler",
    "get_tag_handler",
    "get_user_favorites_handler",
]

