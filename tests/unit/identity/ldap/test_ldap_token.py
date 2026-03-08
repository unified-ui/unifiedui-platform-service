"""Unit tests for unifiedui/identity/ldap/token.py - LDAP Identity Token."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.ldap.token import LDAPIdentityTokenSerializer


class TestLDAPIdentityTokenSerializer:
    """Test suite for LDAPIdentityTokenSerializer."""

    def test_initialization(self):
        """Test token initialization."""
        token_str = "ldap-jwt-token-string"
        deserialized = {"sub": "ldap-user-123", "o": "acme.com"}

        token = LDAPIdentityTokenSerializer(token_str, deserialized)

        assert token.token == token_str
        assert token.deserialized_token == deserialized
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test getting the raw token string."""
        token_str = "test-ldap-token"
        token = LDAPIdentityTokenSerializer(token_str, {})

        assert token.get_token() == token_str

    def test_get_deserialized_token(self):
        """Test getting deserialized token dict."""
        deserialized = {"sub": "user-123", "cn": "Test User"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_deserialized_token() == deserialized

    def test_get_id_from_sub(self):
        """Test getting user ID from sub claim."""
        deserialized = {"sub": "ldap-user-abc-123"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_id() == "ldap-user-abc-123"

    def test_get_id_from_uid_fallback(self):
        """Test getting user ID from uid claim when sub is missing."""
        deserialized = {"uid": "jdoe"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_id() == "jdoe"

    def test_get_id_default(self):
        """Test getting user ID returns empty string when missing."""
        token = LDAPIdentityTokenSerializer("token", {})

        assert token.get_id() == ""

    def test_get_identity_tenant_id_from_org(self):
        """Test getting tenant ID from o (organization) claim."""
        deserialized = {"o": "acme.com"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_identity_tenant_id() == "acme.com"

    def test_get_identity_tenant_id_from_dn_fallback(self):
        """Test getting tenant ID from dn claim when o is missing."""
        deserialized = {"dn": "cn=jdoe,dc=example,dc=com"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_identity_tenant_id() == "cn=jdoe,dc=example,dc=com"

    def test_get_identity_tenant_id_default(self):
        """Test getting tenant ID returns empty string when missing."""
        token = LDAPIdentityTokenSerializer("token", {})

        assert token.get_identity_tenant_id() == ""

    def test_get_display_name_from_cn(self):
        """Test getting display name from cn claim."""
        deserialized = {"cn": "John Doe"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_display_name() == "John Doe"

    def test_get_display_name_default(self):
        """Test getting display name returns empty string when missing."""
        token = LDAPIdentityTokenSerializer("token", {})

        assert token.get_display_name() == ""

    def test_get_principal_name_from_uid(self):
        """Test getting principal name from uid claim."""
        deserialized = {"uid": "jdoe", "mail": "john@acme.com"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_principal_name() == "jdoe"

    def test_get_principal_name_from_mail_fallback(self):
        """Test getting principal name from mail when uid missing."""
        deserialized = {"mail": "john@acme.com"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_principal_name() == "john@acme.com"

    def test_get_firstname_from_given_name(self):
        """Test getting firstname from givenName claim."""
        deserialized = {"givenName": "John"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_firstname() == "John"

    def test_get_firstname_from_cn_split(self):
        """Test getting firstname by splitting cn when givenName missing."""
        deserialized = {"cn": "Jane Smith"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_firstname() == "Jane"

    def test_get_firstname_default(self):
        """Test firstname returns empty string when all fields missing."""
        token = LDAPIdentityTokenSerializer("token", {})

        assert token.get_firstname() == ""

    def test_get_lastname_from_sn(self):
        """Test getting lastname from sn claim."""
        deserialized = {"sn": "Doe"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_lastname() == "Doe"

    def test_get_lastname_from_cn_split(self):
        """Test getting lastname by splitting cn when sn missing."""
        deserialized = {"cn": "Jane Smith"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_lastname() == "Smith"

    def test_get_lastname_default(self):
        """Test lastname returns empty string when all fields missing."""
        token = LDAPIdentityTokenSerializer("token", {})

        assert token.get_lastname() == ""

    def test_get_mail(self):
        """Test getting email address from mail claim."""
        deserialized = {"mail": "john@acme.com"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_mail() == "john@acme.com"

    def test_get_mail_from_email_fallback(self):
        """Test getting email from email claim when mail missing."""
        deserialized = {"email": "john@acme.com"}
        token = LDAPIdentityTokenSerializer("token", deserialized)

        assert token.get_mail() == "john@acme.com"

    def test_get_mail_default(self):
        """Test getting email returns empty string when missing."""
        token = LDAPIdentityTokenSerializer("token", {})

        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test that identity provider is LDAP."""
        token = LDAPIdentityTokenSerializer("token", {})

        assert token.get_identity_provider() == IdenityProviderEnum.LDAP.value

    def test_full_ldap_token(self):
        """Test a complete LDAP token with all claims."""
        deserialized = {
            "sub": "ldap-user-001",
            "uid": "jdoe",
            "cn": "John Doe",
            "sn": "Doe",
            "givenName": "John",
            "mail": "john.doe@acme.com",
            "o": "acme.com",
            "dn": "cn=jdoe,ou=users,dc=acme,dc=com",
        }
        token = LDAPIdentityTokenSerializer("full-ldap-token", deserialized)

        assert token.get_id() == "ldap-user-001"
        assert token.get_identity_tenant_id() == "acme.com"
        assert token.get_display_name() == "John Doe"
        assert token.get_principal_name() == "jdoe"
        assert token.get_firstname() == "John"
        assert token.get_lastname() == "Doe"
        assert token.get_mail() == "john.doe@acme.com"
        assert token.get_identity_provider() == IdenityProviderEnum.LDAP.value
