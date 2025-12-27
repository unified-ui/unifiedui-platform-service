"""FastAPI dependencies for handlers.

This package provides dependency injection functions for:
- Database clients (required)
- Cache clients (optional)
- Vault clients (optional)
- Handler instances (TenantHandler, CustomGroupHandler, CredentialHandler, etc.)

All dependencies are initialized lazily and cached globally.
"""

# Database dependencies
from unifiedui.handlers.dependencies.database import get_db_client

# Cache dependencies
from unifiedui.handlers.dependencies.cache import get_cache_client

# Vault dependencies
from unifiedui.handlers.dependencies.vault import get_vault_client

# Handler dependencies
from unifiedui.handlers.dependencies.tenants import get_tenant_handler
from unifiedui.handlers.dependencies.custom_groups import get_custom_group_handler
from unifiedui.handlers.dependencies.credentials import get_credential_handler
from unifiedui.handlers.dependencies.applications import get_application_handler
from unifiedui.handlers.dependencies.conversations import get_conversation_handler
from unifiedui.handlers.dependencies.autonomous_agents import get_autonomous_agent_handler
from unifiedui.handlers.dependencies.development_platforms import get_development_platform_handler
from unifiedui.handlers.dependencies.chat_widgets import get_chat_widget_handler
from unifiedui.handlers.dependencies.tags import get_tag_handler
from unifiedui.handlers.dependencies.user_favorites import get_user_favorites_handler
from unifiedui.handlers.dependencies.resource_permissions import get_resource_permissions_handler
from unifiedui.handlers.dependencies.resource_tags import get_resource_tags_handler

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
    # Central Handlers
    "get_resource_permissions_handler",
    "get_resource_tags_handler",
]

