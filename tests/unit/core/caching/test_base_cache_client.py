"""Unit tests for unifiedui/core/caching/client.py - BaseCacheClient abstract class."""

from abc import ABC

import pytest

from unifiedui.core.caching.cache import BaseCache
from unifiedui.core.caching.client import BaseCacheClient


class MockBaseCache(BaseCache):
    """Mock BaseCache for testing."""

    def __init__(self):
        self.storage = {}
        self.ping_status = True

    def get(self, key: str):
        return self.storage.get(key)

    def set(self, key: str, value, ttl=None):
        self.storage[key] = value

    def delete(self, key: str) -> bool:
        if key in self.storage:
            del self.storage[key]
            return True
        return False

    def delete_pattern(self, pattern: str) -> int:
        import re

        regex = pattern.replace("*", ".*")
        to_delete = [k for k in self.storage if re.match(regex, k)]
        for k in to_delete:
            del self.storage[k]
        return len(to_delete)

    def ping(self) -> bool:
        return self.ping_status

    def close(self) -> None:
        pass


class MockCacheClient(BaseCacheClient):
    """Mock implementation of BaseCacheClient for testing."""

    def __init__(self):
        self._cache = MockBaseCache()

    def get_cache(self) -> BaseCache:
        return self._cache


class TestBaseCacheClient:
    """Test suite for BaseCacheClient abstract base class."""

    def test_is_abstract_class(self):
        """Test that BaseCacheClient is an abstract class."""
        assert issubclass(BaseCacheClient, ABC)

    def test_cannot_instantiate_base_class(self):
        """Test that BaseCacheClient cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseCacheClient()

    def test_has_get_cache_method(self):
        """Test that BaseCacheClient defines get_cache abstract method."""
        assert hasattr(BaseCacheClient, "get_cache")
        assert callable(BaseCacheClient.get_cache)

    def test_has_get_method(self):
        """Test that BaseCacheClient has get method."""
        assert hasattr(BaseCacheClient, "get")
        assert callable(BaseCacheClient.get)

    def test_has_set_method(self):
        """Test that BaseCacheClient has set method."""
        assert hasattr(BaseCacheClient, "set")
        assert callable(BaseCacheClient.set)

    def test_has_delete_method(self):
        """Test that BaseCacheClient has delete method."""
        assert hasattr(BaseCacheClient, "delete")
        assert callable(BaseCacheClient.delete)

    def test_has_delete_pattern_method(self):
        """Test that BaseCacheClient has delete_pattern method."""
        assert hasattr(BaseCacheClient, "delete_pattern")
        assert callable(BaseCacheClient.delete_pattern)

    def test_has_ping_method(self):
        """Test that BaseCacheClient has ping method."""
        assert hasattr(BaseCacheClient, "ping")
        assert callable(BaseCacheClient.ping)

    def test_has_close_method(self):
        """Test that BaseCacheClient has close method."""
        assert hasattr(BaseCacheClient, "close")
        assert callable(BaseCacheClient.close)


class TestMockCacheClientImplementation:
    """Test suite for MockCacheClient to verify interface methods work."""

    def test_can_instantiate_concrete_implementation(self):
        """Test that concrete implementation can be instantiated."""
        client = MockCacheClient()
        assert isinstance(client, BaseCacheClient)

    def test_get_cache_returns_base_cache(self):
        """Test get_cache returns BaseCache instance."""
        client = MockCacheClient()
        cache = client.get_cache()
        assert isinstance(cache, BaseCache)

    def test_get_delegates_to_cache(self):
        """Test that get method delegates to underlying cache."""
        client = MockCacheClient()
        client.get_cache().set("key1", "value1")

        result = client.get("key1")
        assert result == "value1"

    def test_get_returns_none_for_missing_key(self):
        """Test get returns None for non-existent key."""
        client = MockCacheClient()
        result = client.get("nonexistent")
        assert result is None

    def test_set_delegates_to_cache(self):
        """Test that set method delegates to underlying cache."""
        client = MockCacheClient()
        client.set("key1", "value1")

        result = client.get_cache().get("key1")
        assert result == "value1"

    def test_set_with_ttl(self):
        """Test set method with TTL parameter."""
        client = MockCacheClient()
        client.set("key1", "value1", ttl=60)

        # Verify it was stored (TTL handling is cache-specific)
        assert client.get("key1") == "value1"

    def test_delete_delegates_to_cache(self):
        """Test that delete method delegates to underlying cache."""
        client = MockCacheClient()
        client.set("key1", "value1")

        result = client.delete("key1")
        assert result is True
        assert client.get("key1") is None

    def test_delete_returns_false_for_missing_key(self):
        """Test delete returns False for non-existent key."""
        client = MockCacheClient()
        result = client.delete("nonexistent")
        assert result is False

    def test_delete_pattern_delegates_to_cache(self):
        """Test that delete_pattern delegates to underlying cache."""
        client = MockCacheClient()
        client.set("user:1:data", "data1")
        client.set("user:2:data", "data2")
        client.set("tenant:1:data", "data3")

        count = client.delete_pattern("user:.*")
        assert count == 2
        assert client.get("user:1:data") is None
        assert client.get("tenant:1:data") is not None

    def test_ping_delegates_to_cache(self):
        """Test that ping method delegates to underlying cache."""
        client = MockCacheClient()
        assert client.ping() is True

    def test_ping_returns_false_when_disconnected(self):
        """Test ping returns False when cache is disconnected."""
        client = MockCacheClient()
        client.get_cache().ping_status = False
        assert client.ping() is False

    def test_close_delegates_to_cache(self):
        """Test that close method delegates to underlying cache."""
        client = MockCacheClient()
        # Should not raise exception
        client.close()

    def test_full_workflow(self):
        """Test complete cache client workflow."""
        client = MockCacheClient()

        # Verify connection
        assert client.ping() is True

        # Set multiple values
        client.set("key1", "value1")
        client.set("key2", {"nested": "data"})
        client.set("key3", [1, 2, 3])

        # Retrieve values
        assert client.get("key1") == "value1"
        assert client.get("key2") == {"nested": "data"}
        assert client.get("key3") == [1, 2, 3]

        # Delete one
        assert client.delete("key2") is True
        assert client.get("key2") is None

        # Others still exist
        assert client.get("key1") is not None
        assert client.get("key3") is not None

        # Close connection
        client.close()

    def test_set_overwrites_existing_value(self):
        """Test that set overwrites existing value."""
        client = MockCacheClient()
        client.set("key1", "value1")
        client.set("key1", "value2")

        assert client.get("key1") == "value2"

    def test_delete_pattern_with_no_matches(self):
        """Test delete_pattern with no matching keys."""
        client = MockCacheClient()
        client.set("key1", "value1")

        count = client.delete_pattern("nomatch:.*")
        assert count == 0
        assert client.get("key1") is not None

    def test_complex_data_types(self):
        """Test caching complex data types."""
        client = MockCacheClient()

        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "string": "text",
            "number": 42,
            "bool": True,
            "none": None,
        }

        client.set("complex", complex_data)
        result = client.get("complex")
        assert result == complex_data
