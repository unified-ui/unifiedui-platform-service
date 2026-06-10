"""FastAPI dependencies for handlers.

This package provides dependency injection functions for:
- Database clients (required)
- Cache clients (optional)
- Vault clients (optional)
- Handler instances (TenantHandler, CustomGroupHandler, CredentialHandler, etc.)

All dependencies are initialized lazily and cached globally.
"""

# Cache dependencies
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.chat_agents import get_chat_agent_handler
from unifiedui.handlers.dependencies.chat_widgets import get_chat_widget_handler
from unifiedui.handlers.dependencies.conversations import get_conversation_handler
from unifiedui.handlers.dependencies.credentials import get_credential_handler
from unifiedui.handlers.dependencies.custom_groups import get_custom_group_handler
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.external_apps import get_external_app_handler
from unifiedui.handlers.dependencies.files import get_file_handler
from unifiedui.handlers.dependencies.organizations import get_organization_handler
from unifiedui.handlers.dependencies.principals import get_principal_handler
from unifiedui.handlers.dependencies.resource_permissions import get_resource_permissions_handler
from unifiedui.handlers.dependencies.resource_tags import get_resource_tags_handler
from unifiedui.handlers.dependencies.tags import get_tag_handler

# Handler dependencies
from unifiedui.handlers.dependencies.tenants import get_tenant_handler
from unifiedui.handlers.dependencies.user_favorites import get_user_favorites_handler

# Vault dependencies
from unifiedui.handlers.dependencies.vault import get_vault_client

# Workflow dependencies
from unifiedui.handlers.dependencies.workflows import get_workflow_handler

__all__ = [
    # Cache
    "get_cache_client",
    "get_chat_agent_handler",
    "get_chat_widget_handler",
    "get_conversation_handler",
    "get_credential_handler",
    "get_custom_group_handler",
    # Database
    "get_db_client",
    "get_external_app_handler",
    "get_file_handler",
    "get_organization_handler",
    "get_principal_handler",
    # Central Handlers
    "get_resource_permissions_handler",
    "get_resource_tags_handler",
    "get_tag_handler",
    # Handlers
    "get_tenant_handler",
    "get_user_favorites_handler",
    # Vault
    "get_vault_client",
    # Workflows
    "get_workflow_handler",
]
