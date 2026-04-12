"""JWT token verification with JWKS signature and audience validation."""

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from unifiedui.logger import get_logger

logger = get_logger(__name__)


class JWKSTokenVerifier:
    """Verifies JWT tokens using JWKS endpoint for signature validation and audience check."""

    def __init__(
        self,
        jwks_url: str,
        algorithms: list[str],
        audience: str | list[str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        """Initialize the JWKS token verifier.

        Args:
            jwks_url: URL of the JWKS endpoint for public key retrieval.
            algorithms: List of accepted signing algorithms (e.g. ["RS256"]).
            audience: Expected audience claim(s). Can be a single string or list
                      of accepted audiences. If None, audience is not validated.
            headers: Optional HTTP headers to include when fetching JWKS keys.
        """
        self._jwks_client = PyJWKClient(jwks_url, cache_keys=True, headers=headers or {})
        self._algorithms = algorithms
        self._audience = audience

    def verify_and_decode(self, token: str) -> dict:
        """Verify the token signature and decode claims.

        Args:
            token: Raw JWT token string.

        Returns:
            Decoded token payload as dictionary.

        Raises:
            ValueError: If token signature is invalid, expired, or audience mismatch.
        """
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        except Exception as e:
            logger.warning("Failed to retrieve signing key from JWKS: %s", e)
            raise ValueError(f"Failed to retrieve signing key: {e}")

        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_aud": self._audience is not None,
        }

        try:
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=self._algorithms,
                audience=self._audience,
                options=decode_options,
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidAudienceError:
            raise ValueError(f"Invalid audience. Expected: {self._audience}")
        except InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

        return decoded


_verifier_instance: JWKSTokenVerifier | None = None


def get_token_verifier() -> JWKSTokenVerifier:
    """Get or create the singleton JWKS token verifier from settings.

    Returns:
        Configured JWKSTokenVerifier instance.
    """
    global _verifier_instance
    if _verifier_instance is None:
        from unifiedui.core.config import settings

        client_id = settings.identity_client_id
        accepted_audiences = [client_id, f"api://{client_id}"] if client_id else None

        _verifier_instance = JWKSTokenVerifier(
            jwks_url=settings.identity_jwks_url,
            algorithms=settings.identity_token_algorithms,
            audience=accepted_audiences,
        )
    return _verifier_instance


def reset_token_verifier() -> None:
    """Reset the singleton verifier (for testing)."""
    global _verifier_instance
    _verifier_instance = None
