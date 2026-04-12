"""Unit tests for unifiedui/core/identity/factory.py - Identity Token & Provider Factories."""

import time
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from unifiedui.identity.aws_cognito.provider import AWSCognitoIdentityProvider
from unifiedui.identity.aws_cognito.token import AWSCognitoIdentityTokenSerializer
from unifiedui.identity.extra_id.provider import ExtraIDIdentityProvider
from unifiedui.identity.extra_id.token import ExtraIDIdentityTokenSerializer
from unifiedui.identity.google.provider import GoogleIdentityProvider
from unifiedui.identity.google.token import GoogleIdentityTokenSerializer
from unifiedui.identity.kerberos.provider import KerberosIdentityProvider
from unifiedui.identity.kerberos.token import KerberosIdentityTokenSerializer
from unifiedui.identity.ldap.provider import LDAPIdentityProvider
from unifiedui.identity.ldap.token import LDAPIdentityTokenSerializer
from unifiedui.identity.mock.provider import MockIdentityProvider
from unifiedui.identity.mock.token import MockIdentityToken
from unifiedui.identity.oidc.provider import OIDCIdentityProvider
from unifiedui.identity.oidc.token import OIDCIdentityTokenSerializer
from unifiedui.identity.okta.provider import OktaIdentityProvider
from unifiedui.identity.okta.token import OktaIdentityTokenSerializer
from unifiedui.identity.saml.provider import SAMLIdentityProvider
from unifiedui.identity.saml.token import SAMLIdentityTokenSerializer


def _create_mock_jwt(claims: dict, secret: str = "test-secret") -> str:
    """Create a simple HS256 JWT for testing."""
    return pyjwt.encode(claims, secret, algorithm="HS256")


class TestIdentityTokenFactoryMock:
    """Test suite for IdentityTokenFactory with mock tokens."""

    def test_create_mock_token(self):
        """Test creating a mock identity token from a valid mock JWT."""
        now = int(time.time())
        claims = {
            "iss": "https://mock.identity.provider/test",
            "oid": "mock-user-123",
            "tid": "test-tenant",
            "name": "Mock User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, MockIdentityToken)
        assert result.get_id() == "mock-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.MOCK.value

    def test_create_mock_token_expired(self):
        """Test that an expired mock token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "https://mock.identity.provider/test",
            "oid": "mock-user-123",
            "exp": now - 100,
            "iat": now - 3700,
        }
        token_str = _create_mock_jwt(claims)

        with pytest.raises(ValueError, match="Token has expired"):
            IdentityTokenFactory.create(token_str)

    def test_create_mock_token_no_expiry(self):
        """Test that a mock token without expiry works."""
        claims = {
            "iss": "https://mock.identity.provider/test",
            "oid": "mock-user-no-exp",
            "name": "No Exp User",
        }
        token_str = _create_mock_jwt(claims)

        result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, MockIdentityToken)
        assert result.get_id() == "mock-user-no-exp"


class TestIdentityTokenFactoryEntraID:
    """Test suite for IdentityTokenFactory with Entra ID tokens."""

    def test_create_entra_id_token_with_verification(self):
        """Test creating an Entra ID token with signature verification enabled."""
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "aud": "test-client-id",
            "oid": "entra-user-123",
            "tid": "test-tenant",
            "name": "Entra User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        mock_verifier = MagicMock()
        mock_verifier.verify_and_decode.return_value = claims

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = True
            with patch("unifiedui.core.identity.factory.get_token_verifier", return_value=mock_verifier):
                result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, ExtraIDIdentityTokenSerializer)
        assert result.get_id() == "entra-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.EXTRA_ID.value
        mock_verifier.verify_and_decode.assert_called_once_with(token_str)

    def test_create_entra_id_token_verification_fails(self):
        """Test that verification failure propagates."""
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "oid": "entra-user-123",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        mock_verifier = MagicMock()
        mock_verifier.verify_and_decode.side_effect = ValueError("Invalid token: bad signature")

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = True
            with patch("unifiedui.core.identity.factory.get_token_verifier", return_value=mock_verifier):
                with pytest.raises(ValueError, match="Invalid token"):
                    IdentityTokenFactory.create(token_str)

    def test_create_entra_id_token_without_verification(self):
        """Test creating an Entra ID token with verification disabled (dev mode)."""
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "oid": "entra-user-456",
            "tid": "test-tenant",
            "name": "Dev User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, ExtraIDIdentityTokenSerializer)
        assert result.get_id() == "entra-user-456"

    def test_create_entra_id_token_v2_issuer_with_verification(self):
        """Test creating an Entra ID token with v2.0 issuer format."""
        now = int(time.time())
        claims = {
            "iss": "https://login.microsoftonline.com/test-tenant-id/v2.0",
            "aud": "api://test-client-id",
            "oid": "entra-v2-user-123",
            "tid": "test-tenant-id",
            "name": "Entra V2 User",
            "preferred_username": "v2user@example.com",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        mock_verifier = MagicMock()
        mock_verifier.verify_and_decode.return_value = claims

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = True
            with patch("unifiedui.core.identity.factory.get_token_verifier", return_value=mock_verifier):
                result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, ExtraIDIdentityTokenSerializer)
        assert result.get_id() == "entra-v2-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.EXTRA_ID.value
        mock_verifier.verify_and_decode.assert_called_once_with(token_str)

    def test_create_entra_id_token_v2_issuer_without_verification(self):
        """Test creating an Entra ID token with v2.0 issuer and verification disabled."""
        now = int(time.time())
        claims = {
            "iss": "https://login.microsoftonline.com/test-tenant-id/v2.0",
            "oid": "entra-v2-user-456",
            "tid": "test-tenant-id",
            "name": "Dev V2 User",
            "preferred_username": "v2dev@example.com",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, ExtraIDIdentityTokenSerializer)
        assert result.get_id() == "entra-v2-user-456"

    def test_create_entra_id_token_no_verification_but_expired(self):
        """Test that an expired token fails even when verification is disabled."""
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "oid": "expired-user",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            with pytest.raises(ValueError, match="Token has expired"):
                IdentityTokenFactory.create(token_str)


class TestIdentityTokenFactoryErrors:
    """Test suite for IdentityTokenFactory error cases."""

    def test_invalid_jwt_format(self):
        """Test that a completely invalid JWT raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JWT token"):
            IdentityTokenFactory.create("not-a-jwt-at-all")

    def test_unsupported_issuer(self):
        """Test that an unsupported issuer raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "https://unsupported.issuer.com/",
            "oid": "user-123",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with pytest.raises(ValueError, match="Unsupported token issuer"):
            IdentityTokenFactory.create(token_str)

    def test_missing_issuer(self):
        """Test that a token with no issuer raises ValueError."""
        claims = {"oid": "user-123"}
        token_str = _create_mock_jwt(claims)

        with pytest.raises(ValueError, match="Unsupported token issuer"):
            IdentityTokenFactory.create(token_str)


class TestIdentityProviderFactory:
    """Test suite for IdentityProviderFactory."""

    def test_create_mock_provider(self):
        """Test creating a mock identity provider."""
        mock_token = MockIdentityToken(user_id="test-user", name="Test User")

        provider = IdentityProviderFactory.create(mock_token)

        assert isinstance(provider, MockIdentityProvider)

    def test_create_extra_id_provider(self):
        """Test creating an Entra ID identity provider."""
        deserialized = {
            "oid": "entra-user",
            "tid": "tenant-123",
            "name": "Entra User",
        }
        token = ExtraIDIdentityTokenSerializer("fake-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_client_secret = None
            mock_settings.identity_tenant_id = None
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, ExtraIDIdentityProvider)

    def test_unsupported_provider(self):
        """Test that an unsupported identity provider raises ValueError."""
        mock_token = MagicMock()
        mock_token.get_identity_provider.return_value = "UNSUPPORTED_PROVIDER"

        with pytest.raises(ValueError, match="Unsupported identity provider"):
            IdentityProviderFactory.create(mock_token)


class TestIdentityTokenFactoryGoogle:
    """Test suite for IdentityTokenFactory with Google tokens."""

    def test_create_google_token_with_verification(self):
        """Test creating a Google token with signature verification enabled."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id.apps.googleusercontent.com",
            "sub": "google-user-123",
            "hd": "acme.com",
            "email": "user@acme.com",
            "name": "Acme User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        mock_verifier = MagicMock()
        mock_verifier.verify_and_decode.return_value = claims

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = True
            mock_settings.google_client_id = "google-client-id.apps.googleusercontent.com"
            with patch("unifiedui.core.identity.factory._get_google_token_verifier", return_value=mock_verifier):
                result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, GoogleIdentityTokenSerializer)
        assert result.get_id() == "google-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.GOOGLE_IDENTITY.value
        assert result.get_identity_tenant_id() == "acme.com"
        mock_verifier.verify_and_decode.assert_called_once_with(token_str)

    def test_create_google_token_without_verification(self):
        """Test creating a Google token with verification disabled (dev mode)."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "google-user-456",
            "hd": "example.com",
            "email": "dev@example.com",
            "name": "Dev User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, GoogleIdentityTokenSerializer)
        assert result.get_id() == "google-user-456"
        assert result.get_mail() == "dev@example.com"

    def test_create_google_token_expired(self):
        """Test that expired Google token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "expired-user",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            with pytest.raises(ValueError, match="Token has expired"):
                IdentityTokenFactory.create(token_str)


class TestIdentityTokenFactoryAWSCognito:
    """Test suite for IdentityTokenFactory with AWS Cognito tokens."""

    def test_create_cognito_token_with_verification(self):
        """Test creating a Cognito token with signature verification enabled."""
        now = int(time.time())
        claims = {
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbCdEfGhI",
            "aud": "cognito-client-id-123",
            "sub": "cognito-user-123",
            "email": "user@company.com",
            "name": "Cognito User",
            "cognito:username": "cognitouser",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        mock_verifier = MagicMock()
        mock_verifier.verify_and_decode.return_value = claims

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = True
            mock_settings.aws_cognito_client_id = "cognito-client-id-123"
            with patch("unifiedui.core.identity.factory._get_cognito_token_verifier", return_value=mock_verifier):
                result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, AWSCognitoIdentityTokenSerializer)
        assert result.get_id() == "cognito-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.AWS_COGNITO.value
        assert result.get_identity_tenant_id() == "us-east-1_AbCdEfGhI"
        mock_verifier.verify_and_decode.assert_called_once_with(token_str)

    def test_create_cognito_token_without_verification(self):
        """Test creating a Cognito token with verification disabled (dev mode)."""
        now = int(time.time())
        claims = {
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XyZaBcDeF",
            "sub": "cognito-user-456",
            "email": "dev@company.com",
            "name": "Dev User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, AWSCognitoIdentityTokenSerializer)
        assert result.get_id() == "cognito-user-456"
        assert result.get_mail() == "dev@company.com"

    def test_create_cognito_token_expired(self):
        """Test that expired Cognito token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbCdEfGhI",
            "sub": "expired-user",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            with pytest.raises(ValueError, match="Token has expired"):
                IdentityTokenFactory.create(token_str)

    def test_create_cognito_token_different_regions(self):
        """Test Cognito token creation works for different AWS regions."""
        now = int(time.time())
        regions = ["us-east-1", "eu-west-1", "ap-southeast-1", "us-west-2"]

        for region in regions:
            claims = {
                "iss": f"https://cognito-idp.{region}.amazonaws.com/{region}_PoolId",
                "sub": f"user-{region}",
                "exp": now + 3600,
            }
            token_str = _create_mock_jwt(claims)

            with patch("unifiedui.core.config.settings") as mock_settings:
                mock_settings.identity_verify_signature = False
                result = IdentityTokenFactory.create(token_str)

            assert isinstance(result, AWSCognitoIdentityTokenSerializer)
            assert result.get_identity_tenant_id() == f"{region}_PoolId"


class TestIdentityProviderFactoryGoogle:
    """Test suite for IdentityProviderFactory with Google tokens."""

    def test_create_google_provider(self):
        """Test creating a Google identity provider."""
        deserialized = {
            "sub": "google-user",
            "hd": "acme.com",
            "email": "user@acme.com",
            "name": "Google User",
        }
        token = GoogleIdentityTokenSerializer("google-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.google_service_account_token = "sa-token-123"
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, GoogleIdentityProvider)

    def test_create_google_provider_no_service_account(self):
        """Test creating a Google provider without service account token."""
        deserialized = {
            "sub": "google-user",
            "hd": "acme.com",
            "email": "user@acme.com",
        }
        token = GoogleIdentityTokenSerializer("google-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.google_service_account_token = None
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, GoogleIdentityProvider)


class TestIdentityProviderFactoryAWSCognito:
    """Test suite for IdentityProviderFactory with AWS Cognito tokens."""

    def test_create_cognito_provider(self):
        """Test creating an AWS Cognito identity provider."""
        deserialized = {
            "sub": "cognito-user",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "email": "user@company.com",
        }
        token = AWSCognitoIdentityTokenSerializer("cognito-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.aws_cognito_region = "us-east-1"
            mock_settings.aws_cognito_user_pool_id = "us-east-1_TestPool"
            mock_settings.aws_cognito_access_key_id = None
            mock_settings.aws_cognito_secret_access_key = None
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, AWSCognitoIdentityProvider)

    def test_create_cognito_provider_with_credentials(self):
        """Test creating a Cognito provider with explicit AWS credentials."""
        deserialized = {
            "sub": "cognito-user",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_Pool",
            "email": "user@company.com",
        }
        token = AWSCognitoIdentityTokenSerializer("cognito-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.aws_cognito_region = "eu-west-1"
            mock_settings.aws_cognito_user_pool_id = "eu-west-1_Pool"
            mock_settings.aws_cognito_access_key_id = "AKIAIOSFODNN7EXAMPLE"
            mock_settings.aws_cognito_secret_access_key = "wJalrXUtnFEMI/bPxRfiCYEXAMPLEKEY"
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, AWSCognitoIdentityProvider)

    def test_create_cognito_provider_missing_config(self):
        """Test that missing Cognito config raises ValueError."""
        deserialized = {
            "sub": "cognito-user",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Pool",
        }
        token = AWSCognitoIdentityTokenSerializer("cognito-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.aws_cognito_region = None
            mock_settings.aws_cognito_user_pool_id = None
            with pytest.raises(ValueError, match="AWS_COGNITO_REGION"):
                IdentityProviderFactory.create(token)


class TestIdentityTokenFactoryLDAP:
    """Test suite for IdentityTokenFactory with LDAP tokens."""

    def test_create_ldap_token(self):
        """Test creating an LDAP token from a gateway-issued JWT."""
        now = int(time.time())
        claims = {
            "iss": "ldap://ldap.acme.com",
            "sub": "ldap-user-123",
            "uid": "jdoe",
            "cn": "John Doe",
            "mail": "john@acme.com",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_issuer_url = None
            mock_settings.saml_entity_id = None
            mock_settings.ldap_server_url = "ldap://ldap.acme.com"
            mock_settings.ldap_jwt_secret = "test-secret"
            mock_settings.kerberos_realm = None
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, LDAPIdentityTokenSerializer)
        assert result.get_id() == "ldap-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.LDAP.value

    def test_create_ldap_token_expired(self):
        """Test that expired LDAP token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "ldap://ldap.acme.com",
            "sub": "expired-user",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_issuer_url = None
            mock_settings.saml_entity_id = None
            mock_settings.ldap_server_url = "ldap://ldap.acme.com"
            mock_settings.ldap_jwt_secret = "test-secret"
            mock_settings.kerberos_realm = None
            with pytest.raises(ValueError, match="Invalid LDAP token: Signature has expired"):
                IdentityTokenFactory.create(token_str)

    def test_create_ldaps_token(self):
        """Test creating an LDAPS token (SSL)."""
        now = int(time.time())
        claims = {
            "iss": "ldaps://ldap.acme.com",
            "sub": "ldaps-user",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_issuer_url = None
            mock_settings.saml_entity_id = None
            mock_settings.ldap_server_url = "ldaps://ldap.acme.com"
            mock_settings.ldap_jwt_secret = "test-secret"
            mock_settings.kerberos_realm = None
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, LDAPIdentityTokenSerializer)


class TestIdentityTokenFactoryKerberos:
    """Test suite for IdentityTokenFactory with Kerberos tokens."""

    def test_create_kerberos_token(self):
        """Test creating a Kerberos token from a gateway-issued JWT."""
        now = int(time.time())
        claims = {
            "iss": "krb://ACME.COM",
            "sub": "krb-user-123",
            "principal": "jdoe@ACME.COM",
            "realm": "ACME.COM",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_issuer_url = None
            mock_settings.saml_entity_id = None
            mock_settings.ldap_server_url = None
            mock_settings.kerberos_realm = "ACME.COM"
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, KerberosIdentityTokenSerializer)
        assert result.get_id() == "krb-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.KERBEROS.value

    def test_create_kerberos_token_expired(self):
        """Test that expired Kerberos token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "krb://ACME.COM",
            "sub": "expired",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_issuer_url = None
            mock_settings.saml_entity_id = None
            mock_settings.ldap_server_url = None
            mock_settings.kerberos_realm = "ACME.COM"
            with pytest.raises(ValueError, match="Token has expired"):
                IdentityTokenFactory.create(token_str)


class TestIdentityTokenFactorySAML:
    """Test suite for IdentityTokenFactory with SAML tokens."""

    def test_create_saml_token(self):
        """Test creating a SAML token from a gateway-converted JWT."""
        now = int(time.time())
        claims = {
            "iss": "https://idp.acme.com/saml",
            "uid": "saml-user-123",
            "displayName": "John Doe",
            "email": "john@acme.com",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_issuer_url = None
            mock_settings.saml_entity_id = "https://idp.acme.com/saml"
            mock_settings.ldap_server_url = None
            mock_settings.kerberos_realm = None
            mock_settings.saml_attribute_map_id = "uid"
            mock_settings.saml_attribute_map_email = "email"
            mock_settings.saml_attribute_map_display_name = "displayName"
            mock_settings.saml_attribute_map_first_name = "firstName"
            mock_settings.saml_attribute_map_last_name = "lastName"
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, SAMLIdentityTokenSerializer)
        assert result.get_id() == "saml-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.SAML.value

    def test_create_saml_token_expired(self):
        """Test that expired SAML token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "https://idp.acme.com/saml",
            "uid": "expired-user",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_issuer_url = None
            mock_settings.saml_entity_id = "https://idp.acme.com/saml"
            mock_settings.ldap_server_url = None
            mock_settings.kerberos_realm = None
            mock_settings.saml_attribute_map_id = "uid"
            mock_settings.saml_attribute_map_email = "email"
            mock_settings.saml_attribute_map_display_name = "displayName"
            mock_settings.saml_attribute_map_first_name = "firstName"
            mock_settings.saml_attribute_map_last_name = "lastName"
            with pytest.raises(ValueError, match="Token has expired"):
                IdentityTokenFactory.create(token_str)


class TestIdentityTokenFactoryOkta:
    """Test suite for IdentityTokenFactory with Okta tokens."""

    def test_create_okta_token_with_verification(self):
        """Test creating an Okta token with signature verification enabled."""
        now = int(time.time())
        claims = {
            "iss": "https://dev-12345.okta.com/oauth2/default",
            "sub": "okta-user-123",
            "uid": "okta-uid-123",
            "email": "user@acme.com",
            "name": "Okta User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        mock_verifier = MagicMock()
        mock_verifier.verify_and_decode.return_value = claims

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = True
            mock_settings.okta_client_id = "okta-client-id"
            with patch("unifiedui.core.identity.factory._get_okta_token_verifier", return_value=mock_verifier):
                result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, OktaIdentityTokenSerializer)
        assert result.get_id() == "okta-uid-123"
        assert result.get_identity_provider() == IdenityProviderEnum.OKTA.value
        mock_verifier.verify_and_decode.assert_called_once_with(token_str)

    def test_create_okta_token_without_verification(self):
        """Test creating an Okta token with verification disabled."""
        now = int(time.time())
        claims = {
            "iss": "https://dev-12345.okta.com/oauth2/default",
            "sub": "okta-user-456",
            "email": "dev@acme.com",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, OktaIdentityTokenSerializer)
        assert result.get_id() == "okta-user-456"

    def test_create_okta_token_expired(self):
        """Test that expired Okta token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "https://dev-12345.okta.com/oauth2/default",
            "sub": "expired-user",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            with pytest.raises(ValueError, match="Token has expired"):
                IdentityTokenFactory.create(token_str)

    def test_create_okta_preview_token(self):
        """Test Okta token creation for oktapreview domain."""
        now = int(time.time())
        claims = {
            "iss": "https://dev-12345.oktapreview.com/oauth2/default",
            "sub": "preview-user",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, OktaIdentityTokenSerializer)


class TestIdentityTokenFactoryOIDC:
    """Test suite for IdentityTokenFactory with generic OIDC tokens."""

    def test_create_oidc_token_with_verification(self):
        """Test creating an OIDC token with signature verification enabled."""
        now = int(time.time())
        claims = {
            "iss": "https://auth.example.com",
            "sub": "oidc-user-123",
            "email": "user@example.com",
            "name": "OIDC User",
            "exp": now + 3600,
            "iat": now,
        }
        token_str = _create_mock_jwt(claims)

        mock_verifier = MagicMock()
        mock_verifier.verify_and_decode.return_value = claims

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = True
            mock_settings.oidc_issuer_url = "https://auth.example.com"
            mock_settings.oidc_client_id = "oidc-client-id"
            mock_settings.oidc_jwks_url = "https://auth.example.com/.well-known/jwks.json"
            with patch("unifiedui.core.identity.factory._get_oidc_token_verifier", return_value=mock_verifier):
                result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, OIDCIdentityTokenSerializer)
        assert result.get_id() == "oidc-user-123"
        assert result.get_identity_provider() == IdenityProviderEnum.OIDC.value
        mock_verifier.verify_and_decode.assert_called_once_with(token_str)

    def test_create_oidc_token_without_verification(self):
        """Test creating an OIDC token with verification disabled."""
        now = int(time.time())
        claims = {
            "iss": "https://auth.example.com",
            "sub": "oidc-user-456",
            "email": "dev@example.com",
            "exp": now + 3600,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            mock_settings.oidc_issuer_url = "https://auth.example.com"
            result = IdentityTokenFactory.create(token_str)

        assert isinstance(result, OIDCIdentityTokenSerializer)
        assert result.get_id() == "oidc-user-456"

    def test_create_oidc_token_expired(self):
        """Test that expired OIDC token raises ValueError."""
        now = int(time.time())
        claims = {
            "iss": "https://auth.example.com",
            "sub": "expired-user",
            "exp": now - 100,
        }
        token_str = _create_mock_jwt(claims)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_verify_signature = False
            mock_settings.oidc_issuer_url = "https://auth.example.com"
            with pytest.raises(ValueError, match="Token has expired"):
                IdentityTokenFactory.create(token_str)


class TestIdentityProviderFactoryLDAP:
    """Test suite for IdentityProviderFactory with LDAP tokens."""

    def test_create_ldap_provider(self):
        """Test creating an LDAP identity provider."""
        deserialized = {
            "sub": "ldap-user-1",
            "uid": "jdoe",
            "cn": "John Doe",
        }
        token = LDAPIdentityTokenSerializer("ldap-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.ldap_server_url = "ldap://ldap.acme.com"
            mock_settings.ldap_bind_dn = "cn=admin,dc=acme,dc=com"
            mock_settings.ldap_bind_password = "secret"
            mock_settings.ldap_base_dn = "dc=acme,dc=com"
            mock_settings.ldap_user_search_filter = "(objectClass=person)"
            mock_settings.ldap_group_search_filter = "(objectClass=groupOfNames)"
            mock_settings.ldap_use_ssl = True
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, LDAPIdentityProvider)

    def test_create_ldap_provider_missing_config(self):
        """Test that missing LDAP_SERVER_URL raises ValueError."""
        deserialized = {"sub": "ldap-user"}
        token = LDAPIdentityTokenSerializer("ldap-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.ldap_server_url = None
            with pytest.raises(ValueError, match="LDAP_SERVER_URL"):
                IdentityProviderFactory.create(token)


class TestIdentityProviderFactoryKerberos:
    """Test suite for IdentityProviderFactory with Kerberos tokens."""

    def test_create_kerberos_provider(self):
        """Test creating a Kerberos identity provider."""
        deserialized = {
            "sub": "krb-user-1",
            "principal": "jdoe@ACME.COM",
            "realm": "ACME.COM",
        }
        token = KerberosIdentityTokenSerializer("krb-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.kerberos_ldap_url = "ldap://dc.acme.com"
            mock_settings.kerberos_ldap_base_dn = "dc=acme,dc=com"
            mock_settings.kerberos_realm = "ACME.COM"
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, KerberosIdentityProvider)

    def test_create_kerberos_provider_no_ldap(self):
        """Test creating Kerberos provider without LDAP URL."""
        deserialized = {"sub": "krb-user"}
        token = KerberosIdentityTokenSerializer("krb-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.kerberos_ldap_url = None
            mock_settings.kerberos_ldap_base_dn = None
            mock_settings.kerberos_realm = None
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, KerberosIdentityProvider)


class TestIdentityProviderFactorySAML:
    """Test suite for IdentityProviderFactory with SAML tokens."""

    def test_create_saml_provider(self):
        """Test creating a SAML identity provider."""
        deserialized = {
            "uid": "saml-user-1",
            "iss": "https://idp.acme.com/saml",
            "displayName": "John Doe",
        }
        token = SAMLIdentityTokenSerializer("saml-token", deserialized)
        provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, SAMLIdentityProvider)


class TestIdentityProviderFactoryOkta:
    """Test suite for IdentityProviderFactory with Okta tokens."""

    def test_create_okta_provider(self):
        """Test creating an Okta identity provider."""
        deserialized = {
            "uid": "okta-user-1",
            "iss": "https://dev-12345.okta.com/oauth2/default",
            "email": "user@acme.com",
        }
        token = OktaIdentityTokenSerializer("okta-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.okta_domain = "dev-12345.okta.com"
            mock_settings.okta_api_token = "ssws-token"
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, OktaIdentityProvider)

    def test_create_okta_provider_missing_config(self):
        """Test that missing OKTA_DOMAIN raises ValueError."""
        deserialized = {"sub": "okta-user"}
        token = OktaIdentityTokenSerializer("okta-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.okta_domain = None
            with pytest.raises(ValueError, match="OKTA_DOMAIN"):
                IdentityProviderFactory.create(token)


class TestIdentityProviderFactoryOIDC:
    """Test suite for IdentityProviderFactory with OIDC tokens."""

    def test_create_oidc_provider(self):
        """Test creating a generic OIDC identity provider."""
        deserialized = {
            "sub": "oidc-user-1",
            "iss": "https://auth.example.com",
            "email": "user@example.com",
        }
        token = OIDCIdentityTokenSerializer("oidc-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_userinfo_url = "https://auth.example.com/userinfo"
            mock_settings.oidc_issuer_url = "https://auth.example.com"
            mock_settings.oidc_zitadel_management_api_url = None
            mock_settings.oidc_zitadel_service_token = None
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, OIDCIdentityProvider)

    def test_create_oidc_provider_no_userinfo(self):
        """Test creating OIDC provider without UserInfo endpoint."""
        deserialized = {"sub": "oidc-user"}
        token = OIDCIdentityTokenSerializer("oidc-token", deserialized)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.oidc_userinfo_url = None
            provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, OIDCIdentityProvider)
