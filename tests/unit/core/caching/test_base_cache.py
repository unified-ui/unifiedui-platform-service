"""Unit tests for unifiedui/core/caching/cache.py - BaseCache abstract class."""

from abc import ABC

import pytest

from unifiedui.core.caching.cache import BaseCache


class MockCache(BaseCache):
    """Mock implementation of BaseCache for testing."""

    def __init__(self):
        self.storage = {}
        self.ping_result = True
        self.close_called = False

    def get(self, key: str):
        return self.storage.get(key)

    def set(self, key: str, value, ttl=None):
        self.storage[key] = {"value": value, "ttl": ttl}

    def delete(self, key: str) -> bool:
        if key in self.storage:
            del self.storage[key]
            return True
        return False

    def delete_pattern(self, pattern: str) -> int:
        # Simple pattern matching: * wildcard
        import re

        regex_pattern = pattern.replace("*", ".*")
        keys_to_delete = [k for k in self.storage if re.match(regex_pattern, k)]
        for key in keys_to_delete:
            del self.storage[key]
        return len(keys_to_delete)

    def ping(self) -> bool:
        return self.ping_result

    def close(self) -> None:
        self.close_called = True


class TestBaseCache:
    """Test suite for BaseCache abstract base class."""

    def test_is_abstract_class(self):
        """Test that BaseCache is an abstract class."""
        assert issubclass(BaseCache, ABC)

    def test_cannot_instantiate_base_class(self):
        """Test that BaseCache cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseCache()

    def test_has_get_method(self):
        """Test that BaseCache defines get abstract method."""
        assert hasattr(BaseCache, "get")
        assert callable(BaseCache.get)

    def test_has_set_method(self):
        """Test that BaseCache defines set abstract method."""
        assert hasattr(BaseCache, "set")
        assert callable(BaseCache.set)

    def test_has_delete_method(self):
        """Test that BaseCache defines delete abstract method."""
        assert hasattr(BaseCache, "delete")
        assert callable(BaseCache.delete)

    def test_has_delete_pattern_method(self):
        """Test that BaseCache defines delete_pattern abstract method."""
        assert hasattr(BaseCache, "delete_pattern")
        assert callable(BaseCache.delete_pattern)

    def test_has_ping_method(self):
        """Test that BaseCache defines ping abstract method."""
        assert hasattr(BaseCache, "ping")
        assert callable(BaseCache.ping)

    def test_has_close_method(self):
        """Test that BaseCache defines close abstract method."""
        assert hasattr(BaseCache, "close")
        assert callable(BaseCache.close)


class TestMockCacheImplementation:
    """Test suite for MockCache implementation to verify interface."""

    def test_mock_cache_can_be_instantiated(self):
        """Test that concrete implementation can be instantiated."""
        cache = MockCache()
        assert isinstance(cache, BaseCache)

    def test_get_returns_none_for_missing_key(self):
        """Test get method returns None when key doesn't exist."""
        cache = MockCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_set_and_get(self):
        """Test setting and retrieving a value."""
        cache = MockCache()
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == {"value": "value1", "ttl": None}

    def test_set_with_ttl(self):
        """Test setting a value with TTL."""
        cache = MockCache()
        cache.set("key1", "value1", ttl=60)
        result = cache.get("key1")
        assert result["ttl"] == 60

    def test_delete_existing_key(self):
        """Test deleting an existing key."""
        cache = MockCache()
        cache.set("key1", "value1")
        result = cache.delete("key1")
        assert result is True
        assert cache.get("key1") is None

    def test_delete_nonexistent_key(self):
        """Test deleting a non-existent key returns False."""
        cache = MockCache()
        result = cache.delete("nonexistent")
        assert result is False

    def test_delete_pattern_wildcard_prefix(self):
        """Test deleting keys with pattern matching (prefix)."""
        cache = MockCache()
        cache.set("user:1:data", "data1")
        cache.set("user:2:data", "data2")
        cache.set("tenant:1:data", "data3")

        deleted_count = cache.delete_pattern("user:.*")
        assert deleted_count == 2
        assert cache.get("user:1:data") is None
        assert cache.get("user:2:data") is None
        assert cache.get("tenant:1:data") is not None

    def test_delete_pattern_wildcard_suffix(self):
        """Test deleting keys with pattern matching (suffix)."""
        cache = MockCache()
        cache.set("data:user", "data1")
        cache.set("data:tenant", "data2")
        cache.set("info:user", "data3")

        deleted_count = cache.delete_pattern("data:.*")
        assert deleted_count == 2

    def test_delete_pattern_no_matches(self):
        """Test delete_pattern returns 0 when no keys match."""
        cache = MockCache()
        cache.set("key1", "value1")

        deleted_count = cache.delete_pattern("nomatch:.*")
        assert deleted_count == 0

    def test_ping_returns_true(self):
        """Test ping method returns True when connection is alive."""
        cache = MockCache()
        assert cache.ping() is True

    def test_ping_returns_false_when_disconnected(self):
        """Test ping can return False (simulating disconnection)."""
        cache = MockCache()
        cache.ping_result = False
        assert cache.ping() is False

    def test_close_method(self):
        """Test close method is called."""
        cache = MockCache()
        cache.close()
        assert cache.close_called is True

    def test_multiple_operations(self):
        """Test multiple cache operations in sequence."""
        cache = MockCache()

        # Set multiple values
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Verify all exist
        assert cache.get("key1") is not None
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None

        # Delete one
        cache.delete("key2")
        assert cache.get("key2") is None

        # Others still exist
        assert cache.get("key1") is not None
        assert cache.get("key3") is not None
