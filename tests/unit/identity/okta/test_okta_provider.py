"""Unit tests for unifiedui/identity/okta/provider.py - Okta Identity Provider."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from unifiedui.identity.okta.provider import OktaIdentityProvider
from unifiedui.identity.okta.token import OktaIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse


class TestOktaIdentityProvider:
    """Test suite for OktaIdentityProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deserialized = {
            "uid": "okta-user-1",
            "sub": "okta-sub-1",
            "iss": "https://dev-12345.okta.com/oauth2/default",
            "name": "John Doe",
            "email": "john@acme.com",
        }
        self.token = OktaIdentityTokenSerializer("okta-token", self.deserialized)

    def test_initialization(self):
        """Test provider initialization."""
        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="ssws-token-123",
        )

        assert provider._base_url == "https://dev-12345.okta.com/api/v1"
        assert provider._api_token == "ssws-token-123"

    def test_get_headers_with_token(self):
        """Test authorization headers with API token."""
        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="my-token",
        )
        headers = provider._get_headers()

        assert headers["Authorization"] == "SSWS my-token"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_without_token(self):
        """Test headers without API token."""
        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
        )
        headers = provider._get_headers()

        assert "Authorization" not in headers

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_current_user_security_groups(self, mock_get):
        """Test getting current user's groups."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "grp-1", "profile": {"name": "Engineering"}},
            {"id": "grp-2", "profile": {"name": "Everyone"}},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )
        groups = provider.get_current_user_security_groups()

        assert len(groups) == 2
        assert groups[0].id == "grp-1"
        assert groups[0].display_name == "Engineering"

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_current_user_security_groups_error(self, mock_get):
        """Test graceful handling when API call fails."""
        mock_get.side_effect = requests.RequestException("Network error")

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )
        groups = provider.get_current_user_security_groups()

        assert groups == []

    def test_get_current_user_security_groups_no_user_id(self):
        """Test returns empty when user has no ID."""
        token = OktaIdentityTokenSerializer("t", {})
        provider = OktaIdentityProvider(
            identity_token=token,
            okta_domain="dev-12345.okta.com",
        )
        assert provider.get_current_user_security_groups() == []

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_security_groups(self, mock_get):
        """Test listing all groups."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "g1", "profile": {"name": "Admin"}},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}
        mock_get.return_value = mock_response

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )
        groups, next_link = provider.get_security_groups()

        assert len(groups) == 1
        assert groups[0].display_name == "Admin"
        assert next_link is None

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_security_groups_with_pagination(self, mock_get):
        """Test pagination via Link header."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "g1", "profile": {"name": "Team"}}]
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"Link": '<https://dev-12345.okta.com/api/v1/groups?after=abc>; rel="next"'}
        mock_get.return_value = mock_response

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )
        _groups, next_link = provider.get_security_groups()

        assert next_link == "https://dev-12345.okta.com/api/v1/groups?after=abc"

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_users(self, mock_get):
        """Test listing users."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "u1",
                "profile": {
                    "firstName": "Alice",
                    "lastName": "Smith",
                    "login": "alice@acme.com",
                    "email": "alice@acme.com",
                },
            },
        ]
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}
        mock_get.return_value = mock_response

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )
        users, next_link = provider.get_users()

        assert len(users) == 1
        assert isinstance(users[0], IdentityUserResponse)
        assert next_link is None

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_user_by_id(self, mock_get):
        """Test getting a single user."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "u1",
            "profile": {
                "firstName": "Bob",
                "lastName": "Jones",
                "login": "bob@acme.com",
                "email": "bob@acme.com",
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )
        user = provider.get_user_by_id("u1")

        assert isinstance(user, IdentityUserResponse)
        assert user.id == "u1"
        assert user.display_name == "Bob Jones"

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_user_by_id_not_found(self, mock_get):
        """Test get_user_by_id raises on HTTP error."""
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("404")

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )

        with pytest.raises(requests.HTTPError):
            provider.get_user_by_id("nonexistent")

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_group_by_id(self, mock_get):
        """Test getting a single group."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "g-abc",
            "profile": {"name": "Engineering"},
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )
        group = provider.get_group_by_id("g-abc")

        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "g-abc"
        assert group.display_name == "Engineering"

    @patch("unifiedui.identity.okta.provider.requests.get")
    def test_get_group_by_id_not_found(self, mock_get):
        """Test get_group_by_id raises on HTTP error."""
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("404")

        provider = OktaIdentityProvider(
            identity_token=self.token,
            okta_domain="dev-12345.okta.com",
            api_token="token",
        )

        with pytest.raises(requests.HTTPError):
            provider.get_group_by_id("nonexistent")

    def test_extract_next_link_present(self):
        """Test extracting next link from Link header."""
        mock_response = MagicMock()
        mock_response.headers = {"Link": '<https://example.com/next>; rel="next"'}

        result = OktaIdentityProvider._extract_next_link(mock_response)
        assert result == "https://example.com/next"

    def test_extract_next_link_absent(self):
        """Test returns None when no next link."""
        mock_response = MagicMock()
        mock_response.headers = {}

        result = OktaIdentityProvider._extract_next_link(mock_response)
        assert result is None

    def test_extract_next_link_no_next_rel(self):
        """Test returns None when Link header has no rel=next."""
        mock_response = MagicMock()
        mock_response.headers = {"Link": '<https://example.com/prev>; rel="prev"'}

        result = OktaIdentityProvider._extract_next_link(mock_response)
        assert result is None
