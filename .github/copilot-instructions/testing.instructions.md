# Testing Instructions (CRITICAL)

## Running Tests

```bash
# ALWAYS run tests in parallel — many tests, takes too long otherwise
pytest tests/ -n auto --no-header -q

# With coverage
pytest tests/ -n auto --cov=unifiedui --cov-report=html --cov-report=term-missing

# Single file
pytest tests/unit/api/v1/test_applications.py -n auto --no-header -q

# Single test
pytest tests/unit/api/v1/test_applications.py::TestApplicationRoutes::test_create_application_success -v
```

**pytest config (pyproject.toml)**:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=unifiedui --cov-report=html --cov-report=term-missing"
```

---

## Three-File Pattern (MANDATORY)

Every resource in `tests/unit/api/v1/` has **exactly three test files**:

| File | Tests | Cache Header |
|------|-------|-------------|
| `test_{resource}.py` | CRUD operations, validation, filtering, list queries | `use_cache=False` |
| `test_{resource}_rbac.py` | All RBAC scenarios, permission enforcement | `use_cache=False` |
| `test_{resource}_caching.py` | Cache hit/miss, invalidation, isolation | `use_cache=True` (default) |

### Resources with three-file pattern:
applications, autonomous_agents, chat_widgets, conversations, credentials, custom_groups, identity, principals, tags, tenants, tools, user_favorites

---

## Test File Structure

### 1. `test_{resource}.py` — CRUD Tests

```python
"""Tests for {resource} API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers

# API Endpoints (constants at top)
ENDPOINT_{RESOURCE} = "/api/v1/platform-service/tenants/{tenant_id}/{resources}"
ENDPOINT_{RESOURCE}_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/{resources}/{resource_id}"
ENDPOINT_{RESOURCE}_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/{resources}/{resource_id}/principals"

# Roles and Principal Types (constants)
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


# Helper functions
def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestApplicationRoutes:
    """Test suite for application API routes."""
    
    def test_create_{resource}_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful {resource} creation."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        # ... create resource, assert 201, validate all fields
    
    def test_create_{resource}_missing_name(self, test_client, test_user_token):
        """Test creation with missing required field."""
        # ... assert 422

    def test_list_{resources}(self, test_client, test_user_token):
        """Test listing resources (only those with permissions)."""
    
    def test_get_{resource}_detail(self, ...):
    def test_update_{resource}(self, ...):
    def test_delete_{resource}(self, ...):
    def test_{resource}_not_found(self, ...):
```

**What CRUD tests cover:**
- Successful create with all fields → 201
- Missing required fields → 422
- Invalid field types → 422
- List (user sees only permitted resources) → 200
- Get by ID → 200
- Get non-existent → 404
- Update → 200
- Partial update (PATCH with subset of fields) → 200
- Delete → 204
- Delete non-existent → 404
- Config validation (if resource has config)
- Query params: name filter, is_active, tags, order_by, order_direction, view

---

### 2. `test_{resource}_rbac.py` — RBAC Tests (CRITICAL)

These tests comprehensively verify the role-based access control system.

```python
"""Tests for {resource} RBAC (Role-Based Access Control)."""

class Test{Resource}RBAC:
    """Test suite for {resource} role-based access control."""
    
    # === Creator becomes ADMIN ===
    def test_creator_becomes_admin(self, test_client):
        """Creator automatically gets ADMIN role on the resource."""
    
    # === ADMIN capabilities ===
    def test_admin_can_update(self, test_client):
    def test_admin_can_delete(self, test_client):
    def test_admin_can_manage_principals(self, test_client):
    
    # === Non-member blocked ===
    def test_non_member_cannot_access(self, test_client):
        """User without membership is blocked from view, update, delete, manage principals."""
    
    # === READ role enforcement ===
    def test_read_user_can_view_but_not_modify(self, test_client):
        """READ can: view detail, list principals. 
         READ cannot: update, delete, manage principals."""
    
    # === WRITE role enforcement ===
    def test_write_user_can_modify_but_not_delete_or_manage(self, test_client):
        """WRITE can: view, update.
         WRITE cannot: delete, manage principals."""
    
    # === Multiple admins ===
    def test_multiple_admins(self, test_client):
    
    # === Role replacement ===
    def test_user_role_replacement(self, test_client):
        """Setting new role replaces old one (single-role model)."""
    
    # === Role removal ===
    def test_removing_admin_role(self, test_client):
        """After removing ADMIN, user is fully blocked."""
    
    # === Tenant admin bypass ===
    def test_tenant_global_admin_bypasses_permissions(self, test_client):
        """GLOBAL_ADMIN can access all resources without explicit membership."""
    
    def test_tenant_resource_admin_bypasses_permissions(self, test_client):
        """{RESOURCE}_ADMIN can access all resources of this type."""
    
    # === Group-based permissions ===
    def test_identity_group_permission(self, test_client):
        """User gains access via identity group membership."""
    
    def test_custom_group_permission(self, test_client):
        """User gains access via custom group membership."""
```

**RBAC test scenarios (MUST cover all):**
1. Creator → automatic ADMIN
2. ADMIN full access (CRUD + manage principals)
3. Non-member completely blocked (GET, PATCH, DELETE, PUT principals)
4. READ → can view, cannot modify/delete/manage
5. WRITE → can view + update, cannot delete/manage principals
6. Multiple users with ADMIN
7. Role replacement (grant new role replaces old)
8. Role removal (revoke → blocked)
9. GLOBAL_ADMIN bypasses resource permissions
10. {RESOURCE}_ADMIN bypasses resource permissions
11. Service key + Bearer for `/config` endpoints
12. Identity group grants indirect access
13. Custom group grants indirect access

---

### 3. `test_{resource}_caching.py` — Cache Tests (CRITICAL)

These tests verify precise cache behavior with Redis.

```python
"""Tests for {resource} caching."""

class Test{Resource}Caching:
    """Test suite for {resource} caching behavior with X-Use-Cache enabled."""
    
    # === Cache hits ===
    def test_creator_permissions_cached(self, test_client, fake_redis_client):
        """First access caches, second access uses cache."""
    
    def test_no_access_cached(self, test_client, fake_redis_client):
        """Denied access is also handled correctly with caching."""
    
    # === Permission grant invalidation ===
    def test_direct_user_permission_grant_invalidates_cache(self, test_client, fake_redis_client):
        """Granting permission to user invalidates their cached denial."""
        # 1. User denied (403)
        # 2. Admin grants permission
        # 3. User now allowed (200) — cache was invalidated
    
    # === Permission revoke invalidation ===
    def test_direct_user_permission_revoke_invalidates_cache(self, test_client, fake_redis_client):
        """Revoking permission invalidates cached access."""
        # 1. User allowed (200)
        # 2. Admin revokes permission  
        # 3. User now denied (403) — cache was invalidated
    
    # === Multiple permission changes ===
    def test_multiple_permission_changes_invalidate_cache(self, test_client, fake_redis_client):
        """READ → WRITE → ADMIN: each change invalidates cache correctly."""
    
    # === List caching ===
    def test_list_cached_correctly(self, test_client, fake_redis_client):
        """List respects permission scope (user only sees their resources)."""
    
    # === Cache isolation ===
    def test_cache_isolated_between_users(self, test_client, fake_redis_client):
        """User A's cache does not affect User B's cache."""
    
    # === Tenant admin bypass cached ===
    def test_tenant_admin_bypass_cached_correctly(self, test_client, fake_redis_client):
        """GLOBAL_ADMIN bypass is cached and works on repeated access."""

class Test{Resource}ListCaching:
    """Test list caching with order/filter parameters."""
    
    def test_list_cached_with_order_by(self, test_client, fake_redis_client):
        """Different order_by/direction create different cache entries."""
    
    def test_list_cached_with_is_active(self, test_client, fake_redis_client):
        """is_active filter creates separate cache entries."""
    
    def test_list_cache_key_includes_all_params(self, test_client, fake_redis_client):
        """All query params (skip, limit, view, order, active) are in cache key."""

class Test{Resource}TagCacheInvalidation:
    """Test cache invalidation when modifying resource tags."""

    def test_adding_tags_invalidates_cache(self, ...):
    def test_removing_tags_invalidates_cache(self, ...):
    def test_replacing_tags_invalidates_cache(self, ...):
```

**Cache test scenarios (MUST cover all):**
1. Successful access is cacheable (two identical requests work)
2. Permission denial is handled correctly with caching
3. Granting user permission → user's cache invalidated → access now works
4. Revoking user permission → user's cache invalidated → access now denied
5. Multi-step permission escalation (READ → WRITE → ADMIN → delete)
6. List endpoint respects permissions with caching
7. Cache isolation between different users
8. GLOBAL_ADMIN bypass is cached
9. Group permission grant invalidates all group member caches
10. Tag modifications invalidate resource cache
11. Different list query params create different cache keys

**CRITICAL fixture**: All caching tests MUST use `fake_redis_client` fixture parameter:
```python
def test_something(self, test_client: TestClient, fake_redis_client: Any) -> None:
```

**CRITICAL header**: Caching tests use `create_auth_headers(token)` (default `use_cache=True`).
CRUD and RBAC tests use `create_auth_headers(token, use_cache=False)`.

---

## Fixtures

### Location
All fixtures in `tests/fixtures/` — imported by `tests/conftest.py`.

### Key Fixtures

| Fixture | File | Scope | Description |
|---------|------|-------|-------------|
| `test_db_engine` | `database.py` | function | SQLite temp file, creates all tables |
| `test_db_client` | `database.py` | function | SQLAlchemyClient with test engine |
| `test_client` | `client.py` | function | FastAPI TestClient + helper methods |
| `test_user_token` | `auth.py` | function | Default MockIdentityToken |
| `fake_redis_client` | `cache.py` | function | fakeredis FakeRedis instance |
| `test_vault` | `vault.py` | function | MockVault (in-memory dict) |

### TestClient Helper Methods
The `test_client` fixture adds helper methods:
```python
test_client.create_test_user("user-id", "Display Name") → MockIdentityToken
test_client.create_test_user("user-id", "Name", idp_groups=[...]) → MockIdentityToken
```

### Auth Headers
```python
from tests.conftest import create_auth_headers

# CRUD/RBAC tests: caching disabled
headers = create_auth_headers(user_token, use_cache=False)

# Caching tests: caching enabled (default)
headers = create_auth_headers(user_token)

# Service key tests:
headers = create_auth_headers(user_token, use_cache=False)
headers["X-Service-Key"] = "test-key"
```

### Database Fixture
- Uses SQLite temp file (not in-memory) for cross-connection compatibility
- Function-scoped: fresh database per test
- `Base.metadata.create_all(engine)` creates all tables automatically
- Global singleton pattern: fixtures set `_db_client`, `_cache_client`, `_vault` globals

### MockVault
```python
class MockVault(BaseVault):
    """In-memory vault for testing."""
    # Stores secrets in a plain dict
    # Supports: store_secret, get_secret, update_secret, delete_secret, list_secrets, ping
```

---

## Test Organization Summary

```
tests/
├── conftest.py                         # Imports all fixtures
├── fixtures/
│   ├── auth.py                         # MockIdentityToken, create_auth_headers
│   ├── cache.py                        # fakeredis setup
│   ├── client.py                       # TestClient fixture
│   ├── data.py                         # Sample data
│   ├── database.py                     # SQLite engine + client
│   └── vault.py                        # MockVault
└── unit/
    ├── api/v1/                         # Route integration tests (3-file pattern)
    │   ├── test_applications.py
    │   ├── test_applications_rbac.py
    │   ├── test_applications_caching.py
    │   ├── test_autonomous_agents.py
    │   ├── test_autonomous_agents_rbac.py
    │   ├── test_autonomous_agents_caching.py
    │   ├── ... (same for all resources)
    ├── handlers/                        # Handler unit tests
    ├── caching/                         # Cache infrastructure tests
    ├── core/                            # Core module tests
    ├── identity/                        # Identity provider tests
    ├── libs/                            # Library tests
    ├── schema/                          # Schema validation tests
    ├── utils/                           # Utility tests
    └── vault/                           # Vault implementation tests
```

---

## Test Naming Convention

```python
def test_{action}_{scenario}(self, test_client, ...):
    """Docstring describing what is tested."""
```

Examples:
- `test_create_application_success`
- `test_create_application_missing_name`
- `test_read_user_can_view_but_not_modify`
- `test_direct_user_permission_grant_invalidates_cache`
- `test_cache_isolated_between_users`

---

## Test Helper Functions

Each test file defines its own helper functions at module level:

```python
def create_tenant_for_user(test_client, user_token, tenant_name="Test Tenant") -> str:
    """Create a tenant and return its ID."""

def create_{resource}(test_client, tenant_id, headers, name="Test") -> str:
    """Create a resource and return its ID."""

def add_user_to_tenant(test_client, tenant_id, admin_headers, user_id, role="READER") -> None:
    """Add a user to a tenant with specified role."""
```

These are **duplicated per file intentionally** — each test file is self-contained for parallel execution (`-n auto`).

---

## Adding Tests for a New Resource

1. Create `tests/unit/api/v1/test_{resource}.py`:
   - Endpoint constants
   - Helper functions (create_tenant, create_resource, add_user_to_tenant)
   - CRUD test class covering all operations

2. Create `tests/unit/api/v1/test_{resource}_rbac.py`:
   - Same endpoint constants and helpers
   - Full RBAC test class (all 13 scenarios above)

3. Create `tests/unit/api/v1/test_{resource}_caching.py`:
   - Same endpoint constants and helpers
   - Full caching test class (all 11 scenarios above)
   - All test methods MUST accept `fake_redis_client` fixture
   - Use `create_auth_headers(token)` without `use_cache=False`
