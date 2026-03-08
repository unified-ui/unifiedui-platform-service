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
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Import all fixtures - pytest will automatically discover them
from tests.fixtures.auth import (
    auth_headers,
    create_auth_headers,
    create_test_user,
    test_user_token,
)
from tests.fixtures.cache import (
    fake_redis_client,
    test_cache_client,
)
from tests.fixtures.client import (
    test_client,
)
from tests.fixtures.data import (
    sample_tenant_data,
    sample_update_tenant_data,
)
from tests.fixtures.database import (
    test_db_client,
    test_db_engine,
    test_db_session,
)
from tests.fixtures.vault import (
    mock_vault_client,
)

__all__ = [
    "auth_headers",
    "create_auth_headers",
    # Auth fixtures
    "create_test_user",
    # Cache fixtures
    "fake_redis_client",
    # Vault fixtures
    "mock_vault_client",
    # Data fixtures
    "sample_tenant_data",
    "sample_update_tenant_data",
    "test_cache_client",
    # Client fixtures
    "test_client",
    "test_db_client",
    # Database fixtures
    "test_db_engine",
    "test_db_session",
    "test_user_token",
]
