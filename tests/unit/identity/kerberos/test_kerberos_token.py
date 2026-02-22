"""Unit tests for unifiedui/identity/kerberos/token.py - Kerberos Identity Token Serializer."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.kerberos.token import KerberosIdentityTokenSerializer


class TestKerberosIdentityTokenSerializer:
    """Test suite for KerberosIdentityTokenSerializer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.full_claims = {
            "sub": "krb-user-123",
            "principal": "jdoe@ACME.COM",
            "realm": "ACME.COM",
            "cn": "John Doe",
            "givenName": "John",
            "sn": "Doe",
            "mail": "john.doe@acme.com",
        }

    def test_initialization(self):
        """Test token serializer initialization."""
        token = KerberosIdentityTokenSerializer("krb-token", self.full_claims)

        assert token.token == "krb-token"
        assert token.deserialized_token == self.full_claims

    def test_is_base_identity_token(self):
        """Test that it inherits from BaseIdentityToken."""
        token = KerberosIdentityTokenSerializer("krb-token", self.full_claims)
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test get_token returns raw token string."""
        token = KerberosIdentityTokenSerializer("krb-token-xyz", self.full_claims)
        assert token.get_token() == "krb-token-xyz"

    def test_get_deserialized_token(self):
        """Test get_deserialized_token returns claims dict."""
        token = KerberosIdentityTokenSerializer("t", self.full_claims)
        assert token.get_deserialized_token() == self.full_claims

    def test_get_id_from_sub(self):
        """Test get_id returns sub claim."""
        token = KerberosIdentityTokenSerializer("t", {"sub": "sub-val", "principal": "p"})
        assert token.get_id() == "sub-val"

    def test_get_id_fallback_to_principal(self):
        """Test get_id falls back to principal when sub is missing."""
        token = KerberosIdentityTokenSerializer("t", {"principal": "jdoe@REALM"})
        assert token.get_id() == "jdoe@REALM"

    def test_get_id_default_empty(self):
        """Test get_id returns empty string when both missing."""
        token = KerberosIdentityTokenSerializer("t", {})
        assert token.get_id() == ""

    def test_get_identity_tenant_id(self):
        """Test get_identity_tenant_id returns realm."""
        token = KerberosIdentityTokenSerializer("t", {"realm": "ACME.COM"})
        assert token.get_identity_tenant_id() == "ACME.COM"

    def test_get_identity_tenant_id_default(self):
        """Test get_identity_tenant_id returns empty when no realm."""
        token = KerberosIdentityTokenSerializer("t", {})
        assert token.get_identity_tenant_id() == ""

    def test_get_display_name_from_cn(self):
        """Test get_display_name returns cn claim."""
        token = KerberosIdentityTokenSerializer("t", {"cn": "John Doe"})
        assert token.get_display_name() == "John Doe"

    def test_get_display_name_fallback_to_name(self):
        """Test get_display_name falls back to name."""
        token = KerberosIdentityTokenSerializer("t", {"name": "Jane Smith"})
        assert token.get_display_name() == "Jane Smith"

    def test_get_display_name_default(self):
        """Test get_display_name returns empty when both missing."""
        token = KerberosIdentityTokenSerializer("t", {})
        assert token.get_display_name() == ""

    def test_get_principal_name_from_principal(self):
        """Test get_principal_name returns principal claim."""
        token = KerberosIdentityTokenSerializer("t", {"principal": "jdoe@ACME.COM", "sub": "sub-1"})
        assert token.get_principal_name() == "jdoe@ACME.COM"

    def test_get_principal_name_fallback_to_sub(self):
        """Test get_principal_name falls back to sub."""
        token = KerberosIdentityTokenSerializer("t", {"sub": "sub-value"})
        assert token.get_principal_name() == "sub-value"

    def test_get_firstname_from_given_name(self):
        """Test get_firstname returns givenName."""
        token = KerberosIdentityTokenSerializer("t", {"givenName": "John"})
        assert token.get_firstname() == "John"

    def test_get_firstname_fallback_to_given_name_snake(self):
        """Test get_firstname falls back to given_name."""
        token = KerberosIdentityTokenSerializer("t", {"given_name": "Jane"})
        assert token.get_firstname() == "Jane"

    def test_get_firstname_from_cn_split(self):
        """Test get_firstname extracts from cn when no dedicated claim."""
        token = KerberosIdentityTokenSerializer("t", {"cn": "Alice Cooper"})
        assert token.get_firstname() == "Alice"

    def test_get_firstname_default(self):
        """Test get_firstname returns empty when nothing available."""
        token = KerberosIdentityTokenSerializer("t", {})
        assert token.get_firstname() == ""

    def test_get_lastname_from_sn(self):
        """Test get_lastname returns sn claim."""
        token = KerberosIdentityTokenSerializer("t", {"sn": "Doe"})
        assert token.get_lastname() == "Doe"

    def test_get_lastname_fallback_to_family_name(self):
        """Test get_lastname falls back to family_name."""
        token = KerberosIdentityTokenSerializer("t", {"family_name": "Smith"})
        assert token.get_lastname() == "Smith"

    def test_get_lastname_from_cn_split(self):
        """Test get_lastname extracts from cn when no dedicated claim."""
        token = KerberosIdentityTokenSerializer("t", {"cn": "Alice Cooper"})
        assert token.get_lastname() == "Cooper"

    def test_get_lastname_default(self):
        """Test get_lastname returns empty when nothing available."""
        token = KerberosIdentityTokenSerializer("t", {})
        assert token.get_lastname() == ""

    def test_get_mail_from_mail(self):
        """Test get_mail returns mail claim."""
        token = KerberosIdentityTokenSerializer("t", {"mail": "user@acme.com"})
        assert token.get_mail() == "user@acme.com"

    def test_get_mail_fallback_to_email(self):
        """Test get_mail falls back to email."""
        token = KerberosIdentityTokenSerializer("t", {"email": "user@example.com"})
        assert token.get_mail() == "user@example.com"

    def test_get_mail_default(self):
        """Test get_mail returns empty when both missing."""
        token = KerberosIdentityTokenSerializer("t", {})
        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test get_identity_provider returns KERBEROS enum value."""
        token = KerberosIdentityTokenSerializer("t", {})
        assert token.get_identity_provider() == IdenityProviderEnum.KERBEROS.value

    def test_full_token_scenario(self):
        """Test all getters with full claims."""
        token = KerberosIdentityTokenSerializer("full-token", self.full_claims)

        assert token.get_id() == "krb-user-123"
        assert token.get_identity_tenant_id() == "ACME.COM"
        assert token.get_display_name() == "John Doe"
        assert token.get_principal_name() == "jdoe@ACME.COM"
        assert token.get_firstname() == "John"
        assert token.get_lastname() == "Doe"
        assert token.get_mail() == "john.doe@acme.com"
        assert token.get_identity_provider() == IdenityProviderEnum.KERBEROS.value
