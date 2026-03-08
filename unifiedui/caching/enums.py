"""Enums for cache types."""

from enum import StrEnum


class CacheTypeEnum(StrEnum):
    """Supported cache backend types."""

    REDIS = "REDIS"
