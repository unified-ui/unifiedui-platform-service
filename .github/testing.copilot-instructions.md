---
applyTo: 'tests/**'
---

# AIHub Testing Specifications

## Testing Philosophy
- Write tests BEFORE or alongside production code
- Aim for 90%+ code coverage
- Test behavior, not implementation
- Keep tests isolated and independent

## Code Standards for Tests

### Type Annotations (CRITICAL)
- **ALWAYS** use type annotations in all test code
- **EVERY** function/method parameter MUST have a type annotation
- **EVERY** function/method MUST have a return type annotation
- Use `typing` module for complex types

**Example:**
```python
from typing import Optional, List
import pytest

def test_create_application(
    db_client: SQLAlchemyClient,
    mock_user: ContextIdentityUser,
    tenant_id: str
) -> None:
    """Test application creation."""
    handler = ApplicationHandler(db_client)
    result: ApplicationResponse = handler.create_application(
        tenant_id=tenant_id,
        request=CreateApplicationRequest(name="Test App"),
        user=mock_user
    )
    assert result.name == "Test App"

@pytest.fixture
def mock_user() -> ContextIdentityUser:
    """Create a mock user for testing."""
    return ContextIdentityUser(
        identity=IdentityUser(id="test-123", email="test@example.com"),
        groups=[],
        custom_groups=[],
        tenants=[]
    )
```

**Common Type Annotations:**
- Fixtures: `-> ReturnType`
- Test functions: `-> None`
- Mocks: `-> Mock` or `-> MagicMock`
- Async functions: `async def test_something() -> None:`

## API Test Structure

### Three-File Pattern for API Tests
For each resource in `tests/unit/api/v1/`, create **three test files**:

1. **`test_{resource}.py`**: CRUD operations and basic list filtering
2. **`test_{resource}_rbac.py`**: Explicit RBAC testing
3. **`test_{resource}_caching.py`**: Caching behavior testing

**Exception**: `identity` endpoints (no RBAC tests as they don't have resource-level permissions)

### File 1: `test_{resource}.py` - CRUD Operations

**Purpose**: Test basic CRUD operations and list filtering by user permissions

**Critical Rules:**
- **ALWAYS** set `X-Use-Cache: false` in headers (disable caching)
- Use `create_auth_headers(token, use_cache=False)` helper
- Test happy path and validation errors for each endpoint
- **List operations**: Test that users only see resources they have access to

**Test Structure:**
```python
"""Tests for {resource} API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from tests.fixtures.auth import create_auth_headers

# Constants at module level
ENDPOINT_{RESOURCE}S = "/api/v1/tenants/{tenant_id}/{resource}s"
ENDPOINT_{RESOURCE}_DETAIL = "/api/v1/tenants/{tenant_id}/{resource}s/{{resource_id}}"
ENDPOINT_{RESOURCE}_PRINCIPALS = "/api/v1/tenants/{tenant_id}/{resource}s/{{resource_id}}/principals"

NON_EXISTENT_ID = "non-existent-id"
ROLE_ADMIN = "ADMIN"
ROLE_WRITE = "WRITE"
ROLE_READ = "READ"

class Test{Resource}Routes:
    """Test suite for {resource} API routes."""
    
    def test_create_{resource}_success(
        self, 
        test_client: TestClient,
        sample_{resource}_data: dict[str, Any]
    ) -> None:
        """Test successful {resource} creation."""
        user_token = test_client.create_test_user("creator", "Creator")
        headers = create_auth_headers(user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_{RESOURCE}S.format(tenant_id=tenant_id),
            json=sample_{resource}_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        # ... assertions
    
    def test_list_{resource}s_filtered_by_permissions(
        self,
        test_client: TestClient
    ) -> None:
        """Test that users only see {resource}s they have access to."""
        # User A creates resource
        user_a_token = test_client.create_test_user("user-a", "User A")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        
        # User B should NOT see User A's resource in list
        user_b_token = test_client.create_test_user("user-b", "User B")
        headers_b = create_auth_headers(user_b_token, use_cache=False)
        
        response_b = test_client.get(ENDPOINT_{RESOURCE}S, headers=headers_b)
        assert len(response_b.json()) == 0  # User B sees nothing
        
        response_a = test_client.get(ENDPOINT_{RESOURCE}S, headers=headers_a)
        assert len(response_a.json()) > 0  # User A sees their own
```

**Common Tests to Include:**
- `test_create_{resource}_success` - Happy path
- `test_create_{resource}_missing_name` - Validation
- `test_create_{resource}_invalid_type` - Validation
- `test_get_{resource}_success` - Retrieve single
- `test_get_{resource}_not_found` - 404 case
- `test_list_{resource}s_empty` - Empty list
- `test_list_{resource}s_filtered_by_permissions` - **CRITICAL**: Permission filtering
- `test_list_{resource}s_with_pagination` - Pagination
- `test_update_{resource}_success` - Update happy path
- `test_update_{resource}_not_found` - 404 case
- `test_delete_{resource}_success` - Delete
- `test_delete_{resource}_not_found` - 404 case

### File 2: `test_{resource}_rbac.py` - RBAC Testing

**Purpose**: Explicitly test role-based access control behavior

**Critical Rules:**
- **ALWAYS** set `X-Use-Cache: false` in headers
- Test ALL permission levels: ADMIN, WRITE, READ, NO_ACCESS
- Test access via: Direct user, Identity group, Custom group
- Test permission grant → user gains access
- Test permission revoke → user loses access

**Test Structure:**
```python
"""Tests for {resource} RBAC (Role-Based Access Control)."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from tests.fixtures.auth import create_auth_headers

class Test{Resource}RBAC:
    """Test suite for {resource} role-based access control."""
    
    def test_admin_can_do_everything(self, test_client: TestClient) -> None:
        """Test that ADMIN role has full access."""
        # Create resource with admin
        # Admin can: create, read, update, delete, manage permissions
        pass
    
    def test_write_can_modify_but_not_manage_permissions(
        self, 
        test_client: TestClient
    ) -> None:
        """Test that WRITE role can modify but not manage permissions."""
        # User with WRITE can: read, update
        # User with WRITE CANNOT: delete, manage permissions
        pass
    
    def test_read_can_only_view(self, test_client: TestClient) -> None:
        """Test that READ role can only view."""
        # User with READ can: read only
        # User with READ CANNOT: update, delete, manage permissions
        pass
    
    def test_non_member_has_no_access(self, test_client: TestClient) -> None:
        """Test that users without permissions cannot access resource."""
        # User A creates resource
        # User B (no permissions) cannot: read, update, delete, manage
        pass
    
    def test_direct_user_permission_grant(self, test_client: TestClient) -> None:
        """Test granting permission directly to user."""
        # User initially has no access → 403
        # Admin grants READ to user
        # User now has access → 200
        pass
    
    def test_direct_user_permission_revoke(self, test_client: TestClient) -> None:
        """Test revoking permission from user."""
        # User initially has ADMIN access
        # Admin revokes ADMIN
        # User now has no access → 403
        pass
    
    def test_identity_group_grants_permissions(
        self, 
        test_client: TestClient
    ) -> None:
        """Test that identity group membership grants permissions."""
        # Create user with identity_group_id
        # Admin grants READ to identity_group_id
        # User (member of group) now has READ access
        pass
    
    def test_custom_group_grants_permissions(
        self, 
        test_client: TestClient,
        fake_redis_client: Any
    ) -> None:
        """Test that custom group membership grants permissions."""
        # Create custom group with user as member (in DB)
        # Admin grants WRITE to custom_group_id
        # User (member of group) now has WRITE access
        pass
    
    def test_multiple_permission_sources_combine(
        self,
        test_client: TestClient
    ) -> None:
        """Test that permissions from multiple sources combine correctly."""
        # User has READ via identity group
        # User has WRITE via direct assignment
        # User should have highest permission (WRITE)
        pass
```

**Required RBAC Test Scenarios:**
1. **Admin role**: Full access (CRUD + manage permissions)
2. **Write role**: Read + Update (NO delete, NO manage permissions)
3. **Read role**: Read only
4. **No access**: All operations → 403
5. **Permission grant** (user, identity group, custom group)
6. **Permission revoke** (user, identity group, custom group)
7. **Permission combination** (multiple sources)

### File 3: `test_{resource}_caching.py` - Caching Behavior

**Purpose**: Test cache invalidation and caching behavior

**Critical Rules:**
- **ENABLE caching**: Use default headers or `X-Use-Cache: true`
- Test cache invalidation on permission changes
- Verify cached permissions are used
- Verify cache is cleared when needed

**Test Structure:**
```python
"""Tests for {resource} caching."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from tests.fixtures.auth import create_auth_headers

class Test{Resource}Caching:
    """Test suite for {resource} caching behavior."""
    
    def test_permissions_cached_after_first_access(
        self,
        test_client: TestClient,
        fake_redis_client: Any
    ) -> None:
        """Test that permissions are cached after first access."""
        user_token = test_client.create_test_user("cache-user", "Cache User")
        headers = create_auth_headers(user_token)  # Caching enabled!
        
        # First access - caches permissions
        response1 = test_client.get(ENDPOINT, headers=headers)
        
        # Second access - uses cached permissions (faster)
        response2 = test_client.get(ENDPOINT, headers=headers)
        
        assert response1.status_code == response2.status_code
    
    def test_direct_user_permission_grant_invalidates_cache(
        self,
        test_client: TestClient,
        fake_redis_client: Any
    ) -> None:
        """Test that granting permission invalidates user's cache."""
        # User has no access (cached)
        # Admin grants READ permission
        # User NOW has access (cache was invalidated)
        pass
    
    def test_direct_user_permission_revoke_invalidates_cache(
        self,
        test_client: TestClient,
        fake_redis_client: Any
    ) -> None:
        """Test that revoking permission invalidates user's cache."""
        # User has ADMIN access (cached)
        # Admin revokes ADMIN permission
        # User NOW has no access (cache was invalidated)
        pass
    
    def test_custom_group_permission_grant_invalidates_member_cache(
        self,
        test_client: TestClient,
        fake_redis_client: Any
    ) -> None:
        """Test that granting permission to custom group invalidates member caches."""
        # Create custom group with user as member
        # User has no access (cached)
        # Admin grants READ to custom_group_id
        # User NOW has access via group (cache was invalidated)
        pass
    
    def test_identity_group_permission_grant_invalidates_member_cache(
        self,
        test_client: TestClient,
        fake_redis_client: Any
    ) -> None:
        """Test that granting permission to identity group invalidates member caches."""
        # User with identity_group_id has no access (cached)
        # Admin grants WRITE to identity_group_id
        # User NOW has access via group (cache was invalidated)
        pass
    
    def test_cache_isolated_between_users(
        self,
        test_client: TestClient,
        fake_redis_client: Any
    ) -> None:
        """Test that cache is isolated per user."""
        # User A's cached permissions don't affect User B
        pass
```

**Required Caching Test Scenarios:**
1. **Permissions cached**: First access caches, second uses cache
2. **Direct permission grant**: Cache invalidated
3. **Direct permission revoke**: Cache invalidated
4. **Identity group grant**: Member caches invalidated
5. **Custom group grant**: Member caches invalidated
6. **Cache isolation**: User A cache ≠ User B cache

## Test Structure
```
tests/
├── unit/              # Unit tests (isolated, mocked)
├── integration/       # Integration tests (real infrastructure)
├── e2e/              # End-to-end tests
├── fixtures/         # Shared test fixtures
└── conftest.py       # Pytest configuration
```

## Testing Framework
- **Framework**: pytest
- **Coverage**: pytest-cov
- **Async Support**: pytest-asyncio
- **Mocking**: unittest.mock or pytest-mock
- **HTTP Testing**: httpx or TestClient (FastAPI)

## Test Categories

### Unit Tests (`tests/unit/`)
- Test individual functions, classes, methods in isolation
- Mock all external dependencies:
  - Database clients
  - Cache clients
  - Vault clients
  - HTTP calls
  - Identity providers
- Fast execution (< 1 second per test)
- No real infrastructure required

### Integration Tests (`tests/integration/`)
- Test interactions between components
- Use **real** Azure test resources:
  - Azure AD test tenant
  - Azure Key Vault test instance
  - Azure Storage test account
- Use **real** on-premise test infrastructure:
  - PostgreSQL test database
  - Redis test instance
  - Message broker test instance
- Spin up infrastructure via docker-compose
- Clean up after each test

### E2E Tests (`tests/e2e/`)
- Test complete user workflows
- Full application stack
- Realistic data and scenarios
- Test API endpoints end-to-end

## Database Testing

### In-Memory Database for Unit Tests
- Use SQLite in-memory for fast unit tests
- Configure test database in `conftest.py`:
  ```python
  @pytest.fixture
  def test_db():
      # In-memory SQLite
      engine = create_engine("sqlite:///:memory:")
      TestingSessionLocal = sessionmaker(bind=engine)
      Base.metadata.create_all(bind=engine)
      yield TestingSessionLocal()
      Base.metadata.drop_all(bind=engine)
  ```

### Test Database for Integration Tests
- Use PostgreSQL test database
- Run migrations before tests
- Truncate tables between tests (not drop/create)
- Use transactions with rollback for isolation

### Document Database Testing
- Mock document DB client for unit tests
- Use test collection/bucket for integration tests
- Clear test data after each test

## Caching Testing

### Mock Cache for Unit Tests
- Use `fakeredis` or mock Redis client
- Test cache hit/miss scenarios
- Verify cache invalidation logic

### Real Cache for Integration Tests
- Use Redis test instance (separate from production)
- Test cache expiration
- Test cache invalidation patterns
- Verify tenant-based cache isolation

## Authentication & Identity Testing

### Mock Identity for Unit Tests
- Create mock `IdentityUser` objects:
  ```python
  @pytest.fixture
  def mock_user():
      return IdentityUser(
          id="test-user-123",
          tenant_id="test-tenant-456",
          email="test@example.com",
          roles=["ADMIN"],
          tenants=[],
      )
  ```
- Mock JWT token validation
- Mock permission checks

### Identity Provider for Integration Tests
- Use Azure AD test tenant
- Create test users and groups
- Test actual token validation
- Test Graph API calls

## Permission Testing

### Critical Permission Tests
- Test permission checks for all protected endpoints
- Test with different user roles:
  - System Admin
  - Tenant Admin
  - Application Owner
  - Conversation Member
  - No permissions
- Test resource-level permissions (user can only access their own resources)
- Test custom group membership permissions
- Test permission inheritance

### Permission Test Scenarios
1. User has required permission → Allow
2. User lacks required permission → Deny (403)
3. User has permission on different resource → Deny
4. User permission cached → Fast validation
5. Permission changed → Cache invalidated → New check

## Cache Invalidation Testing

### Test Cache Invalidation Scenarios
- User permission changed → clear `user:{user_id}:*`
- Tenant data updated → clear `{tenant_id}:*`
- Resource deleted → clear specific keys
- Verify cache is actually cleared
- Verify data is re-fetched after invalidation

## Secrets & Vault Testing

### Mock Vault for Unit Tests
- Mock vault client
- Return fake secrets
- Never use real credentials in tests

### Real Vault for Integration Tests
- Use Azure Key Vault test instance
- Create/read/delete test secrets
- Clean up secrets after tests

## Test Data Management

### Fixtures
- Use pytest fixtures for common test data
- Create reusable fixtures in `conftest.py`
- Use factory patterns for complex objects
- Keep fixtures focused and minimal

### Test Data Isolation
- Each test should be independent
- Don't rely on test execution order
- Clean up data after each test
- Use unique IDs (UUIDs) to avoid conflicts

## API Testing

### FastAPI TestClient
```python
from fastapi.testclient import TestClient
from aihub.app import app

client = TestClient(app)

def test_endpoint():
    response = client.get("/api/v1/tenants/123")
    assert response.status_code == 200
```

### Test All HTTP Methods
- GET: Read operations
- POST: Create operations
- PUT/PATCH: Update operations
- DELETE: Delete operations

### Test Response Schemas
- Validate response matches Pydantic schema
- Check required fields
- Verify data types

### Test Error Cases
- Invalid input → 400
- Unauthorized → 401
- Forbidden → 403
- Not found → 404
- Server error → 500

## Mocking Best Practices

### What to Mock in Unit Tests
- Database operations
- Cache operations
- External API calls (N8N, Azure AD)
- Vault operations
- Message broker
- File I/O
- Time-dependent operations

### What NOT to Mock
- The code you're testing
- Simple data transformations
- Pydantic validation
- Standard library functions (unless I/O)

## Test Naming
- Use descriptive names: `test_{what}_{scenario}_{expected}`
- Examples:
  - `test_create_tenant_valid_data_returns_201`
  - `test_get_tenant_unauthorized_returns_403`
  - `test_update_permission_clears_user_cache`

## Running Tests

### Command Line
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aihub --cov-report=html

# Run specific test file
pytest tests/unit/test_tenants.py

# Run specific test
pytest tests/unit/test_tenants.py::test_create_tenant

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

### CI/CD
- Run unit tests on every commit
- Run integration tests on PR
- Require minimum code coverage
- Block merge if tests fail

## Test Configuration

### conftest.py
- Configure test database
- Set up test fixtures
- Configure mocks
- Set up test app instance
- Override dependencies

### Environment Variables
- Use `.env.test` for test configuration
- Never commit real credentials
- Use test-specific endpoints

## Performance Testing
- Mark slow tests with `@pytest.mark.slow`
- Run quick tests by default
- Run slow tests in CI only
- Keep unit tests fast (< 100ms each)

## Coverage Goals
- Overall: 80%+
- Handlers: 90%+
- Core logic: 95%+
- Routes: 80%+
- Utilities: 90%+

## Test Documentation
- Add docstrings to complex tests
- Explain WHY, not WHAT
- Document test setup requirements
- Document known limitations
