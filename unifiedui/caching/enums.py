"""Enums for cache types."""
from enum import Enum


class CacheTypeEnum(str, Enum):
    """Supported cache backend types."""
    REDIS = "REDIS"
