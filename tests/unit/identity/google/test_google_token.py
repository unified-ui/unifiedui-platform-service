"""Unit tests for unifiedui/identity/google/token.py - Google Identity Token."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.google.token import GoogleIdentityTokenSerializer


class TestGoogleIdentityTokenSerializer:
    """Test suite for GoogleIdentityTokenSerializer."""

    def test_initialization(self):
        """Test token initialization."""
        token_str = "google-jwt-token-string"
        deserialized = {"sub": "google-user-123", "hd": "example.com"}

        token = GoogleIdentityTokenSerializer(token_str, deserialized)

        assert token.token == token_str
        assert token.deserialized_token == deserialized
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test getting the raw token string."""
        token_str = "test-google-token"
        token = GoogleIdentityTokenSerializer(token_str, {})

        assert token.get_token() == token_str

    def test_get_deserialized_token(self):
        """Test getting deserialized token dict."""
        deserialized = {"sub": "user-123", "name": "Test User"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_deserialized_token() == deserialized

    def test_get_id(self):
        """Test getting user ID from sub claim."""
        deserialized = {"sub": "google-user-abc-123"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_id() == "google-user-abc-123"

    def test_get_id_default(self):
        """Test getting user ID returns empty string when missing."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_id() == ""

    def test_get_identity_tenant_id(self):
        """Test getting tenant ID from hd claim (Google Workspace domain)."""
        deserialized = {"hd": "acme.com"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_identity_tenant_id() == "acme.com"

    def test_get_identity_tenant_id_default(self):
        """Test getting tenant ID returns empty string for personal Gmail."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_identity_tenant_id() == ""

    def test_get_display_name(self):
        """Test getting display name."""
        deserialized = {"name": "John Doe"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_display_name() == "John Doe"

    def test_get_display_name_default(self):
        """Test getting display name returns empty string when missing."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_display_name() == ""

    def test_get_principal_name(self):
        """Test getting principal name from email claim."""
        deserialized = {"email": "john@acme.com"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_principal_name() == "john@acme.com"

    def test_get_principal_name_default(self):
        """Test getting principal name returns empty string when missing."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_principal_name() == ""

    def test_get_firstname_from_given_name(self):
        """Test getting firstname from given_name claim."""
        deserialized = {"given_name": "John", "name": "John Doe"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_firstname() == "John"

    def test_get_firstname_from_name_split(self):
        """Test getting firstname by splitting name when given_name missing."""
        deserialized = {"name": "Jane Smith"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_firstname() == "Jane"

    def test_get_firstname_from_name_no_space(self):
        """Test firstname returns empty when name has no space."""
        deserialized = {"name": "SingleName"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_firstname() == ""

    def test_get_firstname_default(self):
        """Test firstname returns empty string when all fields missing."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_firstname() == ""

    def test_get_lastname_from_family_name(self):
        """Test getting lastname from family_name claim."""
        deserialized = {"family_name": "Doe", "name": "John Doe"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_lastname() == "Doe"

    def test_get_lastname_from_name_split(self):
        """Test getting lastname by splitting name when family_name missing."""
        deserialized = {"name": "Jane Smith"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_lastname() == "Smith"

    def test_get_lastname_from_name_multiple_parts(self):
        """Test lastname with multi-part name."""
        deserialized = {"name": "John von Neumann"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_lastname() == "von Neumann"

    def test_get_lastname_default(self):
        """Test lastname returns empty string when all fields missing."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_lastname() == ""

    def test_get_mail(self):
        """Test getting email address."""
        deserialized = {"email": "john@acme.com"}
        token = GoogleIdentityTokenSerializer("token", deserialized)

        assert token.get_mail() == "john@acme.com"

    def test_get_mail_default(self):
        """Test getting email returns empty string when missing."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test that identity provider is GOOGLE_IDENTITY."""
        token = GoogleIdentityTokenSerializer("token", {})

        assert token.get_identity_provider() == IdenityProviderEnum.GOOGLE_IDENTITY.value

    def test_full_google_workspace_token(self):
        """Test a complete Google Workspace token with all claims."""
        deserialized = {
            "iss": "https://accounts.google.com",
            "sub": "112345678901234567890",
            "aud": "google-client-id.apps.googleusercontent.com",
            "hd": "enterprise.com",
            "email": "alice@enterprise.com",
            "email_verified": True,
            "name": "Alice Johnson",
            "given_name": "Alice",
            "family_name": "Johnson",
            "picture": "https://lh3.googleusercontent.com/a/photo",
            "iat": 1700000000,
            "exp": 1700003600,
        }
        token = GoogleIdentityTokenSerializer("full-google-token", deserialized)

        assert token.get_id() == "112345678901234567890"
        assert token.get_identity_tenant_id() == "enterprise.com"
        assert token.get_display_name() == "Alice Johnson"
        assert token.get_principal_name() == "alice@enterprise.com"
        assert token.get_firstname() == "Alice"
        assert token.get_lastname() == "Johnson"
        assert token.get_mail() == "alice@enterprise.com"
        assert token.get_identity_provider() == IdenityProviderEnum.GOOGLE_IDENTITY.value

    def test_personal_gmail_token(self):
        """Test a personal Gmail token without hd claim."""
        deserialized = {
            "iss": "https://accounts.google.com",
            "sub": "109876543210987654321",
            "email": "user@gmail.com",
            "name": "Gmail User",
        }
        token = GoogleIdentityTokenSerializer("personal-token", deserialized)

        assert token.get_id() == "109876543210987654321"
        assert token.get_identity_tenant_id() == ""
        assert token.get_mail() == "user@gmail.com"
