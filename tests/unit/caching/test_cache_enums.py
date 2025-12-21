"""Unit tests for aihub/caching/enums.py - CacheTypeEnum."""
import pytest
from enum import Enum

from aihub.caching.enums import CacheTypeEnum


class TestCacheTypeEnum:
    """Test suite for CacheTypeEnum."""
    
    def test_is_enum(self):
        """Test that CacheTypeEnum is an Enum."""
        assert issubclass(CacheTypeEnum, Enum)
    
    def test_is_string_enum(self):
        """Test that CacheTypeEnum inherits from str."""
        assert issubclass(CacheTypeEnum, str)
    
    def test_has_redis_value(self):
        """Test that REDIS value exists."""
        assert hasattr(CacheTypeEnum, 'REDIS')
        assert CacheTypeEnum.REDIS == "REDIS"
    
    def test_redis_value_is_string(self):
        """Test that REDIS value is a string."""
        assert isinstance(CacheTypeEnum.REDIS.value, str)
    
    def test_can_compare_with_string(self):
        """Test that enum can be compared with string."""
        assert CacheTypeEnum.REDIS == "REDIS"
    
    def test_can_create_from_string(self):
        """Test that enum can be created from string."""
        cache_type = CacheTypeEnum("REDIS")
        assert cache_type == CacheTypeEnum.REDIS
    
    def test_invalid_value_raises_error(self):
        """Test that invalid value raises ValueError."""
        with pytest.raises(ValueError):
            CacheTypeEnum("INVALID")
    
    def test_enum_members_count(self):
        """Test the number of enum members."""
        # Currently only REDIS is defined
        assert len(CacheTypeEnum) == 1
    
    def test_enum_member_name(self):
        """Test enum member name property."""
        assert CacheTypeEnum.REDIS.name == "REDIS"
    
    def test_enum_iteration(self):
        """Test iterating over enum members."""
        members = list(CacheTypeEnum)
        assert CacheTypeEnum.REDIS in members
    
    def test_enum_membership(self):
        """Test membership testing."""
        assert "REDIS" in [e.value for e in CacheTypeEnum]
    
    def test_string_representation(self):
        """Test string representation of enum."""
        # Enums that inherit from str will have full qualified name in str()
        # But the value itself is the string
        assert str(CacheTypeEnum.REDIS) in ["REDIS", "CacheTypeEnum.REDIS"]
        assert CacheTypeEnum.REDIS.value == "REDIS"
