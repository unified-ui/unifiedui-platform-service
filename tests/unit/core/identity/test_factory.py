"""Unit tests for unifiedui/core/identity/factory.py - Identity Token & Provider Factories."""

import time
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from unifiedui.identity.extra_id.provider import ExtraIDIdentityProvider
from unifiedui.identity.extra_id.token import ExtraIDIdentityTokenSerializer
from unifiedui.identity.mock.provider import MockIdentityProvider
from unifiedui.identity.mock.token import MockIdentityToken


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

        provider = IdentityProviderFactory.create(token)

        assert isinstance(provider, ExtraIDIdentityProvider)

    def test_unsupported_provider(self):
        """Test that an unsupported identity provider raises ValueError."""
        mock_token = MagicMock()
        mock_token.get_identity_provider.return_value = "UNSUPPORTED_PROVIDER"

        with pytest.raises(ValueError, match="Unsupported identity provider"):
            IdentityProviderFactory.create(mock_token)
