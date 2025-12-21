"""Test configuration and fixtures.

This file imports all fixtures from the fixtures package and configures pytest.
Actual fixture implementations are organized in the fixtures/ directory:
    - fixtures/database.py: Database-related fixtures
    - fixtures/cache.py: Cache and Redis fixtures
    - fixtures/auth.py: Authentication and user fixtures
    - fixtures/client.py: FastAPI test client fixtures
    - fixtures/data.py: Sample data fixtures
"""
import logging

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import all fixtures - pytest will automatically discover them
from tests.fixtures.database import (
    test_db_engine,
    test_db_session,
    test_db_client,
)
from tests.fixtures.cache import (
    fake_redis_client,
    test_cache_client,
)
from tests.fixtures.auth import (
    create_test_user,
    create_auth_headers,
    test_user_token,
    auth_headers,
)
from tests.fixtures.client import (
    test_client,
)
from tests.fixtures.data import (
    sample_tenant_data,
    sample_update_tenant_data,
)
from tests.fixtures.vault import (
    mock_vault_client,
)

__all__ = [
    # Database fixtures
    "test_db_engine",
    "test_db_session",
    "test_db_client",
    # Cache fixtures
    "fake_redis_client",
    "test_cache_client",
    # Auth fixtures
    "create_test_user",
    "create_auth_headers",
    "test_user_token",
    "auth_headers",
    # Client fixtures
    "test_client",
    # Data fixtures
    "sample_tenant_data",
    "sample_update_tenant_data",
    # Vault fixtures
    "mock_vault_client",
]
