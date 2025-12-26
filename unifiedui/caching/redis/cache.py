"""Redis cache implementation."""
import json
from typing import Any, Optional
from datetime import datetime
import redis

from aihub.core.caching.cache import BaseCache
from aihub.logger import get_logger

logger = get_logger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RedisCache(BaseCache):
    """Redis implementation of the BaseCache interface."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600
    ):
        """
        Initialize Redis cache client.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional)
            default_ttl: Default TTL in seconds (default: 1 hour)
        """
        self.default_ttl = default_ttl
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
        logger.info(f"Redis cache initialized: {host}:{port}/{db}")

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from Redis cache.
        
        Args:
            key: Cache key
            
        Returns:
            Deserialized value or None
        """
        try:
            value = self.client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in Redis cache.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds
        """
        try:
            serialized = json.dumps(value, cls=DateTimeEncoder)
            expire_time = ttl if ttl is not None else self.default_ttl
            self.client.setex(key, expire_time, serialized)
            logger.debug(f"Cache SET: {key} (TTL: {expire_time}s)")
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")

    def delete(self, key: str) -> bool:
        """
        Delete a key from Redis.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            result = self.client.delete(key)
            logger.debug(f"Cache DELETE: {key} (deleted: {result})")
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Key pattern (e.g., "tenant:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = self.client.keys(pattern)
            if keys:
                deleted = self.client.delete(*keys)
                logger.debug(f"Cache DELETE PATTERN: {pattern} (deleted: {deleted})")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Redis DELETE PATTERN error for {pattern}: {e}")
            return 0

    def ping(self) -> bool:
        """
        Check if Redis connection is alive.
        
        Returns:
            True if connected
        """
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis PING error: {e}")
            return False

    def close(self) -> None:
        """Close Redis connection."""
        try:
            self.client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Redis CLOSE error: {e}")