# Handlers

## Location
All handler files are in `unifiedui/handlers/`.

---

## Golden Rule: ALL business logic lives in handlers

Handlers own:
- Data retrieval and filtering
- Permission-aware list queries (join with `{resource}_members`)
- Cache read/write/invalidation
- Vault operations (secret storage/retrieval)
- Validation orchestration
- Response construction from DB models → Pydantic schemas

---

## Handler Class Template

```python
"""Business logic handlers for {resource} operations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Union

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import {Resource}, {Resource}Member
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.caching.client import CacheClient
from unifiedui.core.vault.client import BaseVaultClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler

from unifiedui.schema.requests.{resource} import Create{Resource}Request, Update{Resource}Request
from unifiedui.schema.responses.{resource} import {Resource}Response
from unifiedui.exc.{resource} import {Resource}NotFoundError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class {Resource}Handler:
    """Handler class for {resource} business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None,
        vault_client: Optional[BaseVaultClient] = None,
        permissions_handler: Optional[ResourcePermissionsHandler] = None,
        tags_handler: Optional[ResourceTagsHandler] = None
    ):
        """Initialize the {resource} handler."""
        self.db_client = db_client
        self.cache_client = cache_client
        self.vault_client = vault_client
        self._permissions_handler = permissions_handler
        self._tags_handler = tags_handler

    @property
    def permissions_handler(self) -> ResourcePermissionsHandler:
        """Get the permissions handler, creating one if needed."""
        if self._permissions_handler is None:
            from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
            self._permissions_handler = ResourcePermissionsHandler(self.db_client, self.cache_client)
        return self._permissions_handler

    @property
    def tags_handler(self) -> ResourceTagsHandler:
        """Get the tags handler, creating one if needed."""
        if self._tags_handler is None:
            from unifiedui.handlers.resource_tags import ResourceTagsHandler
            self._tags_handler = ResourceTagsHandler(self.db_client, self.cache_client)
        return self._tags_handler
```

---

## Permission-Filtered List Pattern (CRITICAL)

Every list handler:
1. Checks if user is tenant admin → if yes, returns all (no member join)
2. Otherwise collects all principal_ids (user + identity groups + custom groups) 
3. Queries with subquery on `{Resource}Member` table
4. Builds cache key with user-specific parameters

```python
def list_{resources}(self, tenant_id: str, user: ContextIdentityUser, ...):
    user_id = user.identity.get_id()
    
    # Check admin bypass
    is_admin = self._check_tenant_admin(user, tenant_id, [
        TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.{RESOURCE}_ADMIN
    ])
    
    # Collect principal IDs for permission filtering
    if not is_admin:
        identity_group_ids = [g.id for g in user.groups]
        custom_group_ids = [g.id for g in user.custom_groups]
        principal_ids = [user_id] + identity_group_ids + custom_group_ids
    
    # Build query
    query = select({Resource}).where({Resource}.tenant_id == tenant_id)
    if not is_admin:
        member_subquery = (
            select({Resource}Member.{resource}_id)
            .where(
                {Resource}Member.tenant_id == tenant_id,
                {Resource}Member.principal_id.in_(principal_ids)
            ).distinct()
        )
        query = query.where({Resource}.id.in_(member_subquery))
    
    # ... apply filters, ordering, pagination
```

---

## Central Handlers

### ResourcePermissionsHandler
**Location**: `handlers/resource_permissions.py`

Generic handler for permission CRUD on any resource type. Uses `RESOURCE_PERMISSION_CONFIG` dict.

```python
RESOURCE_PERMISSION_CONFIG = {
    "application": {
        "model": Application,
        "member_model": ApplicationMember,
        "id_field": "application_id",
        "cache_prefix": "app",
        "tenant_admin_role": TenantRolesEnum.APPLICATIONS_ADMIN,
    },
    # ... one entry per resource
}
```

Provides: `list_permissions()`, `get_permission()`, `set_permission()`, `delete_permission()`, `add_creator_permission()`

### ResourceTagsHandler
**Location**: `handlers/resource_tags.py`

Generic handler for tag operations. Uses `RESOURCE_TAG_CONFIG` dict.

Provides: `get_resource_tags()`, `set_resource_tags()`, `add_resource_tag()`, `remove_resource_tag()`

### UserFavoritesHandler
**Location**: `handlers/user_favorites.py`

Generic handler for user favorite operations. Uses `RESOURCE_FAVORITE_MAPPING` dict.

```python
RESOURCE_FAVORITE_MAPPING = {
    "applications": {"model": ApplicationUserFavorite, "id_field": "application_id"},
    "autonomous-agents": {"model": AutonomousAgentUserFavorite, "id_field": "autonomous_agent_id"},
    "chat-widgets": {"model": ChatWidgetUserFavorite, "id_field": "chat_widget_id"},
    "conversations": {"model": ConversationUserFavorite, "id_field": "conversation_id"},
    "re-act-agents": {"model": ReActAgentUserFavorite, "id_field": "re_act_agent_id"},
}
```

Provides: `list_user_favorites()`, `add_user_favorite()`, `remove_user_favorite()`

---

## Dependency Factories

Each handler has a factory in `handlers/dependencies/{resource}.py`:

```python
"""Dependency factory for {resource} handler."""
from unifiedui.handlers.{resource} import {Resource}Handler
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.vault import get_vault_client
from unifiedui.handlers.dependencies.resource_permissions import get_resource_permissions_handler
from unifiedui.handlers.dependencies.resource_tags import get_resource_tags_handler


def get_{resource}_handler() -> {Resource}Handler:
    """Create and return a {resource} handler."""
    return {Resource}Handler(
        db_client=get_db_client(),
        cache_client=get_cache_client(),
        vault_client=get_vault_client(),
        permissions_handler=get_resource_permissions_handler(),
        tags_handler=get_resource_tags_handler()
    )
```

---

## Validators

Config validators live in `handlers/validators/`. Used to validate runtime configs before saving.

| Validator | Purpose |
|-----------|---------|
| `ApplicationConfigValidatorFactory` | Validates N8N / Foundry / REST API configs |
| `AutonomousAgentConfigValidator` | Validates autonomous agent configs |
| `CredentialValidator` | Validates credential data |
| `ToolValidator` | Validates tool (MCP / OpenAPI) configs |
| `TenantAIModelValidator` | Validates AI model provider configs |

---

## Non-Standard Handler: TenantAIModelHandler

Unlike standard resource handlers, `TenantAIModelHandler` does **not** use RBAC member filtering:

- No `{Resource}Member` table — AI models are tenant-scoped, not user-scoped
- CRUD endpoints use `@authenticate()` with tenant admin check (no `@check_permissions`)
- S2S endpoint `get_models_by_purpose()` uses `@authenticate_service_key()` — no user context
- Resolves credential secrets from vault with JSON fallback: `{"api_key": secret_str}`
- Has a dedicated dependency: `handlers/dependencies/tenant_ai_models.py`

---

## Cache Invalidation Pattern

When modifying resources or permissions, invalidate related caches:

```python
# After creating/updating/deleting a resource
if self.cache_client:
    self.cache_client.client.delete_pattern(f"{resources}:*:tenant:{tenant_id}:*")

# After changing permissions (grant/revoke)
if self.cache_client:
    self.cache_client.client.delete_pattern(f"{resources}:*:user:{user_id}:*")
    # Also invalidate group members if group permission changed
```
