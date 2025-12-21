"""Unit tests for aihub/identity/mock/provider.py - Mock Identity Provider."""
import pytest
from unittest.mock import Mock

from aihub.identity.mock.provider import MockIdentityProvider
from aihub.identity.mock.token import MockIdentityToken
from aihub.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from aihub.utils.api_query import APIFilterQuery


class TestMockIdentityProvider:
    """Test suite for MockIdentityProvider."""

    def test_initialization(self):
        """Test provider initialization."""
        token = MockIdentityToken(user_id="user-123", idp_groups=["group-1"])
        provider = MockIdentityProvider(token)
        
        assert provider.identity_token is token
        assert provider._users == {}
        assert provider._groups == {}

    def test_get_current_user_security_groups_with_groups(self):
        """Test getting current user's security groups when groups exist."""
        token = MockIdentityToken(user_id="user-123", idp_groups=["group-1", "group-2"])
        provider = MockIdentityProvider(token)
        
        # Add mock groups
        provider.add_group("group-1", "Test Group 1")
        provider.add_group("group-2", "Test Group 2")
        
        result = provider.get_current_user_security_groups()
        
        assert len(result) == 2
        assert isinstance(result[0], IdentityGroupResponse)
        assert result[0].id == "group-1"
        assert result[0].display_name == "Test Group 1"
        assert result[1].id == "group-2"
        assert result[1].display_name == "Test Group 2"

    def test_get_current_user_security_groups_without_add_group(self):
        """Test getting current user's security groups using default names."""
        token = MockIdentityToken(user_id="user-123", idp_groups=["group-1"])
        provider = MockIdentityProvider(token)
        
        result = provider.get_current_user_security_groups()
        
        assert len(result) == 1
        assert result[0].id == "group-1"
        assert result[0].display_name == "Mock Group group-1"

    def test_get_current_user_security_groups_with_query(self):
        """Test getting current user's security groups with query parameter."""
        token = MockIdentityToken(user_id="user-123", idp_groups=["group-1"])
        provider = MockIdentityProvider(token)
        query = APIFilterQuery(top=10)
        
        result = provider.get_current_user_security_groups(query=query)
        
        assert len(result) == 1

    def test_get_current_user_security_groups_token_without_get_groups(self):
        """Test with a token that doesn't have get_groups method."""
        # Create a mock token without get_groups method
        token = Mock()
        token.get_identity_provider.return_value = "mock"
        token.get_identity_tenant_id.return_value = "tenant-1"
        # Explicitly make sure get_groups doesn't exist
        del token.get_groups
        
        provider = MockIdentityProvider(token)
        result = provider.get_current_user_security_groups()
        
        assert result == []

    def test_get_security_groups(self):
        """Test getting all security groups returns empty list."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        
        groups, next_link = provider.get_security_groups()
        
        assert groups == []
        assert next_link is None

    def test_get_security_groups_with_query(self):
        """Test getting security groups with query parameter."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        query = APIFilterQuery(search="test", top=10)
        
        groups, next_link = provider.get_security_groups(query=query)
        
        assert groups == []
        assert next_link is None

    def test_get_users(self):
        """Test getting users returns empty list."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        
        users, next_link = provider.get_users()
        
        assert users == []
        assert next_link is None

    def test_get_users_with_query(self):
        """Test getting users with query parameter."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        query = APIFilterQuery(search="john", top=20)
        
        users, next_link = provider.get_users(query=query)
        
        assert users == []
        assert next_link is None

    def test_get_user_by_id(self):
        """Test getting a user by ID."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        
        user = provider.get_user_by_id("test-user-456")
        
        assert isinstance(user, IdentityUserResponse)
        assert user.id == "test-user-456"
        assert user.identity_provider == "MOCK"
        assert user.identity_tenant_id == "test-tenant-123"
        assert user.display_name == "Mock User"
        assert user.firstname == "Mock"
        assert user.lastname == "User"
        assert user.mail == "test-user-456@test.com"

    def test_get_group_by_id_with_add_group(self):
        """Test getting a group by ID after adding it."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        
        provider.add_group("group-abc", "Custom Group Name")
        group = provider.get_group_by_id("group-abc")
        
        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "group-abc"
        assert group.display_name == "Custom Group Name"

    def test_get_group_by_id_without_add_group(self):
        """Test getting a group by ID without adding it first (uses default name)."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        
        group = provider.get_group_by_id("group-xyz")
        
        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "group-xyz"
        assert group.display_name == "Mock Group group-xyz"

    def test_add_group(self):
        """Test adding a mock group."""
        token = MockIdentityToken(user_id="user-123")
        provider = MockIdentityProvider(token)
        
        provider.add_group("group-1", "Test Group")
        
        assert "group-1" in provider._groups
        assert provider._groups["group-1"]["display_name"] == "Test Group"
