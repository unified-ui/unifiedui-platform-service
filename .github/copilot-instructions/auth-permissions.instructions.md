# Authentication & Permissions

## Location
All auth middleware: `unifiedui/core/middleware/apis/v1/auth.py`

---

## Three Auth Decorators

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
    entity="application",  # or "tenant", "credential", "autonomous_agent", etc.
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
| `application` | ApplicationMember | `application_id` |
| `credential` | CredentialMember | `credential_id` |
| `autonomous_agent` | AutonomousAgentMember | `autonomous_agent_id` |
| `custom_group` | CustomGroupMember | `custom_group_id` |
| `conversation` | ConversationMember | `conversation_id` |
| `chat_widget` | ChatWidgetMember | `chat_widget_id` |
| `tool` | ToolMember | `tool_id` |
| `tag` | (uses IS_CREATOR check) | `tag_id` |
| `user_favorite` | (uses IS_CREATOR check) | `user_id` |

### 3. `@authenticate_autonomous_agent_api_key()`
API key authentication without Bearer token.

- Validates `X-Unified-UI-Autonomous-Agent-API-Key` header
- Retrieves primary/secondary keys from vault (never cached for rotation support)
- Stores `request.state.autonomous_agent` and `request.state.authenticated_via_api_key = True`
- Requires `tenant_id` and `autonomous_agent_id` in path params

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

For internal service-to-service calls:

```python
@authenticate(required_service_auth_key="X_AGENT_SERVICE_KEY")
```

- Service key stored in environment variable / `Settings`
- Header: `X-Service-Key: <key>`
- Both service key AND Bearer token required
- Use case: Agent service calling platform service endpoints

---

## Cache Header

- `X-Use-Cache: true` (default) — ContextIdentityUser uses Redis cache for tenants/groups
- `X-Use-Cache: false` — Forces fresh DB queries for user context
- **Tests always use `use_cache=False`** except for caching-specific tests
