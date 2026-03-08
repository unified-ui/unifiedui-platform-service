"""Unit tests for unifiedui/identity/saml/token.py - SAML Identity Token Serializer."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.saml.token import SAMLIdentityTokenSerializer


class TestSAMLIdentityTokenSerializer:
    """Test suite for SAMLIdentityTokenSerializer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.full_claims = {
            "uid": "saml-user-123",
            "sub": "saml-sub-fallback",
            "iss": "https://idp.acme.com/saml",
            "displayName": "John Doe",
            "name": "name-fallback",
            "email": "john@acme.com",
            "nameID": "nameID-fallback",
            "firstName": "John",
            "given_name": "given-fallback",
            "lastName": "Doe",
            "family_name": "family-fallback",
        }

    def test_initialization(self):
        """Test token serializer initialization with defaults."""
        token = SAMLIdentityTokenSerializer("saml-token", self.full_claims)
        assert token.token == "saml-token"
        assert token.deserialized_token == self.full_claims

    def test_is_base_identity_token(self):
        """Test inheritence from BaseIdentityToken."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test get_token returns raw token string."""
        token = SAMLIdentityTokenSerializer("saml-xyz", {})
        assert token.get_token() == "saml-xyz"

    def test_get_deserialized_token(self):
        """Test get_deserialized_token returns claims dict."""
        token = SAMLIdentityTokenSerializer("t", self.full_claims)
        assert token.get_deserialized_token() == self.full_claims

    def test_get_id_from_configured_attribute(self):
        """Test get_id returns value from configured uid attribute."""
        token = SAMLIdentityTokenSerializer("t", self.full_claims)
        assert token.get_id() == "saml-user-123"

    def test_get_id_custom_attribute(self):
        """Test get_id with custom attribute mapping."""
        token = SAMLIdentityTokenSerializer("t", {"custom_id": "abc-123"}, attribute_map_id="custom_id")
        assert token.get_id() == "abc-123"

    def test_get_id_fallback_to_sub(self):
        """Test get_id falls back to sub when configured attribute missing."""
        token = SAMLIdentityTokenSerializer("t", {"sub": "sub-val"})
        assert token.get_id() == "sub-val"

    def test_get_id_default_empty(self):
        """Test get_id returns empty string when nothing available."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert token.get_id() == ""

    def test_get_identity_tenant_id(self):
        """Test get_identity_tenant_id returns issuer."""
        token = SAMLIdentityTokenSerializer("t", {"iss": "https://idp.acme.com"})
        assert token.get_identity_tenant_id() == "https://idp.acme.com"

    def test_get_identity_tenant_id_default(self):
        """Test get_identity_tenant_id returns empty when no iss."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert token.get_identity_tenant_id() == ""

    def test_get_display_name_from_configured(self):
        """Test get_display_name returns configured attribute."""
        token = SAMLIdentityTokenSerializer("t", self.full_claims)
        assert token.get_display_name() == "John Doe"

    def test_get_display_name_custom_attribute(self):
        """Test get_display_name with custom mapping."""
        token = SAMLIdentityTokenSerializer("t", {"cn": "Custom Name"}, attribute_map_display_name="cn")
        assert token.get_display_name() == "Custom Name"

    def test_get_display_name_fallback_to_name(self):
        """Test get_display_name falls back to name claim."""
        token = SAMLIdentityTokenSerializer("t", {"name": "Fallback Name"})
        assert token.get_display_name() == "Fallback Name"

    def test_get_display_name_default(self):
        """Test get_display_name returns empty when nothing available."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert token.get_display_name() == ""

    def test_get_principal_name_from_configured_email(self):
        """Test get_principal_name returns configured email attribute."""
        token = SAMLIdentityTokenSerializer("t", self.full_claims)
        assert token.get_principal_name() == "john@acme.com"

    def test_get_principal_name_fallback_to_name_id(self):
        """Test get_principal_name falls back to nameID."""
        token = SAMLIdentityTokenSerializer("t", {"nameID": "user@example.com"})
        assert token.get_principal_name() == "user@example.com"

    def test_get_firstname_from_configured(self):
        """Test get_firstname returns configured attribute."""
        token = SAMLIdentityTokenSerializer("t", self.full_claims)
        assert token.get_firstname() == "John"

    def test_get_firstname_fallback_to_given_name(self):
        """Test get_firstname falls back to given_name."""
        token = SAMLIdentityTokenSerializer("t", {"given_name": "Jane"})
        assert token.get_firstname() == "Jane"

    def test_get_firstname_from_display_name_split(self):
        """Test get_firstname extracts from display name."""
        token = SAMLIdentityTokenSerializer("t", {"displayName": "Alice Cooper"})
        assert token.get_firstname() == "Alice"

    def test_get_firstname_default(self):
        """Test get_firstname returns empty when nothing available."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert token.get_firstname() == ""

    def test_get_lastname_from_configured(self):
        """Test get_lastname returns configured attribute."""
        token = SAMLIdentityTokenSerializer("t", self.full_claims)
        assert token.get_lastname() == "Doe"

    def test_get_lastname_fallback_to_family_name(self):
        """Test get_lastname falls back to family_name."""
        token = SAMLIdentityTokenSerializer("t", {"family_name": "Smith"})
        assert token.get_lastname() == "Smith"

    def test_get_lastname_from_display_name_split(self):
        """Test get_lastname extracts from display name."""
        token = SAMLIdentityTokenSerializer("t", {"displayName": "Alice Cooper"})
        assert token.get_lastname() == "Cooper"

    def test_get_lastname_default(self):
        """Test get_lastname returns empty when nothing available."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert token.get_lastname() == ""

    def test_get_mail_from_configured(self):
        """Test get_mail returns configured email attribute."""
        token = SAMLIdentityTokenSerializer("t", {"email": "john@acme.com"})
        assert token.get_mail() == "john@acme.com"

    def test_get_mail_custom_attribute(self):
        """Test get_mail with custom mapping."""
        token = SAMLIdentityTokenSerializer("t", {"saml_mail": "a@b.com"}, attribute_map_email="saml_mail")
        assert token.get_mail() == "a@b.com"

    def test_get_mail_default(self):
        """Test get_mail returns empty when nothing available."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test get_identity_provider returns SAML enum value."""
        token = SAMLIdentityTokenSerializer("t", {})
        assert token.get_identity_provider() == IdenityProviderEnum.SAML.value

    def test_custom_attribute_mapping(self):
        """Test all getters with custom attribute mapping."""
        claims = {
            "user_id": "u-1",
            "user_email": "custom@test.com",
            "full_name": "Custom User",
            "first": "Custom",
            "last": "User",
        }
        token = SAMLIdentityTokenSerializer(
            "t",
            claims,
            attribute_map_id="user_id",
            attribute_map_email="user_email",
            attribute_map_display_name="full_name",
            attribute_map_first_name="first",
            attribute_map_last_name="last",
        )

        assert token.get_id() == "u-1"
        assert token.get_mail() == "custom@test.com"
        assert token.get_display_name() == "Custom User"
        assert token.get_firstname() == "Custom"
        assert token.get_lastname() == "User"

    def test_full_token_scenario(self):
        """Test all getters with full claims and defaults."""
        token = SAMLIdentityTokenSerializer("full-token", self.full_claims)

        assert token.get_id() == "saml-user-123"
        assert token.get_identity_tenant_id() == "https://idp.acme.com/saml"
        assert token.get_display_name() == "John Doe"
        assert token.get_principal_name() == "john@acme.com"
        assert token.get_firstname() == "John"
        assert token.get_lastname() == "Doe"
        assert token.get_mail() == "john@acme.com"
        assert token.get_identity_provider() == IdenityProviderEnum.SAML.value
