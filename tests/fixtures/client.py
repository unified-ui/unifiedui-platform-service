"""FastAPI test client fixtures."""
import logging
import pytest
from typing import Generator
from fastapi.testclient import TestClient

from aihub.app import create_app
from aihub.core.database.client import SQLAlchemyClient
from aihub.caching.client import CacheClient
from aihub.caching.redis.cache import RedisCache
from tests.fixtures.auth import create_test_user, create_auth_headers

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def test_client(
    test_db_client: SQLAlchemyClient,
    test_cache_client: CacheClient,
    fake_redis_client: RedisCache,
    mock_vault_client
) -> Generator[TestClient, None, None]:
    """Create a FastAPI test client with test database and cache."""
    logger.info("Creating FastAPI test client")
    logger.info(f"Test DB Engine: {test_db_client.engine}")
    logger.info(f"Test DB URL: {test_db_client.config.database_url}")
    
    # Set test clients as global singletons BEFORE app creation
    import aihub.handlers.dependencies.database as db_dep
    import aihub.caching.dependencies as old_cache_dep
    import aihub.handlers.dependencies.cache as new_cache_dep
    import aihub.handlers.dependencies.vault as vault_dep
    
    # Clear ALL cache databases before test to avoid pollution from previous tests
    fake_redis_client.client.flushall()
    logger.info("Cache cleared before test")
    
    db_dep._db_client = test_db_client
    
    # Set BOTH cache client globals (old and new)
    old_cache_dep._cache_client = test_cache_client
    new_cache_dep._cache_client = test_cache_client
    new_cache_dep._cache_initialized = True
    
    # Set vault client global
    vault_dep._vault_client = mock_vault_client
    
    # CRITICAL: Clear the LRU cache to force get_cache_client() to use our test client
    old_cache_dep.get_cache_client.cache_clear()
    vault_dep.get_vault_client.cache_clear()
    
    logger.info("Set test clients as global singletons")
    
    app = create_app()
    logger.info(f"App created")
    
    client = TestClient(app)
    
    # Store references for access in tests
    client.db_client = test_db_client
    client.cache_client = test_cache_client
    client.vault_client = mock_vault_client
    
    # Add helper methods to the client for easier test usage
    client.create_test_user = create_test_user
    client.create_auth_headers = create_auth_headers
    
    yield client
    
    # Clean up - clear cache, reset singletons, and dispose connections
    try:
        fake_redis_client.client.flushall()  # Clear ALL DBs to avoid test pollution
        logger.info("Cache cleared after test")
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")
    
    db_dep._db_client = None
    old_cache_dep._cache_client = None
    new_cache_dep._cache_client = None
    new_cache_dep._cache_initialized = False
    vault_dep._vault_client = None
    logger.info("Singletons reset")
