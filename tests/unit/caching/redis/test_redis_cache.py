"""Unit tests for unifiedui/caching/redis/cache.py - RedisCache."""
import pytest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from unifiedui.caching.redis.cache import RedisCache, DateTimeEncoder
from unifiedui.core.caching.cache import BaseCache


class TestDateTimeEncoder:
    """Test suite for DateTimeEncoder JSON encoder."""
    
    def test_encodes_datetime(self):
        """Test that datetime objects are encoded to ISO format."""
        dt = datetime(2025, 12, 21, 10, 30, 45)
        result = json.dumps({"timestamp": dt}, cls=DateTimeEncoder)
        assert "2025-12-21T10:30:45" in result
    
    def test_encodes_regular_types(self):
        """Test that regular types are encoded normally."""
        data = {"string": "test", "number": 42, "bool": True}
        result = json.dumps(data, cls=DateTimeEncoder)
        assert json.loads(result) == data
    
    def test_encodes_nested_datetime(self):
        """Test encoding nested datetime in complex structures."""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        data = {
            "record": {
                "created_at": dt,
                "name": "test"
            }
        }
        result = json.dumps(data, cls=DateTimeEncoder)
        assert "2025-01-01T12:00:00" in result


class TestRedisCache:
    """Test suite for RedisCache implementation."""
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_initialization_with_defaults(self, mock_redis_class):
        """Test RedisCache initialization with default parameters."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        
        cache = RedisCache()
        
        mock_redis_class.assert_called_once_with(
            host="localhost",
            port=6379,
            db=0,
            password=None,
            decode_responses=True
        )
        assert cache.default_ttl == 3600
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_initialization_with_custom_params(self, mock_redis_class):
        """Test RedisCache initialization with custom parameters."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        
        cache = RedisCache(
            host="redis.example.com",
            port=6380,
            db=2,
            password="secret",
            default_ttl=7200
        )
        
        mock_redis_class.assert_called_once_with(
            host="redis.example.com",
            port=6380,
            db=2,
            password="secret",
            decode_responses=True
        )
        assert cache.default_ttl == 7200
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_is_base_cache_implementation(self, mock_redis_class):
        """Test that RedisCache implements BaseCache."""
        cache = RedisCache()
        assert isinstance(cache, BaseCache)
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_get_returns_deserialized_value(self, mock_redis_class):
        """Test get method returns deserialized JSON value."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.return_value = '{"key": "value"}'
        
        cache = RedisCache()
        result = cache.get("test_key")
        
        mock_client.get.assert_called_once_with("test_key")
        assert result == {"key": "value"}
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_get_returns_none_when_key_missing(self, mock_redis_class):
        """Test get returns None when key doesn't exist."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.return_value = None
        
        cache = RedisCache()
        result = cache.get("missing_key")
        
        assert result is None
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_get_handles_json_decode_error(self, mock_redis_class):
        """Test get handles JSON decode errors gracefully."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.side_effect = Exception("JSON decode error")
        
        cache = RedisCache()
        result = cache.get("bad_json_key")
        
        assert result is None
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_set_with_default_ttl(self, mock_redis_class):
        """Test set method uses default TTL when not specified."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        
        cache = RedisCache(default_ttl=3600)
        cache.set("key1", {"data": "value"})
        
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args
        assert call_args[0][0] == "key1"
        assert call_args[0][1] == 3600
        assert json.loads(call_args[0][2]) == {"data": "value"}
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_set_with_custom_ttl(self, mock_redis_class):
        """Test set method with custom TTL."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        
        cache = RedisCache()
        cache.set("key1", "value1", ttl=120)
        
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args
        assert call_args[0][1] == 120
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_set_serializes_datetime(self, mock_redis_class):
        """Test set method serializes datetime objects."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        
        cache = RedisCache()
        dt = datetime(2025, 12, 21, 10, 30, 0)
        cache.set("key1", {"timestamp": dt})
        
        call_args = mock_client.setex.call_args
        serialized = call_args[0][2]
        assert "2025-12-21T10:30:00" in serialized
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_set_handles_serialization_error(self, mock_redis_class):
        """Test set handles serialization errors gracefully."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.setex.side_effect = Exception("Serialization error")
        
        cache = RedisCache()
        # Should not raise exception
        cache.set("key1", "value1")
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_delete_existing_key(self, mock_redis_class):
        """Test delete method for existing key."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.delete.return_value = 1
        
        cache = RedisCache()
        result = cache.delete("key1")
        
        mock_client.delete.assert_called_once_with("key1")
        assert result is True
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_delete_nonexistent_key(self, mock_redis_class):
        """Test delete method for non-existent key."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.delete.return_value = 0
        
        cache = RedisCache()
        result = cache.delete("missing_key")
        
        assert result is False
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_delete_handles_error(self, mock_redis_class):
        """Test delete handles errors gracefully."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.delete.side_effect = Exception("Delete error")
        
        cache = RedisCache()
        result = cache.delete("key1")
        
        assert result is False
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_delete_pattern_matches_keys(self, mock_redis_class):
        """Test delete_pattern deletes matching keys."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.keys.return_value = ["user:1", "user:2", "user:3"]
        mock_client.delete.return_value = 3
        
        cache = RedisCache()
        count = cache.delete_pattern("user:*")
        
        mock_client.keys.assert_called_once_with("user:*")
        mock_client.delete.assert_called_once_with("user:1", "user:2", "user:3")
        assert count == 3
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_delete_pattern_no_matches(self, mock_redis_class):
        """Test delete_pattern with no matching keys."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.keys.return_value = []
        
        cache = RedisCache()
        count = cache.delete_pattern("nomatch:*")
        
        assert count == 0
        mock_client.delete.assert_not_called()
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_delete_pattern_handles_error(self, mock_redis_class):
        """Test delete_pattern handles errors gracefully."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.keys.side_effect = Exception("Pattern error")
        
        cache = RedisCache()
        count = cache.delete_pattern("user:*")
        
        assert count == 0
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_ping_success(self, mock_redis_class):
        """Test ping returns True when connection is alive."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True
        
        cache = RedisCache()
        result = cache.ping()
        
        mock_client.ping.assert_called_once()
        assert result is True
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_ping_failure(self, mock_redis_class):
        """Test ping returns False when connection fails."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.side_effect = Exception("Connection error")
        
        cache = RedisCache()
        result = cache.ping()
        
        assert result is False
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_close_connection(self, mock_redis_class):
        """Test close method closes Redis connection."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        
        cache = RedisCache()
        cache.close()
        
        mock_client.close.assert_called_once()
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_close_handles_error(self, mock_redis_class):
        """Test close handles errors gracefully."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.close.side_effect = Exception("Close error")
        
        cache = RedisCache()
        # Should not raise exception
        cache.close()
    
    @patch('unifiedui.caching.redis.cache.redis.Redis')
    def test_full_cache_workflow(self, mock_redis_class):
        """Test complete cache workflow."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.get.return_value = '{"data": "value"}'
        mock_client.delete.return_value = 1
        
        cache = RedisCache()
        
        # Ping
        assert cache.ping() is True
        
        # Set
        cache.set("key1", {"data": "value"})
        
        # Get
        result = cache.get("key1")
        assert result == {"data": "value"}
        
        # Delete
        assert cache.delete("key1") is True
        
        # Close
        cache.close()
