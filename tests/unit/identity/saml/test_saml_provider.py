"""Unit tests for unifiedui/identity/saml/provider.py - SAML Identity Provider."""

import pytest
import requests

from unifiedui.identity.saml.provider import SAMLIdentityProvider
from unifiedui.identity.saml.token import SAMLIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse


class TestSAMLIdentityProvider:
    """Test suite for SAMLIdentityProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deserialized = {
            "uid": "saml-user-1",
            "iss": "https://idp.acme.com",
            "displayName": "John Doe",
            "email": "john@acme.com",
            "firstName": "John",
            "lastName": "Doe",
            "groups": ["Engineering", "Team-Lead"],
        }
        self.token = SAMLIdentityTokenSerializer("saml-token", self.deserialized)

    def test_initialization(self):
        """Test provider initialization."""
        provider = SAMLIdentityProvider(identity_token=self.token)
        assert provider.identity_token == self.token

    def test_get_current_user_security_groups_string_list(self):
        """Test extracting groups from string list in assertion."""
        provider = SAMLIdentityProvider(identity_token=self.token)
        groups = provider.get_current_user_security_groups()

        assert len(groups) == 2
        assert isinstance(groups[0], IdentityGroupResponse)
        assert groups[0].id == "Engineering"
        assert groups[0].display_name == "Engineering"
        assert groups[1].id == "Team-Lead"

    def test_get_current_user_security_groups_dict_list(self):
        """Test extracting groups from dict list in assertion."""
        claims = {
            "uid": "u1",
            "groups": [
                {"id": "g1", "name": "Admins"},
                {"value": "g2", "display_name": "Developers"},
            ],
        }
        token = SAMLIdentityTokenSerializer("t", claims)
        provider = SAMLIdentityProvider(identity_token=token)
        groups = provider.get_current_user_security_groups()

        assert len(groups) == 2
        assert groups[0].id == "g1"
        assert groups[0].display_name == "Admins"
        assert groups[1].id == "g2"
        assert groups[1].display_name == "Developers"

    def test_get_current_user_security_groups_empty(self):
        """Test no groups returns empty list."""
        token = SAMLIdentityTokenSerializer("t", {"uid": "u1"})
        provider = SAMLIdentityProvider(identity_token=token)
        assert provider.get_current_user_security_groups() == []

    def test_get_current_user_security_groups_invalid_type(self):
        """Test non-list groups claim returns empty list."""
        token = SAMLIdentityTokenSerializer("t", {"uid": "u1", "groups": "not-a-list"})
        provider = SAMLIdentityProvider(identity_token=token)
        assert provider.get_current_user_security_groups() == []

    def test_get_security_groups(self):
        """Test get_security_groups returns same as current user groups."""
        provider = SAMLIdentityProvider(identity_token=self.token)
        groups, next_link = provider.get_security_groups()

        assert len(groups) == 2
        assert next_link is None

    def test_get_users(self):
        """Test get_users returns only the current user."""
        provider = SAMLIdentityProvider(identity_token=self.token)
        users, next_link = provider.get_users()

        assert len(users) == 1
        assert isinstance(users[0], IdentityUserResponse)
        assert users[0].id == "saml-user-1"
        assert users[0].display_name == "John Doe"
        assert next_link is None

    def test_get_user_by_id_current_user(self):
        """Test get_user_by_id returns current user when ID matches."""
        provider = SAMLIdentityProvider(identity_token=self.token)
        user = provider.get_user_by_id("saml-user-1")

        assert isinstance(user, IdentityUserResponse)
        assert user.id == "saml-user-1"
        assert user.mail == "john@acme.com"

    def test_get_user_by_id_not_found(self):
        """Test get_user_by_id raises when ID doesn't match."""
        provider = SAMLIdentityProvider(identity_token=self.token)

        with pytest.raises(requests.RequestException, match="SAML user not found"):
            provider.get_user_by_id("other-user")

    def test_get_group_by_id_found(self):
        """Test get_group_by_id returns matching group."""
        provider = SAMLIdentityProvider(identity_token=self.token)
        group = provider.get_group_by_id("Engineering")

        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "Engineering"

    def test_get_group_by_id_not_found(self):
        """Test get_group_by_id raises when group not in assertion."""
        provider = SAMLIdentityProvider(identity_token=self.token)

        with pytest.raises(requests.RequestException, match="SAML group not found"):
            provider.get_group_by_id("nonexistent-group")
