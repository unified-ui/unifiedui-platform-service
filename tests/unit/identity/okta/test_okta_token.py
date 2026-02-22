"""Unit tests for unifiedui/identity/okta/token.py - Okta Identity Token Serializer."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.okta.token import OktaIdentityTokenSerializer


class TestOktaIdentityTokenSerializer:
    """Test suite for OktaIdentityTokenSerializer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.full_claims = {
            "uid": "okta-uid-123",
            "sub": "okta-sub-456",
            "iss": "https://dev-12345.okta.com/oauth2/default",
            "name": "John Doe",
            "preferred_username": "jdoe@acme.com",
            "email": "john@acme.com",
            "given_name": "John",
            "family_name": "Doe",
        }

    def test_initialization(self):
        """Test token serializer initialization."""
        token = OktaIdentityTokenSerializer("okta-token", self.full_claims)
        assert token.token == "okta-token"
        assert token.deserialized_token == self.full_claims

    def test_is_base_identity_token(self):
        """Test inheritance from BaseIdentityToken."""
        token = OktaIdentityTokenSerializer("t", {})
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test get_token returns raw token string."""
        token = OktaIdentityTokenSerializer("okta-xyz", {})
        assert token.get_token() == "okta-xyz"

    def test_get_deserialized_token(self):
        """Test get_deserialized_token returns claims dict."""
        token = OktaIdentityTokenSerializer("t", self.full_claims)
        assert token.get_deserialized_token() == self.full_claims

    def test_get_id_from_uid(self):
        """Test get_id returns uid claim."""
        token = OktaIdentityTokenSerializer("t", {"uid": "okta-uid", "sub": "okta-sub"})
        assert token.get_id() == "okta-uid"

    def test_get_id_fallback_to_sub(self):
        """Test get_id falls back to sub when uid missing."""
        token = OktaIdentityTokenSerializer("t", {"sub": "okta-sub"})
        assert token.get_id() == "okta-sub"

    def test_get_id_default_empty(self):
        """Test get_id returns empty string when both missing."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_id() == ""

    def test_get_identity_tenant_id_okta_domain(self):
        """Test get_identity_tenant_id extracts org from Okta issuer."""
        token = OktaIdentityTokenSerializer("t", {"iss": "https://dev-12345.okta.com/oauth2/default"})
        assert token.get_identity_tenant_id() == "dev-12345"

    def test_get_identity_tenant_id_non_okta(self):
        """Test get_identity_tenant_id returns full iss for non-Okta issuer."""
        token = OktaIdentityTokenSerializer("t", {"iss": "https://custom.auth.com"})
        assert token.get_identity_tenant_id() == "https://custom.auth.com"

    def test_get_identity_tenant_id_default(self):
        """Test get_identity_tenant_id returns empty when no iss."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_identity_tenant_id() == ""

    def test_get_display_name(self):
        """Test get_display_name returns name claim."""
        token = OktaIdentityTokenSerializer("t", {"name": "Jane Smith"})
        assert token.get_display_name() == "Jane Smith"

    def test_get_display_name_default(self):
        """Test get_display_name returns empty when no name."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_display_name() == ""

    def test_get_principal_name_from_preferred_username(self):
        """Test get_principal_name returns preferred_username."""
        token = OktaIdentityTokenSerializer("t", {"preferred_username": "user@acme.com", "email": "x@y.com"})
        assert token.get_principal_name() == "user@acme.com"

    def test_get_principal_name_fallback_to_email(self):
        """Test get_principal_name falls back to email."""
        token = OktaIdentityTokenSerializer("t", {"email": "user@acme.com"})
        assert token.get_principal_name() == "user@acme.com"

    def test_get_principal_name_default(self):
        """Test get_principal_name returns empty when both missing."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_principal_name() == ""

    def test_get_firstname_from_given_name(self):
        """Test get_firstname returns given_name."""
        token = OktaIdentityTokenSerializer("t", {"given_name": "John"})
        assert token.get_firstname() == "John"

    def test_get_firstname_from_name_split(self):
        """Test get_firstname extracts from name when no given_name."""
        token = OktaIdentityTokenSerializer("t", {"name": "Alice Cooper"})
        assert token.get_firstname() == "Alice"

    def test_get_firstname_default(self):
        """Test get_firstname returns empty when nothing available."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_firstname() == ""

    def test_get_lastname_from_family_name(self):
        """Test get_lastname returns family_name."""
        token = OktaIdentityTokenSerializer("t", {"family_name": "Doe"})
        assert token.get_lastname() == "Doe"

    def test_get_lastname_from_name_split(self):
        """Test get_lastname extracts from name when no family_name."""
        token = OktaIdentityTokenSerializer("t", {"name": "Alice Cooper"})
        assert token.get_lastname() == "Cooper"

    def test_get_lastname_default(self):
        """Test get_lastname returns empty when nothing available."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_lastname() == ""

    def test_get_mail(self):
        """Test get_mail returns email claim."""
        token = OktaIdentityTokenSerializer("t", {"email": "user@acme.com"})
        assert token.get_mail() == "user@acme.com"

    def test_get_mail_default(self):
        """Test get_mail returns empty when no email."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test get_identity_provider returns OKTA enum value."""
        token = OktaIdentityTokenSerializer("t", {})
        assert token.get_identity_provider() == IdenityProviderEnum.OKTA.value

    def test_full_token_scenario(self):
        """Test all getters with full claims."""
        token = OktaIdentityTokenSerializer("full-token", self.full_claims)

        assert token.get_id() == "okta-uid-123"
        assert token.get_identity_tenant_id() == "dev-12345"
        assert token.get_display_name() == "John Doe"
        assert token.get_principal_name() == "jdoe@acme.com"
        assert token.get_firstname() == "John"
        assert token.get_lastname() == "Doe"
        assert token.get_mail() == "john@acme.com"
        assert token.get_identity_provider() == IdenityProviderEnum.OKTA.value
