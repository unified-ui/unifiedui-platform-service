---
applyTo: 'tests/**'
---

# AIHub Testing Specifications

## Testing Philosophy
- Write tests BEFORE or alongside production code
- Aim for 80%+ code coverage
- Test behavior, not implementation
- Keep tests isolated and independent

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
