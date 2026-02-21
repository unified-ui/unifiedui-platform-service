# Authentication & Permissions

## Location
All auth middleware: `unifiedui/core/middleware/apis/v1/auth.py`

---

## Four Auth Decorators

### 1. `@authenticate()`
Standard user authentication via Bearer token.

- Extracts `Authorization: Bearer <token>` header
- Creates `ContextIdentityUser` from token (validates via identity provider)
- Stores user in `request.state.user`
- Checks `X-Use-Cache` header (default `true`) → stores in `request.state.use_cache`
- If `tenant_id` in path params → verifies user is member of that tenant

**Optional service key**: `@authenticate(required_service_auth_key="X_AGENT_SERVICE_KEY")`
- Also validates `X-Service-Key` header against `settings.x_agent_service_key`
- Both Bearer AND service key must be valid

### 2. `@check_permissions()`
Permission check applied after `@authenticate()`.

```python
@check_permissions(
    entity="chat_agent",  # or "tenant", "credential", "autonomous_agent", etc.
    required_permissions=[PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN]
)
```

**Permission resolution flow:**
1. **Tenant-level bypass**: If user has `GLOBAL_ADMIN` → pass
2. **Resource-specific admin**: If user has `{RESOURCE}_ADMIN` on tenant → pass
3. **Resource-level check**: Query `{resource}_members` table for user's principal_ids with allowed roles

**Role hierarchy (important!):**
- Requesting `READ` → accepts ADMIN, WRITE, or READ
- Requesting `WRITE` → accepts ADMIN or WRITE
- Requesting `ADMIN` → accepts only ADMIN

**Supported entity types:**
| Entity | Member Model | ID Path Param |
|--------|-------------|---------------|
| `tenant` | (uses TenantRolesEnum) | `tenant_id` |
| `chat_agent` | ChatAgentMember | `chat_agent_id` |
| `credential` | CredentialMember | `credential_id` |
| `autonomous_agent` | AutonomousAgentMember | `autonomous_agent_id` |
| `custom_group` | CustomGroupMember | `custom_group_id` |
| `conversation` | ConversationMember | `conversation_id` |
| `chat_widget` | ChatWidgetMember | `chat_widget_id` |
| `tool` | ToolMember | `tool_id` |
| `tag` | (uses IS_CREATOR check) | `tag_id` |
| `user_favorite` | (uses IS_CREATOR check) | `user_id` |

**Note**: `tenant_ai_model` uses `@authenticate_service_key()` instead of `@check_permissions()` — no member table, no RBAC. Only agent-service can access via service key.

### 3. `@authenticate_autonomous_agent_api_key()`
API key authentication without Bearer token.

- Validates `X-Unified-UI-Autonomous-Agent-API-Key` header
- Retrieves primary/secondary keys from vault (never cached for rotation support)
- Stores `request.state.autonomous_agent` and `request.state.authenticated_via_api_key = True`
- Requires `tenant_id` and `autonomous_agent_id` in path params

### 4. `@authenticate_service_key(required_service_auth_key)`
Service-to-service authentication via `X-Service-Key` only. **No Bearer token required.**

```python
@authenticate_service_key(required_service_auth_key="AGENT_TO_PLATFORM_SERVICE_KEY")
```

- Validates only the `X-Service-Key` header against vault-resolved key
- No `ContextIdentityUser` is created — no user context available
- Used for endpoints that only agent-service calls (e.g., AI model lookup by purpose)
- Key resolved from vault via `app_vault.build_secret_uri(key_name)`

---

## ContextIdentityUser

Created by `@authenticate()`, provides lazy-loaded user context:

```python
user: ContextIdentityUser = request.state.user

user.identity.get_id()       # User ID from token
user.identity.get_name()     # Display name
user.identity.get_email()    # Email
user.tenants                 # List of tenant memberships with roles (cached)
user.groups                  # Identity provider groups (cached)
user.custom_groups           # UnifiedUI custom groups (cached)
```

All properties use Redis cache when `use_cache=True` (controlled by `X-Use-Cache` header).

---

## Authorization Flow (Step by Step)

1. **Token extraction** → Bearer token from Authorization header
2. **Token validation** → Identity provider validates JWT, returns user identity
3. **Tenant access check** → User must be member of `tenant_id` in path
4. **Permission check** (if `@check_permissions` applied):
   a. Check tenant-level admin roles (GLOBAL_ADMIN, {RESOURCE}_ADMIN)
   b. Collect all principal_ids: user_id + identity_group_ids + custom_group_ids
   c. Query `{resource}_members` for matching principal with sufficient role
5. **Handler execution** → User object available via `request.state.user`

---

## Service Key Authentication

For internal service-to-service calls, two patterns exist:

### 1. Service key + Bearer token (both required)

```python
@authenticate(required_service_auth_key="AGENT_TO_PLATFORM_SERVICE_KEY")
```

- Both `X-Service-Key` AND `Authorization: Bearer` must be valid
- Use case: Endpoints where the agent-service acts on behalf of a user

### 2. Service key only (no Bearer token)

```python
@authenticate_service_key(required_service_auth_key="AGENT_TO_PLATFORM_SERVICE_KEY")
```

- Only `X-Service-Key` is validated
- No user context available — no `ContextIdentityUser`
- Use case: Endpoints called by agent-service that don't need user identity (e.g., fetching AI models by purpose)

Service keys are stored in the **app vault** and resolved via `app_vault.build_secret_uri(key_name)`.

---

## Cache Header

- `X-Use-Cache: true` (default) — ContextIdentityUser uses Redis cache for tenants/groups
- `X-Use-Cache: false` — Forces fresh DB queries for user context
- **Tests always use `use_cache=False`** except for caching-specific tests

---

## Permission Resolver (`my_permission`)

**File**: `unifiedui/handlers/permission_resolver.py`

Returns the calling user's effective permission on each resource in API responses. Every resource response schema includes `my_permission: Optional[str]` (`'ADMIN'` | `'WRITE'` | `'READ'` | `None`).

### Functions

| Function | Purpose |
|----------|---------|
| `get_principal_ids(user, db, tenant_id)` | Collects all principal IDs for the user (user_id + identity groups + custom groups) |
| `check_is_admin(user, tenant_id, resource_type)` | Checks tenant-level admin bypass (GLOBAL_ADMIN or {RESOURCE}_ADMIN) |
| `resolve_my_permission(db, member_model, resource_id, principal_ids, is_admin)` | Resolves the highest permission for a single resource |
| `resolve_my_permissions_bulk(db, member_model, resource_ids, principal_ids, is_admin)` | Resolves permissions for multiple resources in a single query |

### Resolution Logic

1. If `is_admin` → return `'ADMIN'` immediately
2. Query `{resource}_members` table for matching `principal_id` + `resource_id`
3. Return the highest permission found (`ADMIN` > `WRITE` > `READ`)
4. If no membership → return `None`

### Usage in Handlers

```python
principal_ids = await get_principal_ids(user, db, tenant_id)
is_admin = check_is_admin(user, tenant_id, "chat_agent")

# Single resource
my_perm = resolve_my_permission(db, ChatAgentMember, app.id, principal_ids, is_admin)

# Bulk (list endpoints)
perms = resolve_my_permissions_bulk(db, ChatAgentMember, app_ids, principal_ids, is_admin)
```

### Response Schema

All 7 RBAC resource response schemas include:

```python
class ChatAgentResponse(BaseModel):
    # ... other fields ...
    my_permission: Optional[str] = None
```

### Supported Resources

ChatAgent, AutonomousAgent, ChatWidget, ReActAgent, Conversation, Credential, Tool.

### Adding New Roles

When adding new `TenantPermissionEnum` roles:

1. Add the enum value in `core/database/enums.py`
2. Create an Alembic migration
3. Update `permission_resolver.py` if the role affects `check_is_admin` logic
4. Update the **frontend** `usePermissions.ts` hook (CREATOR_ROLES, ADMIN_ROLES maps) and `api/types.ts` (`TenantPermissionEnum`)
5. Document the new role in both platform and frontend instruction files
