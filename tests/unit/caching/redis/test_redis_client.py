"""Unit tests for unifiedui/caching/redis/client.py - RedisCacheClient."""

from unittest.mock import Mock, patch

from unifiedui.caching.redis.client import RedisCacheClient
from unifiedui.core.caching.cache import BaseCache
from unifiedui.core.caching.client import BaseCacheClient


class TestRedisCacheClient:
    """Test suite for RedisCacheClient."""

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_initialization_with_defaults(self, mock_redis_cache_class):
        """Test initialization with default parameters."""
        mock_cache = Mock()
        mock_redis_cache_class.return_value = mock_cache

        RedisCacheClient()

        mock_redis_cache_class.assert_called_once_with(
            host="localhost", port=6379, db=0, password=None, default_ttl=3600
        )

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_initialization_with_custom_params(self, mock_redis_cache_class):
        """Test initialization with custom parameters."""
        mock_cache = Mock()
        mock_redis_cache_class.return_value = mock_cache

        RedisCacheClient(host="custom.redis.host", port=6380, db=2, password="secret123", default_ttl=7200)

        mock_redis_cache_class.assert_called_once_with(
            host="custom.redis.host", port=6380, db=2, password="secret123", default_ttl=7200
        )

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_is_base_cache_client_implementation(self, mock_redis_cache_class):
        """Test that RedisCacheClient implements BaseCacheClient."""
        client = RedisCacheClient()
        assert isinstance(client, BaseCacheClient)

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_get_cache_returns_redis_cache(self, mock_redis_cache_class):
        """Test get_cache returns RedisCache instance."""
        mock_cache = Mock(spec=BaseCache)
        mock_redis_cache_class.return_value = mock_cache

        client = RedisCacheClient()
        result = client.get_cache()

        assert result is mock_cache

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_inherits_base_client_methods(self, mock_redis_cache_class):
        """Test that inherited methods from BaseCacheClient work."""
        mock_cache = Mock()
        mock_cache.get.return_value = "test_value"
        mock_cache.delete.return_value = True
        mock_cache.delete_pattern.return_value = 5
        mock_cache.ping.return_value = True
        mock_redis_cache_class.return_value = mock_cache

        client = RedisCacheClient()

        # Test inherited get
        assert client.get("key1") == "test_value"
        mock_cache.get.assert_called_with("key1")

        # Test inherited set
        client.set("key2", "value2", ttl=60)
        mock_cache.set.assert_called_with("key2", "value2", 60)

        # Test inherited delete
        delete_result = client.delete("key1")
        assert delete_result is True
        mock_cache.delete.assert_called_with("key1")

        # Test inherited delete_pattern
        pattern_result = client.delete_pattern("user:*")
        assert pattern_result == 5
        mock_cache.delete_pattern.assert_called_with("user:*")

        # Test inherited ping
        assert client.ping() is True
        mock_cache.ping.assert_called_once()

        # Test inherited close
        client.close()
        mock_cache.close.assert_called_once()

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_multiple_clients_have_separate_caches(self, mock_redis_cache_class):
        """Test that multiple clients have separate cache instances."""
        mock_cache1 = Mock()
        mock_cache2 = Mock()
        mock_redis_cache_class.side_effect = [mock_cache1, mock_cache2]

        client1 = RedisCacheClient()
        client2 = RedisCacheClient()

        assert client1.get_cache() is not client2.get_cache()

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_password_param_is_optional(self, mock_redis_cache_class):
        """Test that password parameter is optional."""
        mock_cache = Mock()
        mock_redis_cache_class.return_value = mock_cache

        # Without password
        RedisCacheClient()
        call_kwargs = mock_redis_cache_class.call_args[1]
        assert call_kwargs["password"] is None

        # With password
        mock_redis_cache_class.reset_mock()
        RedisCacheClient(password="secret")
        call_kwargs = mock_redis_cache_class.call_args[1]
        assert call_kwargs["password"] == "secret"

    @patch("unifiedui.caching.redis.client.RedisCache")
    def test_default_ttl_configuration(self, mock_redis_cache_class):
        """Test default TTL configuration."""
        mock_cache = Mock()
        mock_redis_cache_class.return_value = mock_cache

        RedisCacheClient(default_ttl=5000)
        call_kwargs = mock_redis_cache_class.call_args[1]
        assert call_kwargs["default_ttl"] == 5000
