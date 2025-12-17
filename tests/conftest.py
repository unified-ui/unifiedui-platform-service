"""Test configuration and fixtures."""
import os
import pytest
from typing import Generator, Optional
from unittest.mock import Mock, MagicMock
from fastapi.testclient import TestClient
import fakeredis

from aihub.app import create_app
from aihub.docdatabase.client import DatabaseClient
from aihub.caching.client import CacheClient
from aihub.core.identity.users import ContextIdentityUser


# Set test environment variables
os.environ["DOCUMENT_DATABASE"] = "MONGO_DB"
os.environ["MONGODB_CONNECTION_STRING"] = "mongodb://test:test@localhost:27017"
os.environ["MONGODB_DATABASE_NAME"] = "aihub_test"
os.environ["CACHE_ENABLED"] = "true"
os.environ["CACHE_BACKEND"] = "REDIS"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "1"  # Use different DB for tests
os.environ["REDIS_PASSWORD"] = "admin"


@pytest.fixture
def mock_db_client():
    """Create a mock database client."""
    mock_client = Mock(spec=DatabaseClient)
    
    # Mock tenants collection
    mock_tenants = MagicMock()
    mock_client.tenants = mock_tenants
    
    # Mock permissions collection
    mock_permissions = MagicMock()
    mock_client.permissions = mock_permissions
    
    # Mock health check
    mock_client.health_check.return_value = True
    
    return mock_client


@pytest.fixture
def fake_redis_client():
    """Create a fake Redis client for testing."""
    from aihub.caching.redis.cache import RedisCache
    
    # Create fake Redis server
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    
    # Create RedisCache instance with fake client
    redis_cache = RedisCache(host="localhost", port=6379, db=1, default_ttl=3600)
    redis_cache.client = fake_redis
    
    return redis_cache


@pytest.fixture
def mock_cache_client(fake_redis_client):
    """Create a mock cache client with fake Redis."""
    from aihub.caching.redis.client import RedisCacheClient
    from aihub.caching.client import CacheClient
    
    redis_client = RedisCacheClient(host="localhost", port=6379, db=1)
    redis_client._cache = fake_redis_client
    
    cache_client = CacheClient(redis_client)
    
    # Clear cache before each test
    fake_redis_client.client.flushdb()
    
    return cache_client


@pytest.fixture
def mock_identity_user(mock_db_client, mock_cache_client):
    """Create a mock authenticated user."""
    # Mock the token and identity
    mock_user = Mock(spec=ContextIdentityUser)
    
    # Create mock identity object
    mock_identity = Mock()
    mock_identity.get_id.return_value = "test-user-123"
    mock_identity.get_display_name.return_value = "Test User"
    mock_identity.get_mail.return_value = "test@example.com"
    mock_identity.get_firstname.return_value = "Test"
    mock_identity.get_lastname.return_value = "User"
    mock_identity.get_identity_provider.return_value = "entra_id"
    mock_identity.get_identity_tenant_id.return_value = "tenant-123"
    
    mock_user.identity = mock_identity
    
    # Mock groups
    mock_user.groups = []
    mock_user.custom_groups = []
    mock_user.tenants = []
    
    return mock_user


@pytest.fixture
def test_client(mock_db_client, mock_cache_client, mock_identity_user):
    """Create a FastAPI test client with mocked dependencies."""
    app = create_app()
    
    # Override dependencies
    from aihub.database.dependencies import get_db_client
    from aihub.caching.dependencies import get_cache_client
    
    app.dependency_overrides[get_db_client] = lambda: mock_db_client
    app.dependency_overrides[get_cache_client] = lambda: mock_cache_client
    
    client = TestClient(app)
    
    # Store mocks on client for access in tests
    client.mock_db = mock_db_client
    client.mock_cache = mock_cache_client
    client.mock_user = mock_identity_user
    
    yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Generate authentication headers for testing."""
    return {
        "Authorization": "Bearer test-token-123",
        "Content-Type": "application/json"
    }


@pytest.fixture
def sample_tenant_data():
    """Sample tenant data for testing."""
    return {
        "name": "Test Tenant",
        "description": "A test tenant",
        "meta": {"key": "value"}
    }


@pytest.fixture
def sample_permission_data():
    """Sample permission data for testing."""
    return {
        "user_id": "user-456",
        "action": "read"
    }
