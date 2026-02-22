"""Unit tests for unifiedui/identity/oidc/token.py - Generic OIDC Identity Token Serializer."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.oidc.token import OIDCIdentityTokenSerializer


class TestOIDCIdentityTokenSerializer:
    """Test suite for OIDCIdentityTokenSerializer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.full_claims = {
            "sub": "oidc-user-123",
            "iss": "https://auth.example.com",
            "name": "John Doe",
            "preferred_username": "jdoe",
            "email": "john@example.com",
            "given_name": "John",
            "family_name": "Doe",
        }

    def test_initialization(self):
        """Test token serializer initialization."""
        token = OIDCIdentityTokenSerializer("oidc-token", self.full_claims)
        assert token.token == "oidc-token"
        assert token.deserialized_token == self.full_claims

    def test_is_base_identity_token(self):
        """Test inheritance from BaseIdentityToken."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test get_token returns raw token string."""
        token = OIDCIdentityTokenSerializer("oidc-xyz", {})
        assert token.get_token() == "oidc-xyz"

    def test_get_deserialized_token(self):
        """Test get_deserialized_token returns claims dict."""
        token = OIDCIdentityTokenSerializer("t", self.full_claims)
        assert token.get_deserialized_token() == self.full_claims

    def test_get_id(self):
        """Test get_id returns sub claim."""
        token = OIDCIdentityTokenSerializer("t", {"sub": "user-abc"})
        assert token.get_id() == "user-abc"

    def test_get_id_default(self):
        """Test get_id returns empty when sub missing."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_id() == ""

    def test_get_identity_tenant_id(self):
        """Test get_identity_tenant_id returns issuer."""
        token = OIDCIdentityTokenSerializer("t", {"iss": "https://auth.example.com"})
        assert token.get_identity_tenant_id() == "https://auth.example.com"

    def test_get_identity_tenant_id_default(self):
        """Test get_identity_tenant_id returns empty when no iss."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_identity_tenant_id() == ""

    def test_get_display_name(self):
        """Test get_display_name returns name claim."""
        token = OIDCIdentityTokenSerializer("t", {"name": "Jane Smith"})
        assert token.get_display_name() == "Jane Smith"

    def test_get_display_name_default(self):
        """Test get_display_name returns empty when no name."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_display_name() == ""

    def test_get_principal_name_from_preferred_username(self):
        """Test get_principal_name returns preferred_username."""
        token = OIDCIdentityTokenSerializer("t", {"preferred_username": "jdoe", "email": "x@y.com"})
        assert token.get_principal_name() == "jdoe"

    def test_get_principal_name_fallback_to_email(self):
        """Test get_principal_name falls back to email."""
        token = OIDCIdentityTokenSerializer("t", {"email": "user@example.com"})
        assert token.get_principal_name() == "user@example.com"

    def test_get_principal_name_default(self):
        """Test get_principal_name returns empty when both missing."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_principal_name() == ""

    def test_get_firstname_from_given_name(self):
        """Test get_firstname returns given_name."""
        token = OIDCIdentityTokenSerializer("t", {"given_name": "John"})
        assert token.get_firstname() == "John"

    def test_get_firstname_from_name_split(self):
        """Test get_firstname extracts from name when no given_name."""
        token = OIDCIdentityTokenSerializer("t", {"name": "Alice Cooper"})
        assert token.get_firstname() == "Alice"

    def test_get_firstname_default(self):
        """Test get_firstname returns empty when nothing available."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_firstname() == ""

    def test_get_lastname_from_family_name(self):
        """Test get_lastname returns family_name."""
        token = OIDCIdentityTokenSerializer("t", {"family_name": "Doe"})
        assert token.get_lastname() == "Doe"

    def test_get_lastname_from_name_split(self):
        """Test get_lastname extracts from name when no family_name."""
        token = OIDCIdentityTokenSerializer("t", {"name": "Alice Cooper"})
        assert token.get_lastname() == "Cooper"

    def test_get_lastname_default(self):
        """Test get_lastname returns empty when nothing available."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_lastname() == ""

    def test_get_mail(self):
        """Test get_mail returns email claim."""
        token = OIDCIdentityTokenSerializer("t", {"email": "user@example.com"})
        assert token.get_mail() == "user@example.com"

    def test_get_mail_default(self):
        """Test get_mail returns empty when no email."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test get_identity_provider returns OIDC enum value."""
        token = OIDCIdentityTokenSerializer("t", {})
        assert token.get_identity_provider() == IdenityProviderEnum.OIDC.value

    def test_full_token_scenario(self):
        """Test all getters with full claims."""
        token = OIDCIdentityTokenSerializer("full-token", self.full_claims)

        assert token.get_id() == "oidc-user-123"
        assert token.get_identity_tenant_id() == "https://auth.example.com"
        assert token.get_display_name() == "John Doe"
        assert token.get_principal_name() == "jdoe"
        assert token.get_firstname() == "John"
        assert token.get_lastname() == "Doe"
        assert token.get_mail() == "john@example.com"
        assert token.get_identity_provider() == IdenityProviderEnum.OIDC.value
