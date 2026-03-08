"""Unit tests for unifiedui/identity/google/provider.py - Google Identity Provider."""

from unittest.mock import MagicMock, patch

import requests

from unifiedui.identity.google.provider import GoogleIdentityProvider
from unifiedui.identity.google.token import GoogleIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class TestGoogleIdentityProvider:
    """Test suite for GoogleIdentityProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deserialized = {
            "sub": "google-user-123",
            "hd": "acme.com",
            "email": "user@acme.com",
            "name": "Test User",
        }
        self.token = GoogleIdentityTokenSerializer("google-token", self.deserialized)

    def test_initialization_with_service_account(self):
        """Test provider initialization with a service account token."""
        provider = GoogleIdentityProvider(
            identity_token=self.token,
            service_account_token="sa-token-123",
        )

        assert provider.identity_token == self.token
        assert provider._api_token == "sa-token-123"

    def test_initialization_without_service_account(self):
        """Test provider initialization falls back to identity token."""
        provider = GoogleIdentityProvider(identity_token=self.token)

        assert provider._api_token == "google-token"

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_current_user_security_groups(self, mock_get):
        """Test getting groups for the current user."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "groups": [
                {"id": "group-1", "name": "Engineering", "email": "eng@acme.com"},
                {"id": "group-2", "name": "All Staff", "email": "all@acme.com"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa-token")
        result = provider.get_current_user_security_groups()

        assert len(result) == 2
        assert isinstance(result[0], IdentityGroupResponse)
        assert result[0].id == "group-1"
        assert result[0].display_name == "Engineering"
        assert result[1].id == "group-2"

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert "userKey" in call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_current_user_security_groups_empty_email(self, mock_get):
        """Test getting groups returns empty list when no email."""
        empty_token = GoogleIdentityTokenSerializer("token", {"sub": "user-123"})
        provider = GoogleIdentityProvider(identity_token=empty_token)

        result = provider.get_current_user_security_groups()

        assert result == []
        mock_get.assert_not_called()

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_current_user_security_groups_api_error(self, mock_get):
        """Test getting groups returns empty on API error."""
        mock_get.side_effect = requests.RequestException("Connection error")

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa-token")
        result = provider.get_current_user_security_groups()

        assert result == []

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_security_groups(self, mock_get):
        """Test listing all groups in the domain."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "groups": [
                {"id": "grp-1", "name": "Dev Team"},
                {"id": "grp-2", "name": "QA Team"},
            ],
            "nextPageToken": "token-page-2",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        groups, next_token = provider.get_security_groups()

        assert len(groups) == 2
        assert next_token == "token-page-2"
        assert groups[0].display_name == "Dev Team"

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_security_groups_with_search(self, mock_get):
        """Test listing groups with a search filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"groups": [{"id": "grp-1", "name": "Engineering"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        query = APIFilterQuery(search="Eng", top=10)
        groups, _ = provider.get_security_groups(query=query)

        assert len(groups) == 1
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert "query" in params

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_security_groups_api_error(self, mock_get):
        """Test listing groups returns empty on API error."""
        mock_get.side_effect = requests.RequestException("API error")

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        groups, next_token = provider.get_security_groups()

        assert groups == []
        assert next_token is None

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_users(self, mock_get):
        """Test listing users in the domain."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "users": [
                {
                    "id": "user-1",
                    "name": {"fullName": "Alice Smith"},
                    "primaryEmail": "alice@acme.com",
                },
                {
                    "id": "user-2",
                    "name": {"fullName": "Bob Jones"},
                    "primaryEmail": "bob@acme.com",
                },
            ],
            "nextPageToken": "users-page-2",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        users, next_token = provider.get_users()

        assert len(users) == 2
        assert isinstance(users[0], IdentityUserResponse)
        assert users[0].display_name == "Alice Smith"
        assert next_token == "users-page-2"

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_users_api_error(self, mock_get):
        """Test listing users returns empty on API error."""
        mock_get.side_effect = requests.RequestException("API error")

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        users, next_token = provider.get_users()

        assert users == []
        assert next_token is None

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_user_by_id(self, mock_get):
        """Test getting a single user by ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "user-abc",
            "name": {"fullName": "Alice Smith", "givenName": "Alice", "familyName": "Smith"},
            "primaryEmail": "alice@acme.com",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        user = provider.get_user_by_id("user-abc")

        assert isinstance(user, IdentityUserResponse)
        assert user.id == "user-abc"
        assert user.display_name == "Alice Smith"
        assert user.mail == "alice@acme.com"
        assert user.firstname == "Alice"
        assert user.lastname == "Smith"

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_group_by_id(self, mock_get):
        """Test getting a single group by ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "grp-abc",
            "name": "Engineering Team",
            "email": "eng@acme.com",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        group = provider.get_group_by_id("grp-abc")

        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "grp-abc"
        assert group.display_name == "Engineering Team"

    @patch("unifiedui.identity.google.provider.requests.get")
    def test_get_current_user_security_groups_with_pagination(self, mock_get):
        """Test groups with pagination query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"groups": [{"id": "grp-1", "name": "Team A"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = GoogleIdentityProvider(identity_token=self.token, service_account_token="sa")
        query = APIFilterQuery(top=5)
        result = provider.get_current_user_security_groups(query=query)

        assert len(result) == 1
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params.get("maxResults") == 5
