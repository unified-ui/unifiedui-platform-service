"""Unit tests for unifiedui/identity/oidc/provider.py - Generic OIDC Identity Provider."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from unifiedui.identity.oidc.provider import OIDCIdentityProvider
from unifiedui.identity.oidc.token import OIDCIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse


class TestOIDCIdentityProvider:
    """Test suite for OIDCIdentityProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deserialized = {
            "sub": "oidc-user-1",
            "iss": "https://auth.example.com",
            "name": "John Doe",
            "email": "john@example.com",
            "given_name": "John",
            "family_name": "Doe",
            "preferred_username": "jdoe",
            "groups": ["Engineering", "Admin"],
        }
        self.token = OIDCIdentityTokenSerializer("oidc-token", self.deserialized)

    def test_initialization(self):
        """Test provider initialization."""
        provider = OIDCIdentityProvider(
            identity_token=self.token,
            userinfo_url="https://auth.example.com/userinfo",
        )

        assert provider._userinfo_url == "https://auth.example.com/userinfo"

    def test_initialization_no_userinfo(self):
        """Test initialization without userinfo URL."""
        provider = OIDCIdentityProvider(identity_token=self.token)
        assert provider._userinfo_url is None

    def test_get_current_user_security_groups_string_list(self):
        """Test extracting groups from string list in token claims."""
        provider = OIDCIdentityProvider(identity_token=self.token)
        groups = provider.get_current_user_security_groups()

        assert len(groups) == 2
        assert groups[0].id == "Engineering"
        assert groups[0].display_name == "Engineering"

    def test_get_current_user_security_groups_from_roles(self):
        """Test extracting groups from roles claim."""
        claims = {"sub": "u1", "roles": ["admin", "user"]}
        token = OIDCIdentityTokenSerializer("t", claims)
        provider = OIDCIdentityProvider(identity_token=token)
        groups = provider.get_current_user_security_groups()

        assert len(groups) == 2
        assert groups[0].id == "admin"

    def test_get_current_user_security_groups_dict_list(self):
        """Test extracting groups from dict list in claims."""
        claims = {
            "sub": "u1",
            "groups": [
                {"id": "g1", "name": "Team A"},
                {"value": "g2", "display_name": "Team B"},
            ],
        }
        token = OIDCIdentityTokenSerializer("t", claims)
        provider = OIDCIdentityProvider(identity_token=token)
        groups = provider.get_current_user_security_groups()

        assert len(groups) == 2
        assert groups[0].id == "g1"
        assert groups[1].id == "g2"

    def test_get_current_user_security_groups_empty(self):
        """Test empty groups returns empty list."""
        token = OIDCIdentityTokenSerializer("t", {"sub": "u1"})
        provider = OIDCIdentityProvider(identity_token=token)
        assert provider.get_current_user_security_groups() == []

    def test_get_current_user_security_groups_invalid_type(self):
        """Test non-list groups returns empty list."""
        token = OIDCIdentityTokenSerializer("t", {"sub": "u1", "groups": "not-a-list"})
        provider = OIDCIdentityProvider(identity_token=token)
        assert provider.get_current_user_security_groups() == []

    def test_get_security_groups(self):
        """Test get_security_groups delegates to current user groups."""
        provider = OIDCIdentityProvider(identity_token=self.token)
        groups, next_link = provider.get_security_groups()

        assert len(groups) == 2
        assert next_link is None

    @patch("unifiedui.identity.oidc.provider.requests.get")
    def test_get_users_with_userinfo(self, mock_get):
        """Test get_users calls UserInfo endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sub": "oidc-user-1",
            "name": "John Doe",
            "email": "john@example.com",
            "preferred_username": "jdoe",
            "given_name": "John",
            "family_name": "Doe",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OIDCIdentityProvider(
            identity_token=self.token,
            userinfo_url="https://auth.example.com/userinfo",
        )
        users, next_link = provider.get_users()

        assert len(users) == 1
        assert users[0].id == "oidc-user-1"
        assert users[0].display_name == "John Doe"
        assert next_link is None

    def test_get_users_without_userinfo(self):
        """Test get_users falls back to token claims."""
        provider = OIDCIdentityProvider(identity_token=self.token)
        users, next_link = provider.get_users()

        assert len(users) == 1
        assert users[0].id == "oidc-user-1"
        assert users[0].display_name == "John Doe"
        assert next_link is None

    @patch("unifiedui.identity.oidc.provider.requests.get")
    def test_get_users_userinfo_error_fallback(self, mock_get):
        """Test get_users falls back to token when userinfo fails."""
        mock_get.side_effect = requests.RequestException("Connection error")

        provider = OIDCIdentityProvider(
            identity_token=self.token,
            userinfo_url="https://auth.example.com/userinfo",
        )
        users, _next_link = provider.get_users()

        assert len(users) == 1
        assert users[0].id == "oidc-user-1"

    def test_get_user_by_id_current_user(self):
        """Test get_user_by_id returns current user when ID matches."""
        provider = OIDCIdentityProvider(identity_token=self.token)
        user = provider.get_user_by_id("oidc-user-1")

        assert isinstance(user, IdentityUserResponse)
        assert user.id == "oidc-user-1"

    def test_get_user_by_id_not_found(self):
        """Test get_user_by_id raises when ID doesn't match."""
        provider = OIDCIdentityProvider(identity_token=self.token)

        with pytest.raises(requests.RequestException, match="OIDC user not found"):
            provider.get_user_by_id("other-user")

    def test_get_group_by_id_found(self):
        """Test get_group_by_id returns matching group."""
        provider = OIDCIdentityProvider(identity_token=self.token)
        group = provider.get_group_by_id("Engineering")

        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "Engineering"

    def test_get_group_by_id_not_found(self):
        """Test get_group_by_id raises when group not in claims."""
        provider = OIDCIdentityProvider(identity_token=self.token)

        with pytest.raises(requests.RequestException, match="OIDC group not found"):
            provider.get_group_by_id("nonexistent")
