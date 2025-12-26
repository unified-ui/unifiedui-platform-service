"""Unit tests for unifiedui/identity/extra_id/provider.py - ExtraID Identity Provider."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from unifiedui.identity.extra_id.provider import ExtraIDIdentityProvider
from unifiedui.identity.extra_id.token import ExtraIDIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery
from unifiedui.core.identity.providers import BaseIdentityProvider


class TestExtraIDIdentityProvider:
    """Test suite for ExtraIDIdentityProvider."""

    def setup_method(self):
        """Setup test fixtures."""
        self.token_data = {
            "oid": "user-123",
            "tid": "tenant-456",
            "name": "Test User"
        }
        self.token = ExtraIDIdentityTokenSerializer("test-token", self.token_data)
        self.provider = ExtraIDIdentityProvider(self.token)

    def test_initialization(self):
        """Test provider initialization."""
        assert isinstance(self.provider, BaseIdentityProvider)
        assert self.provider.identity_token == self.token

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_current_user_security_groups(self, mock_get):
        """Test getting current user's security groups."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "value": [
                {"id": "group-1", "displayName": "Group 1"},
                {"id": "group-2", "displayName": "Group 2"}
            ]
        }
        mock_get.return_value = mock_response
        
        groups = self.provider.get_current_user_security_groups()
        
        assert len(groups) == 2
        assert groups[0].id == "group-1"
        assert groups[0].display_name == "Group 1"
        mock_get.assert_called_once()

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_current_user_security_groups_with_next_link(self, mock_get):
        """Test getting groups with next_link."""
        mock_response = Mock()
        mock_response.json.return_value = {"value": [{"id": "g1", "displayName": "Group"}]}
        mock_get.return_value = mock_response
        
        query = APIFilterQuery(next_link="https://graph.microsoft.com/v1.0/me/memberOf?$skiptoken=abc")
        groups = self.provider.get_current_user_security_groups(query)
        
        # Verify next_link was used directly and params are empty
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://graph.microsoft.com/v1.0/me/memberOf?$skiptoken=abc"
        assert call_args[1]["params"] == {}
        assert len(groups) == 1

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_security_groups(self, mock_get):
        """Test getting all security groups."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "value": [{"id": "g1", "displayName": "Sec Group"}],
            "@odata.nextLink": "https://next-link"
        }
        mock_get.return_value = mock_response
        
        groups, next_link = self.provider.get_security_groups()
        
        assert len(groups) == 1
        assert next_link == "https://next-link"

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_security_groups_with_search(self, mock_get):
        """Test getting groups with search query."""
        mock_response = Mock()
        mock_response.json.return_value = {"value": []}
        mock_get.return_value = mock_response
        
        query = APIFilterQuery(search="admin")
        self.provider.get_security_groups(query)
        
        # Verify ConsistencyLevel header and search param
        call_args = mock_get.call_args
        assert call_args[1]["headers"]["ConsistencyLevel"] == "eventual"
        assert "$search" in call_args[1]["params"]

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_security_groups_with_next_link(self, mock_get):
        """Test getting groups with next_link parameter."""
        mock_response = Mock()
        mock_response.json.return_value = {"value": [{"id": "g2", "displayName": "Group 2"}]}
        mock_get.return_value = mock_response
        
        query = APIFilterQuery(next_link="https://graph.microsoft.com/v1.0/groups?$skiptoken=xyz")
        groups, _ = self.provider.get_security_groups(query)
        
        # Verify next_link was used and params are empty
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://graph.microsoft.com/v1.0/groups?$skiptoken=xyz"
        assert call_args[1]["params"] == {}
        assert len(groups) == 1

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_users(self, mock_get):
        """Test getting users from directory."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "value": [
                {"id": "u1", "displayName": "User 1", "userPrincipalName": "user1@test.com"}
            ],
            "@odata.nextLink": "next-page"
        }
        mock_get.return_value = mock_response
        
        users, next_link = self.provider.get_users()
        
        assert len(users) == 1
        assert users[0].id == "u1"
        assert next_link == "next-page"

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_users_with_search(self, mock_get):
        """Test getting users with search query."""
        mock_response = Mock()
        mock_response.json.return_value = {"value": [{"id": "u1", "displayName": "John", "userPrincipalName": "john@test.com"}]}
        mock_get.return_value = mock_response
        
        query = APIFilterQuery(search="john")
        users, _ = self.provider.get_users(query)
        
        call_args = mock_get.call_args
        assert "ConsistencyLevel" in call_args[1]["headers"]
        assert "$search" in call_args[1]["params"]
        assert len(users) == 1
    
    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_users_with_next_link(self, mock_get):
        """Test getting users with next_link."""
        mock_response = Mock()
        mock_response.json.return_value = {"value": [{"id": "u1", "displayName": "User", "userPrincipalName": "user@test.com"}]}
        mock_get.return_value = mock_response
        
        query = APIFilterQuery(next_link="https://graph.microsoft.com/v1.0/users?$skiptoken=xyz")
        users, _ = self.provider.get_users(query)
        
        # Verify next_link was used directly and params are empty
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://graph.microsoft.com/v1.0/users?$skiptoken=xyz"
        assert call_args[1]["params"] == {}
        assert len(users) == 1

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_user_by_id(self, mock_get):
        """Test getting a specific user by ID."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "user-abc",
            "displayName": "John Doe",
            "userPrincipalName": "john@test.com",
            "givenName": "John",
            "surname": "Doe",
            "mail": "john.doe@test.com"
        }
        mock_get.return_value = mock_response
        
        user = self.provider.get_user_by_id("user-abc")
        
        assert isinstance(user, IdentityUserResponse)
        assert user.id == "user-abc"
        assert user.display_name == "John Doe"
        assert user.firstname == "John"
        assert user.lastname == "Doe"
        assert user.mail == "john.doe@test.com"

    @patch('unifiedui.identity.extra_id.provider.requests.get')
    def test_get_group_by_id(self, mock_get):
        """Test getting a specific group by ID."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "group-xyz",
            "displayName": "Admin Group"
        }
        mock_get.return_value = mock_response
        
        group = self.provider.get_group_by_id("group-xyz")
        
        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "group-xyz"
        assert group.display_name == "Admin Group"

    def test_parse_groups_response(self):
        """Test parsing groups response."""
        data = {
            "value": [
                {"id": "g1", "displayName": "Group 1"},
                {"id": "g2", "displayName": "Group 2"}
            ]
        }
        
        groups = self.provider._parse_groups_response(data)
        
        assert len(groups) == 2
        assert all(isinstance(g, IdentityGroupResponse) for g in groups)

    def test_parse_users_response(self):
        """Test parsing users response."""
        data = {
            "value": [
                {"id": "u1", "displayName": "User 1", "userPrincipalName": "u1@test.com"}
            ]
        }
        
        users = self.provider._parse_users_response(data)
        
        assert len(users) == 1
        assert isinstance(users[0], IdentityUserResponse)
        assert users[0].identity_provider == "EXTRA_ID"
