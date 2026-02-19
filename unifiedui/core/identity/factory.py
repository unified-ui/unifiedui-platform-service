"""Factory classes for identity token deserialization and provider creation."""

import jwt
import time

from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.token_verifier import get_token_verifier
from unifiedui.identity.extra_id.provider import ExtraIDIdentityProvider
from unifiedui.identity.extra_id.token import ExtraIDIdentityTokenSerializer
from unifiedui.identity.mock.token import MockIdentityToken
from unifiedui.identity.mock.provider import MockIdentityProvider
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class IdentityTokenFactory:
    """Factory for creating identity token instances from raw JWT strings."""

    @staticmethod
    def create(token: str) -> BaseIdentityToken:
        """Create an identity token from a raw JWT string.

        First peeks at the unverified claims to determine the issuer,
        then applies full signature + audience verification for production issuers.
        Mock tokens (test issuer) skip signature verification.

        Args:
            token: Raw JWT token string.

        Returns:
            Typed identity token instance.

        Raises:
            ValueError: If the token is invalid, expired, or from an unsupported issuer.
        """
        try:
            unverified_claims: dict = jwt.decode(
                token,
                options={"verify_signature": False},
            )
        except InvalidTokenError as e:
            raise ValueError(f"Invalid JWT token: {str(e)}")

        iss: str = unverified_claims.get("iss", "")

        if iss.startswith("https://mock.identity.provider/"):
            return IdentityTokenFactory._create_mock_token(token, unverified_claims)

        if iss.startswith("https://sts.windows.net/"):
            return IdentityTokenFactory._create_entra_id_token(token)

        raise ValueError(f"Unsupported token issuer: {iss}")

    @staticmethod
    def _create_mock_token(token: str, unverified_claims: dict) -> MockIdentityToken:
        """Create a mock identity token for testing (no signature verification).

        Args:
            token: Raw JWT token string.
            unverified_claims: Pre-decoded claims.

        Returns:
            MockIdentityToken instance.
        """
        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        mock_token = MockIdentityToken.__new__(MockIdentityToken)
        BaseIdentityToken.__init__(mock_token, token, unverified_claims)
        mock_token._identity_provider = IdenityProviderEnum.MOCK.value
        return mock_token

    @staticmethod
    def _create_entra_id_token(token: str) -> ExtraIDIdentityTokenSerializer:
        """Create an Entra ID token with full JWKS signature and audience verification.

        Args:
            token: Raw JWT token string.

        Returns:
            ExtraIDIdentityTokenSerializer instance.

        Raises:
            ValueError: If signature or audience validation fails.
        """
        from unifiedui.core.config import settings

        if settings.identity_verify_signature:
            verifier = get_token_verifier()
            verified_claims = verifier.verify_and_decode(token)
            return ExtraIDIdentityTokenSerializer(token, verified_claims)

        logger.warning("Token signature verification is DISABLED — not recommended for production")
        unverified_claims: dict = jwt.decode(token, options={"verify_signature": False})

        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return ExtraIDIdentityTokenSerializer(token, unverified_claims)


class IdentityProviderFactory:
    """Factory for creating identity provider instances based on the token type."""

    @staticmethod
    def create(identity_token: BaseIdentityToken) -> BaseIdentityProvider:
        """Create an identity provider from the given identity token.

        Args:
            identity_token: Typed identity token instance.

        Returns:
            Identity provider for the token's identity system.

        Raises:
            ValueError: If the identity provider is not supported.
        """
        match identity_token.get_identity_provider():
            case IdenityProviderEnum.MOCK.value:
                return MockIdentityProvider(identity_token=identity_token)
            case IdenityProviderEnum.EXTRA_ID.value:
                return ExtraIDIdentityProvider(identity_token=identity_token)

        raise ValueError(f"Unsupported identity provider for: {identity_token.get_identity_provider()}")
