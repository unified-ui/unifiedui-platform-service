"""Redis cache implementation."""

import json
from datetime import datetime
from typing import Any

import redis

from unifiedui.core.caching.cache import BaseCache
from unifiedui.logger import get_logger

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
        password: str | None = None,
        default_ttl: int = 3600,
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
        self.client = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)
        logger.info("Redis cache initialized: %s:%s/%s", host, port, db)

    def get(self, key: str) -> Any | None:
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
                logger.debug("Cache HIT: %s", key)
                return json.loads(value)  # type: ignore[arg-type]
            logger.debug("Cache MISS: %s", key)
            return None
        except Exception as e:
            logger.error("Redis GET error for key %s: %s", key, e)
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
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
            logger.debug("Cache SET: %s (TTL: %ss)", key, expire_time)
        except Exception as e:
            logger.error("Redis SET error for key %s: %s", key, e)

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
            logger.debug("Cache DELETE: %s (deleted: %s)", key, result)
            return result > 0  # type: ignore[operator]
        except Exception as e:
            logger.error("Redis DELETE error for key %s: %s", key, e)
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
                deleted = self.client.delete(*keys)  # type: ignore[misc]
                logger.debug("Cache DELETE PATTERN: %s (deleted: %s)", pattern, deleted)
                return deleted  # type: ignore[return-value]
            return 0
        except Exception as e:
            logger.error("Redis DELETE PATTERN error for %s: %s", pattern, e)
            return 0

    def ping(self) -> bool:
        """
        Check if Redis connection is alive.

        Returns:
            True if connected
        """
        try:
            return self.client.ping()  # type: ignore[return-value]
        except Exception as e:
            logger.error("Redis PING error: %s", e)
            return False

    def close(self) -> None:
        """Close Redis connection."""
        try:
            self.client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error("Redis CLOSE error: %s", e)
