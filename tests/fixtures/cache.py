"""Cache fixtures for testing."""

import logging

import fakeredis
import pytest

from unifiedui.caching.client import CacheClient
from unifiedui.caching.redis.cache import RedisCache
from unifiedui.caching.redis.client import RedisCacheClient

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def fake_redis_client() -> RedisCache:
    """Create a fake Redis client for testing."""
    # Create fake Redis server
    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    # Create RedisCache instance with fake client
    redis_cache = RedisCache(host="localhost", port=6379, db=1, default_ttl=3600)
    redis_cache.client = fake_redis

    return redis_cache


@pytest.fixture(scope="function")
def test_cache_client(fake_redis_client: RedisCache) -> CacheClient:
    """Create a test cache client with fake Redis."""
    redis_client = RedisCacheClient(host="localhost", port=6379, db=1)
    redis_client._cache = fake_redis_client

    cache_client = CacheClient(redis_client)

    # Clear ALL cache databases before each test
    fake_redis_client.client.flushall()

    return cache_client
