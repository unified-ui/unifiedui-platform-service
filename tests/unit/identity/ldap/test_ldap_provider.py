"""Unit tests for unifiedui/identity/ldap/provider.py - LDAP Identity Provider."""

import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from unifiedui.identity.ldap.provider import LDAPIdentityProvider
from unifiedui.identity.ldap.token import LDAPIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


def _make_ldap3_mock() -> MagicMock:
    """Create a properly configured ldap3 module mock."""
    mock = MagicMock()
    mock.ALL = "ALL"
    mock.SUBTREE = "SUBTREE"
    return mock


class TestLDAPIdentityProvider:
    """Test suite for LDAPIdentityProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deserialized = {
            "sub": "ldap-user-123",
            "uid": "jdoe",
            "cn": "John Doe",
            "mail": "john@acme.com",
            "o": "acme.com",
            "dn": "cn=jdoe,ou=users,dc=acme,dc=com",
        }
        self.token = LDAPIdentityTokenSerializer("ldap-token", self.deserialized)

    def test_initialization(self):
        """Test provider initialization."""
        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com:389",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        assert provider.identity_token == self.token
        assert provider._server_url == "ldap://ldap.acme.com:389"
        assert provider._bind_dn == "cn=admin,dc=acme,dc=com"
        assert provider._base_dn == "dc=acme,dc=com"

    def test_get_current_user_security_groups(self):
        """Test getting groups for the current user via LDAP."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.entryUUID = "group-uuid-1"
        mock_entry.cn = "Engineering"
        mock_entry.entry_dn = "cn=Engineering,ou=groups,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            result = provider.get_current_user_security_groups()

        assert len(result) == 1
        assert isinstance(result[0], IdentityGroupResponse)

    def test_get_current_user_security_groups_no_ldap3(self):
        """Test graceful handling when ldap3 is not installed."""
        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": None}):
            result = provider.get_current_user_security_groups()

        assert result == []

    def test_get_security_groups(self):
        """Test listing all groups in the directory."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.entryUUID = "grp-1"
        mock_entry.cn = "Dev Team"
        mock_entry.entry_dn = "cn=Dev Team,ou=groups,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            groups, next_link = provider.get_security_groups()

        assert len(groups) == 1
        assert next_link is None

    def test_get_users(self):
        """Test listing users in the directory."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.entryUUID = "user-1"
        mock_entry.cn = "Alice Smith"
        mock_entry.uid = "asmith"
        mock_entry.mail = "alice@acme.com"
        mock_entry.givenName = "Alice"
        mock_entry.sn = "Smith"
        mock_entry.entry_dn = "cn=Alice Smith,ou=users,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            users, next_link = provider.get_users()

        assert len(users) == 1
        assert isinstance(users[0], IdentityUserResponse)
        assert next_link is None

    def test_get_user_by_id(self):
        """Test getting a single user by UID."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.entryUUID = "user-abc"
        mock_entry.cn = "Bob Jones"
        mock_entry.uid = "bjones"
        mock_entry.mail = "bob@acme.com"
        mock_entry.givenName = "Bob"
        mock_entry.sn = "Jones"
        mock_entry.entry_dn = "cn=Bob Jones,ou=users,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            user = provider.get_user_by_id("bjones")

        assert isinstance(user, IdentityUserResponse)

    def test_get_user_by_id_not_found(self):
        """Test getting a user that doesn't exist."""
        mock_ldap3 = _make_ldap3_mock()
        mock_conn = MagicMock()
        mock_conn.entries = []
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            with pytest.raises(requests.RequestException, match="LDAP user not found"):
                provider.get_user_by_id("nonexistent")

    def test_get_group_by_id(self):
        """Test getting a single group by CN."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.entryUUID = "grp-abc"
        mock_entry.cn = "Engineering"
        mock_entry.entry_dn = "cn=Engineering,ou=groups,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            group = provider.get_group_by_id("Engineering")

        assert isinstance(group, IdentityGroupResponse)

    def test_get_group_by_id_not_found(self):
        """Test getting a group that doesn't exist."""
        mock_ldap3 = _make_ldap3_mock()
        mock_conn = MagicMock()
        mock_conn.entries = []
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            with pytest.raises(requests.RequestException, match="LDAP group not found"):
                provider.get_group_by_id("nonexistent")

    def test_get_users_with_search(self):
        """Test listing users with a search filter."""
        mock_ldap3 = _make_ldap3_mock()
        mock_conn = MagicMock()
        mock_conn.entries = []
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = LDAPIdentityProvider(
            identity_token=self.token,
            server_url="ldap://ldap.acme.com",
            bind_dn="cn=admin,dc=acme,dc=com",
            bind_password="secret",
            base_dn="dc=acme,dc=com",
        )
        query = APIFilterQuery(search="Alice", top=10)

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            users, _ = provider.get_users(query=query)

        assert users == []
