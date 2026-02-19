"""Unit tests for unifiedui/core/identity/token_verifier.py - JWKS Token Verifier."""
import time
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from unifiedui.core.identity.token_verifier import JWKSTokenVerifier, get_token_verifier, reset_token_verifier


def _generate_rsa_keypair():
    """Generate an RSA key pair for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


def _create_signed_token(private_key, claims: dict, headers: dict | None = None) -> str:
    """Create a signed JWT token with the given claims."""
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pyjwt.encode(claims, pem, algorithm="RS256", headers=headers)


class TestJWKSTokenVerifier:
    """Test suite for JWKSTokenVerifier."""

    def test_verify_and_decode_valid_token(self):
        """Test that a validly signed token with correct audience is decoded."""
        private_key, public_key = _generate_rsa_keypair()
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "aud": "test-client-id",
            "oid": "user-123",
            "exp": now + 3600,
            "iat": now,
        }
        token = _create_signed_token(private_key, claims, headers={"kid": "test-kid"})

        mock_signing_key = MagicMock()
        mock_signing_key.key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        verifier = JWKSTokenVerifier(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            algorithms=["RS256"],
            audience="test-client-id",
        )

        with patch.object(verifier._jwks_client, "get_signing_key_from_jwt", return_value=mock_signing_key):
            decoded = verifier.verify_and_decode(token)

        assert decoded["oid"] == "user-123"
        assert decoded["aud"] == "test-client-id"

    def test_verify_and_decode_expired_token(self):
        """Test that an expired token raises ValueError."""
        private_key, public_key = _generate_rsa_keypair()
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "aud": "test-client-id",
            "oid": "user-123",
            "exp": now - 100,
            "iat": now - 3700,
        }
        token = _create_signed_token(private_key, claims, headers={"kid": "test-kid"})

        mock_signing_key = MagicMock()
        mock_signing_key.key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        verifier = JWKSTokenVerifier(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            algorithms=["RS256"],
            audience="test-client-id",
        )

        with patch.object(verifier._jwks_client, "get_signing_key_from_jwt", return_value=mock_signing_key):
            with pytest.raises(ValueError, match="Token has expired"):
                verifier.verify_and_decode(token)

    def test_verify_and_decode_wrong_audience(self):
        """Test that a token with wrong audience raises ValueError."""
        private_key, public_key = _generate_rsa_keypair()
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "aud": "wrong-client-id",
            "oid": "user-123",
            "exp": now + 3600,
            "iat": now,
        }
        token = _create_signed_token(private_key, claims, headers={"kid": "test-kid"})

        mock_signing_key = MagicMock()
        mock_signing_key.key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        verifier = JWKSTokenVerifier(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            algorithms=["RS256"],
            audience="correct-client-id",
        )

        with patch.object(verifier._jwks_client, "get_signing_key_from_jwt", return_value=mock_signing_key):
            with pytest.raises(ValueError, match="Invalid audience"):
                verifier.verify_and_decode(token)

    def test_verify_and_decode_invalid_signature(self):
        """Test that a token signed with wrong key raises ValueError."""
        private_key_1, _ = _generate_rsa_keypair()
        _, public_key_2 = _generate_rsa_keypair()
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "aud": "test-client-id",
            "oid": "user-123",
            "exp": now + 3600,
            "iat": now,
        }
        token = _create_signed_token(private_key_1, claims, headers={"kid": "test-kid"})

        mock_signing_key = MagicMock()
        mock_signing_key.key = public_key_2.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        verifier = JWKSTokenVerifier(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            algorithms=["RS256"],
            audience="test-client-id",
        )

        with patch.object(verifier._jwks_client, "get_signing_key_from_jwt", return_value=mock_signing_key):
            with pytest.raises(ValueError, match="Invalid token"):
                verifier.verify_and_decode(token)

    def test_verify_and_decode_jwks_fetch_failure(self):
        """Test that JWKS fetch failure raises ValueError."""
        verifier = JWKSTokenVerifier(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            algorithms=["RS256"],
            audience="test-client-id",
        )

        with patch.object(
            verifier._jwks_client,
            "get_signing_key_from_jwt",
            side_effect=Exception("Network error"),
        ):
            with pytest.raises(ValueError, match="Failed to retrieve signing key"):
                verifier.verify_and_decode("some.jwt.token")

    def test_verify_and_decode_no_audience_validation(self):
        """Test that audience is not validated when audience is None."""
        private_key, public_key = _generate_rsa_keypair()
        now = int(time.time())
        claims = {
            "iss": "https://sts.windows.net/test-tenant/",
            "aud": "any-audience",
            "oid": "user-123",
            "exp": now + 3600,
            "iat": now,
        }
        token = _create_signed_token(private_key, claims, headers={"kid": "test-kid"})

        mock_signing_key = MagicMock()
        mock_signing_key.key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        verifier = JWKSTokenVerifier(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            algorithms=["RS256"],
            audience=None,
        )

        with patch.object(verifier._jwks_client, "get_signing_key_from_jwt", return_value=mock_signing_key):
            decoded = verifier.verify_and_decode(token)

        assert decoded["oid"] == "user-123"
        assert decoded["aud"] == "any-audience"


class TestGetTokenVerifier:
    """Test suite for the singleton get_token_verifier."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_token_verifier()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_token_verifier()

    def test_get_token_verifier_creates_singleton(self):
        """Test that get_token_verifier creates and returns a singleton."""
        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_jwks_url = "https://example.com/keys"
            mock_settings.identity_token_algorithms = ["RS256"]
            mock_settings.identity_client_id = "test-client"

            verifier1 = get_token_verifier()
            verifier2 = get_token_verifier()

            assert verifier1 is verifier2
            assert isinstance(verifier1, JWKSTokenVerifier)

    def test_reset_token_verifier(self):
        """Test that reset_token_verifier clears the singleton."""
        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.identity_jwks_url = "https://example.com/keys"
            mock_settings.identity_token_algorithms = ["RS256"]
            mock_settings.identity_client_id = "test-client"

            verifier1 = get_token_verifier()
            reset_token_verifier()
            verifier2 = get_token_verifier()

            assert verifier1 is not verifier2
