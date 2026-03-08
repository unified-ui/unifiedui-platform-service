"""FastAPI test client fixtures."""

import logging
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.auth import create_auth_headers, create_test_user
from unifiedui.app import create_app
from unifiedui.caching.client import CacheClient
from unifiedui.caching.redis.cache import RedisCache
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import Organization, OrganizationMember

logger = logging.getLogger(__name__)

TEST_ORGANIZATION_ID = "test-org-00000000"
TEST_IDENTITY_PROVIDER = "MOCK"
TEST_IDENTITY_TENANT_ID = "test-tenant-123"
TEST_DEFAULT_USER_ID = "test-user-123"


@pytest.fixture(scope="function")
def test_client(
    test_db_client: SQLAlchemyClient, test_cache_client: CacheClient, fake_redis_client: RedisCache, mock_vault_client
) -> Generator[TestClient]:
    """Create a FastAPI test client with test database and cache."""
    logger.info("Creating FastAPI test client")
    logger.info(f"Test DB Engine: {test_db_client.engine}")
    logger.info(f"Test DB URL: {test_db_client.config.database_url}")

    # Set test clients as global singletons BEFORE app creation
    import unifiedui.caching.dependencies as old_cache_dep
    import unifiedui.handlers.dependencies.cache as new_cache_dep
    import unifiedui.handlers.dependencies.database as db_dep
    import unifiedui.handlers.dependencies.vault as vault_dep

    # Clear ALL cache databases before test to avoid pollution from previous tests
    fake_redis_client.client.flushall()
    logger.info("Cache cleared before test")

    db_dep._db_client = test_db_client

    # Set BOTH cache client globals (old and new)
    old_cache_dep._cache_client = test_cache_client
    new_cache_dep._cache_client = test_cache_client
    new_cache_dep._cache_initialized = True

    # Set vault client globals (both _vault_client and _secrets_vault)
    vault_dep._vault_client = mock_vault_client
    vault_dep._secrets_vault = mock_vault_client

    # CRITICAL: Clear the LRU cache to force get_cache_client() to use our test client
    old_cache_dep.get_cache_client.cache_clear()
    vault_dep.get_vault_client.cache_clear()

    logger.info("Set test clients as global singletons")

    _seed_test_organization(test_db_client)

    app = create_app()
    logger.info("App created")

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
    vault_dep._secrets_vault = None
    logger.info("Singletons reset")


def _seed_test_organization(db_client: SQLAlchemyClient) -> None:
    """Seed a test organization matching the mock identity provider.

    Creates an Organization with identity_provider=MOCK and
    identity_tenant_id=test-tenant-123 so that all mock users
    can resolve their organization_context.
    Also creates an OrganizationMember for the default test user.
    """
    with db_client.get_session() as session:
        org = Organization(
            id=TEST_ORGANIZATION_ID,
            name="Test Organization",
            slug="test-organization",
            identity_provider=TEST_IDENTITY_PROVIDER,
            identity_tenant_id=TEST_IDENTITY_TENANT_ID,
            subscription_tier="free",
            is_active=True,
            created_by="system",
            updated_by="system",
        )
        session.add(org)
        session.flush()

        member = OrganizationMember(
            id=str(uuid.uuid4()),
            organization_id=TEST_ORGANIZATION_ID,
            principal_id=TEST_DEFAULT_USER_ID,
            principal_type="IDENTITY_USER",
            role="ORGANISATION_GLOBAL_ADMIN",
            created_by="system",
            updated_by="system",
        )
        session.add(member)
    logger.info("Seeded test organization: %s", TEST_ORGANIZATION_ID)
