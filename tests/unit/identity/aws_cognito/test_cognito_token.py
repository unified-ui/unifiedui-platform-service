"""Unit tests for unifiedui/identity/aws_cognito/token.py - AWS Cognito Identity Token."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.aws_cognito.token import AWSCognitoIdentityTokenSerializer


class TestAWSCognitoIdentityTokenSerializer:
    """Test suite for AWSCognitoIdentityTokenSerializer."""

    def test_initialization(self):
        """Test token initialization."""
        token_str = "cognito-jwt-token"
        deserialized = {"sub": "cognito-user-123"}

        token = AWSCognitoIdentityTokenSerializer(token_str, deserialized)

        assert token.token == token_str
        assert token.deserialized_token == deserialized
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test getting the raw token string."""
        token_str = "test-cognito-token"
        token = AWSCognitoIdentityTokenSerializer(token_str, {})

        assert token.get_token() == token_str

    def test_get_deserialized_token(self):
        """Test getting deserialized token dict."""
        deserialized = {"sub": "user-123", "name": "Test User"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_deserialized_token() == deserialized

    def test_get_id(self):
        """Test getting user ID from sub claim."""
        deserialized = {"sub": "cognito-sub-abc-123"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_id() == "cognito-sub-abc-123"

    def test_get_id_default(self):
        """Test getting user ID returns empty string when missing."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_id() == ""

    def test_get_identity_tenant_id_from_iss(self):
        """Test getting tenant ID from issuer URL (user pool ID)."""
        deserialized = {"iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbCdEfGhI"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_identity_tenant_id() == "us-east-1_AbCdEfGhI"

    def test_get_identity_tenant_id_no_iss(self):
        """Test getting tenant ID returns empty string when no issuer."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_identity_tenant_id() == ""

    def test_get_identity_tenant_id_no_slash(self):
        """Test getting tenant ID when issuer has no slash."""
        deserialized = {"iss": "no-slash-issuer"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_identity_tenant_id() == ""

    def test_get_display_name_from_name(self):
        """Test getting display name from name claim."""
        deserialized = {"name": "John Doe"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_display_name() == "John Doe"

    def test_get_display_name_from_given_family(self):
        """Test getting display name constructed from given + family name."""
        deserialized = {"given_name": "Jane", "family_name": "Smith"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_display_name() == "Jane Smith"

    def test_get_display_name_from_email(self):
        """Test getting display name falls back to email."""
        deserialized = {"email": "user@example.com"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_display_name() == "user@example.com"

    def test_get_display_name_from_cognito_username(self):
        """Test getting display name falls back to cognito:username."""
        deserialized = {"cognito:username": "johndoe42"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_display_name() == "johndoe42"

    def test_get_display_name_default(self):
        """Test getting display name returns empty string when all missing."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_display_name() == ""

    def test_get_principal_name_from_email(self):
        """Test getting principal name from email claim."""
        deserialized = {"email": "user@example.com", "cognito:username": "user42"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_principal_name() == "user@example.com"

    def test_get_principal_name_from_cognito_username(self):
        """Test getting principal name from cognito:username when no email."""
        deserialized = {"cognito:username": "user42"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_principal_name() == "user42"

    def test_get_principal_name_from_preferred_username(self):
        """Test getting principal name from preferred_username as last resort."""
        deserialized = {"preferred_username": "preferred_user"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_principal_name() == "preferred_user"

    def test_get_principal_name_default(self):
        """Test getting principal name returns empty string when all missing."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_principal_name() == ""

    def test_get_firstname_from_given_name(self):
        """Test getting firstname from given_name claim."""
        deserialized = {"given_name": "John", "name": "John Doe"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_firstname() == "John"

    def test_get_firstname_from_name_split(self):
        """Test getting firstname by splitting name when given_name missing."""
        deserialized = {"name": "Jane Smith"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_firstname() == "Jane"

    def test_get_firstname_default(self):
        """Test firstname returns empty string when all fields missing."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_firstname() == ""

    def test_get_lastname_from_family_name(self):
        """Test getting lastname from family_name claim."""
        deserialized = {"family_name": "Doe"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_lastname() == "Doe"

    def test_get_lastname_from_name_split(self):
        """Test getting lastname by splitting name when family_name missing."""
        deserialized = {"name": "Jane Smith"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_lastname() == "Smith"

    def test_get_lastname_default(self):
        """Test lastname returns empty string when all fields missing."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_lastname() == ""

    def test_get_mail(self):
        """Test getting email address."""
        deserialized = {"email": "user@example.com"}
        token = AWSCognitoIdentityTokenSerializer("token", deserialized)

        assert token.get_mail() == "user@example.com"

    def test_get_mail_default(self):
        """Test getting email returns empty string when missing."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test that identity provider is AWS_COGNITO."""
        token = AWSCognitoIdentityTokenSerializer("token", {})

        assert token.get_identity_provider() == IdenityProviderEnum.AWS_COGNITO.value

    def test_full_cognito_token(self):
        """Test a complete Cognito token with all claims."""
        deserialized = {
            "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XyZaBcDeF",
            "aud": "4k3nd8fg9j1mno2pq3rstuv456",
            "token_use": "id",
            "auth_time": 1700000000,
            "exp": 1700003600,
            "iat": 1700000000,
            "email": "alice@company.com",
            "email_verified": True,
            "name": "Alice Johnson",
            "given_name": "Alice",
            "family_name": "Johnson",
            "cognito:username": "alice.johnson",
        }
        token = AWSCognitoIdentityTokenSerializer("full-cognito-token", deserialized)

        assert token.get_id() == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert token.get_identity_tenant_id() == "eu-west-1_XyZaBcDeF"
        assert token.get_display_name() == "Alice Johnson"
        assert token.get_principal_name() == "alice@company.com"
        assert token.get_firstname() == "Alice"
        assert token.get_lastname() == "Johnson"
        assert token.get_mail() == "alice@company.com"
        assert token.get_identity_provider() == IdenityProviderEnum.AWS_COGNITO.value
