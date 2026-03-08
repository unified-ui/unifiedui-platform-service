"""Unit tests for unifiedui/identity/kerberos/provider.py - Kerberos Identity Provider."""

import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from unifiedui.identity.kerberos.provider import KerberosIdentityProvider
from unifiedui.identity.kerberos.token import KerberosIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse


def _make_ldap3_mock() -> MagicMock:
    """Create a properly configured ldap3 module mock for Kerberos SASL."""
    mock = MagicMock()
    mock.ALL = "ALL"
    mock.SUBTREE = "SUBTREE"
    mock.SASL = "SASL"
    mock.KERBEROS = "KERBEROS"
    return mock


class TestKerberosIdentityProvider:
    """Test suite for KerberosIdentityProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deserialized = {
            "sub": "krb-user-123",
            "principal": "jdoe@ACME.COM",
            "realm": "ACME.COM",
            "cn": "John Doe",
            "mail": "john@acme.com",
        }
        self.token = KerberosIdentityTokenSerializer("krb-token", self.deserialized)

    def test_initialization(self):
        """Test provider initialization."""
        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
            realm="ACME.COM",
        )

        assert provider.identity_token == self.token
        assert provider._ldap_url == "ldap://dc.acme.com"
        assert provider._ldap_base_dn == "dc=acme,dc=com"
        assert provider._realm == "ACME.COM"

    def test_get_current_user_security_groups_no_ldap_url(self):
        """Test that empty LDAP URL returns empty list."""
        provider = KerberosIdentityProvider(identity_token=self.token)
        assert provider.get_current_user_security_groups() == []

    def test_get_current_user_security_groups(self):
        """Test getting groups for current user via LDAP."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.objectGUID = "guid-1"
        mock_entry.cn = "Engineering"
        mock_entry.entry_dn = "cn=Engineering,ou=groups,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            result = provider.get_current_user_security_groups()

        assert len(result) == 1
        assert isinstance(result[0], IdentityGroupResponse)

    def test_get_security_groups(self):
        """Test listing all groups."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.objectGUID = "grp-1"
        mock_entry.cn = "Dev Team"
        mock_entry.entry_dn = "cn=Dev,ou=groups,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            groups, next_link = provider.get_security_groups()

        assert len(groups) == 1
        assert next_link is None

    def test_get_security_groups_no_ldap_url(self):
        """Test that no LDAP URL returns empty tuple."""
        provider = KerberosIdentityProvider(identity_token=self.token)
        groups, next_link = provider.get_security_groups()
        assert groups == []
        assert next_link is None

    def test_get_users(self):
        """Test listing users."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.objectGUID = "user-1"
        mock_entry.cn = "Alice Smith"
        mock_entry.sAMAccountName = "asmith"
        mock_entry.mail = "alice@acme.com"
        mock_entry.givenName = "Alice"
        mock_entry.sn = "Smith"
        mock_entry.entry_dn = "cn=Alice,ou=users,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            users, next_link = provider.get_users()

        assert len(users) == 1
        assert isinstance(users[0], IdentityUserResponse)
        assert next_link is None

    def test_get_user_by_id(self):
        """Test getting a single user."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.objectGUID = "user-abc"
        mock_entry.cn = "Bob Jones"
        mock_entry.sAMAccountName = "bjones"
        mock_entry.mail = "bob@acme.com"
        mock_entry.givenName = "Bob"
        mock_entry.sn = "Jones"
        mock_entry.entry_dn = "cn=Bob,ou=users,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            user = provider.get_user_by_id("bjones")

        assert isinstance(user, IdentityUserResponse)

    def test_get_user_by_id_not_found(self):
        """Test user not found raises exception."""
        mock_ldap3 = _make_ldap3_mock()
        mock_conn = MagicMock()
        mock_conn.entries = []
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            with pytest.raises(requests.RequestException, match="Kerberos user not found"):
                provider.get_user_by_id("nonexistent")

    def test_get_user_by_id_no_ldap_url(self):
        """Test get_user_by_id raises when no LDAP URL configured."""
        provider = KerberosIdentityProvider(identity_token=self.token)

        with pytest.raises(requests.RequestException, match="LDAP URL not configured"):
            provider.get_user_by_id("some-user")

    def test_get_group_by_id(self):
        """Test getting a single group."""
        mock_ldap3 = _make_ldap3_mock()
        mock_entry = MagicMock()
        mock_entry.objectGUID = "grp-abc"
        mock_entry.cn = "Admin"
        mock_entry.entry_dn = "cn=Admin,ou=groups,dc=acme,dc=com"

        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            group = provider.get_group_by_id("Admin")

        assert isinstance(group, IdentityGroupResponse)

    def test_get_group_by_id_not_found(self):
        """Test group not found raises exception."""
        mock_ldap3 = _make_ldap3_mock()
        mock_conn = MagicMock()
        mock_conn.entries = []
        mock_ldap3.Connection.return_value = mock_conn
        mock_ldap3.Server.return_value = MagicMock()

        provider = KerberosIdentityProvider(
            identity_token=self.token,
            ldap_url="ldap://dc.acme.com",
            ldap_base_dn="dc=acme,dc=com",
        )

        with patch.dict(sys.modules, {"ldap3": mock_ldap3}):
            with pytest.raises(requests.RequestException, match="Kerberos group not found"):
                provider.get_group_by_id("nonexistent")

    def test_get_group_by_id_no_ldap_url(self):
        """Test get_group_by_id raises when no LDAP URL configured."""
        provider = KerberosIdentityProvider(identity_token=self.token)

        with pytest.raises(requests.RequestException, match="LDAP URL not configured"):
            provider.get_group_by_id("some-group")
