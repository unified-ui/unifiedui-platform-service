"""Test configuration and fixtures."""
import os
import pytest
import logging
import tempfile
from typing import Generator
from fastapi.testclient import TestClient
import fakeredis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from aihub.app import create_app
from aihub.core.database.models import Base
from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.config import DatabaseConfig
from aihub.caching.redis.cache import RedisCache
from aihub.caching.redis.client import RedisCacheClient
from aihub.caching.client import CacheClient
from aihub.core.identity.mock import MockIdentityToken


# Test database - use a temporary file instead of :memory: to share between connections
_test_db_file = None

def get_test_db_url():
    """Get test database URL with temporary file."""
    global _test_db_file
    if _test_db_file is None:
        # Create a temporary file for the test database
        fd, _test_db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)  # Close the file descriptor, SQLite will open it
    return f"sqlite:///{_test_db_file}"


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine with SQLite file."""
    TEST_DATABASE_URL = get_test_db_url()
    
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        echo=False
    )
    
    # Create all tables
    logger.info(f"Creating tables, available tables before: {Base.metadata.tables.keys()}")
    Base.metadata.create_all(bind=engine)
    
    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Tables created in test database: {tables}")
    
    yield engine
    
    # Drop all tables after test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    
    # Clean up the temporary file
    global _test_db_file
    if _test_db_file and os.path.exists(_test_db_file):
        os.unlink(_test_db_file)
        _test_db_file = None


@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    SessionLocal = sessionmaker(bind=test_db_engine)
    session = SessionLocal()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def test_db_client(test_db_engine):
    """Create a test database client with SQLite file."""
    TEST_DATABASE_URL = get_test_db_url()
    
    config = DatabaseConfig(database_url=TEST_DATABASE_URL)
    client = SQLAlchemyClient(config=config)
    
    # Replace engine and SessionLocal with test instances
    client.engine.dispose()  # Close the engine created in __init__
    client.engine = test_db_engine
    client.SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )
    
    yield client
    
    client.close()


@pytest.fixture(scope="function")
def fake_redis_client():
    """Create a fake Redis client for testing."""
    # Create fake Redis server
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    
    # Create RedisCache instance with fake client
    redis_cache = RedisCache(host="localhost", port=6379, db=1, default_ttl=3600)
    redis_cache.client = fake_redis
    
    return redis_cache


@pytest.fixture(scope="function")
def test_cache_client(fake_redis_client):
    """Create a test cache client with fake Redis."""
    redis_client = RedisCacheClient(host="localhost", port=6379, db=1)
    redis_client._cache = fake_redis_client
    
    cache_client = CacheClient(redis_client)
    
    # Clear cache before each test
    fake_redis_client.client.flushdb()
    
    return cache_client


def create_test_user(user_id: str = "test-user-123", name: str = "Test User", mail: str = None):
    """
    Create a test user with JWT token.
    
    Args:
        user_id: User ID
        name: User's display name
        mail: User's email
        
    Returns:
        MockIdentityToken instance
    """
    logger.info(f"Creating test user: user_id={user_id}, name={name}, mail={mail}")
    token = MockIdentityToken(user_id=user_id, name=name, mail=mail)
    logger.info(f"Generated JWT token: {token.get_token()[:50]}...")
    return token


@pytest.fixture(scope="function")
def test_client(test_db_client, test_cache_client):
    """Create a FastAPI test client with test database and cache."""
    logger.info("Creating FastAPI test client")
    logger.info(f"Test DB Engine: {test_db_client.engine}")
    logger.info(f"Test DB URL: {test_db_client.config.database_url}")
    
    # Reset global singletons before creating app
    import aihub.handlers.dependencies.database as db_dep
    import aihub.handlers.dependencies.cache as cache_dep
    db_dep._db_client = None
    cache_dep._cache_client = None
    
    app = create_app()
    logger.info(f"App created, routes: {[route.path for route in app.routes if hasattr(route, 'path')]}")
    
    # Override dependencies
    from aihub.handlers.dependencies import get_db_client
    from aihub.caching.dependencies import get_cache_client
    
    def get_test_db_client():
        logger.info(f"get_db_client override called, returning test client: {test_db_client.engine}")
        return test_db_client
    
    app.dependency_overrides[get_db_client] = get_test_db_client
    app.dependency_overrides[get_cache_client] = lambda: test_cache_client
    logger.info("Dependency overrides set")
    
    client = TestClient(app)
    
    # Store references for access in tests
    client.db_client = test_db_client
    client.cache_client = test_cache_client
    client.create_test_user = create_test_user
    
    yield client
    
    # Clean up
    app.dependency_overrides.clear()
    db_dep._db_client = None
    cache_dep._cache_client = None


@pytest.fixture
def test_user_token():
    """Create a default test user token."""
    logger.info("Creating default test user token")
    token = create_test_user()
    logger.info(f"Default test user token created")
    return token


@pytest.fixture
def auth_headers(test_user_token):
    """Generate authentication headers for testing with real JWT."""
    logger.info("Generating auth headers")
    headers = {
        "Authorization": f"Bearer {test_user_token.get_token()}",
        "Content-Type": "application/json"
    }
    logger.info(f"Auth headers: Authorization=Bearer {test_user_token.get_token()[:30]}...")
    return headers


@pytest.fixture
def sample_tenant_data():
    """Sample tenant data for testing."""
    return {
        "name": "Test Tenant",
        "description": "A test tenant"
    }


@pytest.fixture
def sample_update_tenant_data():
    """Sample tenant update data for testing."""
    return {
        "name": "Updated Test Tenant",
        "description": "An updated test tenant"
    }
