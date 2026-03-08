"""Factory classes for identity token deserialization and provider creation."""

import time

import jwt
from jwt.exceptions import InvalidTokenError

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.core.identity.token_verifier import JWKSTokenVerifier, get_token_verifier
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
            raise ValueError(f"Invalid JWT token: {e!s}")

        iss: str = unverified_claims.get("iss", "")

        if iss.startswith("https://mock.identity.provider/"):
            return IdentityTokenFactory._create_mock_token(token, unverified_claims)

        is_entra_v1 = iss.startswith("https://sts.windows.net/")
        is_entra_v2 = iss.startswith("https://login.microsoftonline.com/") and iss.endswith("/v2.0")

        if is_entra_v1 or is_entra_v2:
            return IdentityTokenFactory._create_entra_id_token(token)

        if iss.startswith("https://accounts.google.com"):
            return IdentityTokenFactory._create_google_token(token)

        if iss.startswith("https://cognito-idp.") and ".amazonaws.com/" in iss:
            return IdentityTokenFactory._create_aws_cognito_token(token)

        if "okta.com" in iss or ".oktapreview.com" in iss:
            return IdentityTokenFactory._create_okta_token(token, iss)

        from unifiedui.core.config import settings

        if settings.oidc_issuer_url and iss == settings.oidc_issuer_url:
            return IdentityTokenFactory._create_oidc_token(token)

        if settings.saml_entity_id and iss == settings.saml_entity_id:
            return IdentityTokenFactory._create_saml_token(token, unverified_claims)

        if settings.ldap_server_url and (iss.startswith("ldap://") or iss.startswith("ldaps://")):
            return IdentityTokenFactory._create_ldap_token(token, unverified_claims)

        if settings.kerberos_realm and iss.startswith("krb://"):
            return IdentityTokenFactory._create_kerberos_token(token, unverified_claims)

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

        logger.debug(
            "Token signature verification is disabled — expected when using delegated Microsoft Graph access tokens"
        )
        unverified_claims: dict = jwt.decode(token, options={"verify_signature": False})

        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return ExtraIDIdentityTokenSerializer(token, unverified_claims)

    @staticmethod
    def _create_google_token(token: str) -> GoogleIdentityTokenSerializer:
        """Create a Google identity token with JWKS signature verification.

        Args:
            token: Raw JWT token string.

        Returns:
            GoogleIdentityTokenSerializer instance.

        Raises:
            ValueError: If signature or audience validation fails.
        """
        from unifiedui.core.config import settings

        if settings.identity_verify_signature:
            google_verifier = _get_google_token_verifier()
            verified_claims = google_verifier.verify_and_decode(token)
            return GoogleIdentityTokenSerializer(token, verified_claims)

        unverified_claims: dict = jwt.decode(token, options={"verify_signature": False})

        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return GoogleIdentityTokenSerializer(token, unverified_claims)

    @staticmethod
    def _create_aws_cognito_token(token: str) -> AWSCognitoIdentityTokenSerializer:
        """Create an AWS Cognito identity token with JWKS signature verification.

        Args:
            token: Raw JWT token string.

        Returns:
            AWSCognitoIdentityTokenSerializer instance.

        Raises:
            ValueError: If signature or audience validation fails.
        """
        from unifiedui.core.config import settings

        if settings.identity_verify_signature:
            unverified_claims: dict = jwt.decode(token, options={"verify_signature": False})
            iss = unverified_claims.get("iss", "")
            cognito_verifier = _get_cognito_token_verifier(iss)
            verified_claims = cognito_verifier.verify_and_decode(token)
            return AWSCognitoIdentityTokenSerializer(token, verified_claims)

        unverified_claims = jwt.decode(token, options={"verify_signature": False})

        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return AWSCognitoIdentityTokenSerializer(token, unverified_claims)

    @staticmethod
    def _create_ldap_token(token: str, unverified_claims: dict) -> LDAPIdentityTokenSerializer:
        """Create an LDAP identity token (no JWKS verification, gateway-trusted).

        Args:
            token: Raw JWT token string.
            unverified_claims: Pre-decoded claims.

        Returns:
            LDAPIdentityTokenSerializer instance.
        """
        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return LDAPIdentityTokenSerializer(token, unverified_claims)

    @staticmethod
    def _create_kerberos_token(token: str, unverified_claims: dict) -> KerberosIdentityTokenSerializer:
        """Create a Kerberos identity token (gateway-converted JWT).

        Args:
            token: Raw JWT token string.
            unverified_claims: Pre-decoded claims.

        Returns:
            KerberosIdentityTokenSerializer instance.
        """
        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return KerberosIdentityTokenSerializer(token, unverified_claims)

    @staticmethod
    def _create_saml_token(token: str, unverified_claims: dict) -> SAMLIdentityTokenSerializer:
        """Create a SAML identity token (assertion-converted JWT).

        Args:
            token: Raw JWT token string.
            unverified_claims: Pre-decoded claims.

        Returns:
            SAMLIdentityTokenSerializer instance with configured attribute mapping.
        """
        from unifiedui.core.config import settings

        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return SAMLIdentityTokenSerializer(
            token,
            unverified_claims,
            attribute_map_id=settings.saml_attribute_map_id,
            attribute_map_email=settings.saml_attribute_map_email,
            attribute_map_display_name=settings.saml_attribute_map_display_name,
            attribute_map_first_name=settings.saml_attribute_map_first_name,
            attribute_map_last_name=settings.saml_attribute_map_last_name,
        )

    @staticmethod
    def _create_okta_token(token: str, issuer_url: str) -> OktaIdentityTokenSerializer:
        """Create an Okta identity token with JWKS signature verification.

        Args:
            token: Raw JWT token string.
            issuer_url: The Okta issuer URL.

        Returns:
            OktaIdentityTokenSerializer instance.

        Raises:
            ValueError: If signature or audience validation fails.
        """
        from unifiedui.core.config import settings

        if settings.identity_verify_signature:
            okta_verifier = _get_okta_token_verifier(issuer_url)
            verified_claims = okta_verifier.verify_and_decode(token)
            return OktaIdentityTokenSerializer(token, verified_claims)

        unverified_claims: dict = jwt.decode(token, options={"verify_signature": False})

        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return OktaIdentityTokenSerializer(token, unverified_claims)

    @staticmethod
    def _create_oidc_token(token: str) -> OIDCIdentityTokenSerializer:
        """Create a generic OIDC identity token with JWKS signature verification.

        Args:
            token: Raw JWT token string.

        Returns:
            OIDCIdentityTokenSerializer instance.

        Raises:
            ValueError: If signature or audience validation fails.
        """
        from unifiedui.core.config import settings

        if settings.identity_verify_signature:
            oidc_verifier = _get_oidc_token_verifier()
            verified_claims = oidc_verifier.verify_and_decode(token)
            return OIDCIdentityTokenSerializer(token, verified_claims)

        unverified_claims: dict = jwt.decode(token, options={"verify_signature": False})

        exp = unverified_claims.get("exp")
        if exp and int(time.time()) >= exp:
            raise ValueError("Token has expired")

        return OIDCIdentityTokenSerializer(token, unverified_claims)


class IdentityProviderFactory:
    """Factory for creating identity provider instances based on the token type."""

    @staticmethod
    def create(identity_token: BaseIdentityToken) -> BaseIdentityProvider:
        """Create an identity provider from the given identity token.

        For Entra ID tokens, exchanges the user token for a Microsoft Graph
        token via the OBO flow when OBO is configured.

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
                graph_token = IdentityProviderFactory._get_graph_token(identity_token)
                return ExtraIDIdentityProvider(identity_token=identity_token, graph_token=graph_token)
            case IdenityProviderEnum.GOOGLE_IDENTITY.value:
                return IdentityProviderFactory._create_google_provider(identity_token)
            case IdenityProviderEnum.AWS_COGNITO.value:
                return IdentityProviderFactory._create_aws_cognito_provider(identity_token)
            case IdenityProviderEnum.LDAP.value:
                return IdentityProviderFactory._create_ldap_provider(identity_token)
            case IdenityProviderEnum.KERBEROS.value:
                return IdentityProviderFactory._create_kerberos_provider(identity_token)
            case IdenityProviderEnum.SAML.value:
                return SAMLIdentityProvider(identity_token=identity_token)
            case IdenityProviderEnum.OKTA.value:
                return IdentityProviderFactory._create_okta_provider(identity_token)
            case IdenityProviderEnum.OIDC.value:
                return IdentityProviderFactory._create_oidc_provider(identity_token)

        raise ValueError(f"Unsupported identity provider for: {identity_token.get_identity_provider()}")

    @staticmethod
    def _get_graph_token(identity_token: BaseIdentityToken) -> str | None:
        """Exchange the user token for a Graph token via OBO if configured.

        Args:
            identity_token: The user's verified identity token.

        Returns:
            Graph access token, or None if OBO is not configured.
        """
        from unifiedui.core.config import settings

        if not settings.identity_client_secret or not settings.identity_tenant_id:
            logger.debug(
                "OBO not configured (missing client_secret or tenant_id), using token directly for Graph calls"
            )
            return None

        try:
            from unifiedui.core.identity.obo_token_exchange import get_obo_client

            obo_client = get_obo_client()
            return obo_client.exchange_for_graph_token(identity_token.token)
        except ValueError as e:
            logger.error("OBO token exchange failed: %s", e)
            raise

    @staticmethod
    def _create_google_provider(identity_token: BaseIdentityToken) -> GoogleIdentityProvider:
        """Create a Google Workspace identity provider.

        Args:
            identity_token: The user's verified Google identity token.

        Returns:
            Configured GoogleIdentityProvider instance.
        """
        from unifiedui.core.config import settings

        return GoogleIdentityProvider(
            identity_token=identity_token,
            service_account_token=settings.google_service_account_token,
        )

    @staticmethod
    def _create_aws_cognito_provider(identity_token: BaseIdentityToken) -> AWSCognitoIdentityProvider:
        """Create an AWS Cognito identity provider.

        Args:
            identity_token: The user's verified Cognito identity token.

        Returns:
            Configured AWSCognitoIdentityProvider instance.
        """
        from unifiedui.core.config import settings

        if not settings.aws_cognito_region or not settings.aws_cognito_user_pool_id:
            raise ValueError(
                "AWS_COGNITO_REGION and AWS_COGNITO_USER_POOL_ID are required for AWS Cognito identity provider"
            )

        return AWSCognitoIdentityProvider(
            identity_token=identity_token,
            aws_region=settings.aws_cognito_region,
            user_pool_id=settings.aws_cognito_user_pool_id,
            aws_access_key_id=settings.aws_cognito_access_key_id,
            aws_secret_access_key=settings.aws_cognito_secret_access_key,
        )

    @staticmethod
    def _create_ldap_provider(identity_token: BaseIdentityToken) -> LDAPIdentityProvider:
        """Create an LDAP identity provider.

        Args:
            identity_token: The user's verified LDAP identity token.

        Returns:
            Configured LDAPIdentityProvider instance.
        """
        from unifiedui.core.config import settings

        if not settings.ldap_server_url:
            raise ValueError("LDAP_SERVER_URL is required for LDAP identity provider")

        return LDAPIdentityProvider(
            identity_token=identity_token,
            server_url=settings.ldap_server_url,
            bind_dn=settings.ldap_bind_dn,
            bind_password=settings.ldap_bind_password,
            base_dn=settings.ldap_base_dn or "",
            user_search_filter=settings.ldap_user_search_filter,
            group_search_filter=settings.ldap_group_search_filter,
            use_ssl=settings.ldap_use_ssl,
        )

    @staticmethod
    def _create_kerberos_provider(identity_token: BaseIdentityToken) -> KerberosIdentityProvider:
        """Create a Kerberos identity provider.

        Args:
            identity_token: The user's verified Kerberos identity token.

        Returns:
            Configured KerberosIdentityProvider instance.
        """
        from unifiedui.core.config import settings

        return KerberosIdentityProvider(
            identity_token=identity_token,
            ldap_url=settings.kerberos_ldap_url,
            ldap_base_dn=settings.kerberos_ldap_base_dn or "",
            realm=settings.kerberos_realm or "",
        )

    @staticmethod
    def _create_okta_provider(identity_token: BaseIdentityToken) -> OktaIdentityProvider:
        """Create an Okta identity provider.

        Args:
            identity_token: The user's verified Okta identity token.

        Returns:
            Configured OktaIdentityProvider instance.
        """
        from unifiedui.core.config import settings

        if not settings.okta_domain:
            raise ValueError("OKTA_DOMAIN is required for Okta identity provider")

        return OktaIdentityProvider(
            identity_token=identity_token,
            okta_domain=settings.okta_domain,
            api_token=settings.okta_api_token,
        )

    @staticmethod
    def _create_oidc_provider(identity_token: BaseIdentityToken) -> OIDCIdentityProvider:
        """Create a generic OIDC identity provider.

        Args:
            identity_token: The user's verified OIDC identity token.

        Returns:
            Configured OIDCIdentityProvider instance.
        """
        from unifiedui.core.config import settings

        return OIDCIdentityProvider(
            identity_token=identity_token,
            userinfo_url=settings.oidc_userinfo_url,
        )


_google_verifier_instance: JWKSTokenVerifier | None = None
_cognito_verifier_instances: dict[str, JWKSTokenVerifier] = {}
_okta_verifier_instances: dict[str, JWKSTokenVerifier] = {}
_oidc_verifier_instance: JWKSTokenVerifier | None = None


def _get_google_token_verifier() -> JWKSTokenVerifier:
    """Get or create a singleton Google JWKS token verifier.

    Returns:
        Configured JWKSTokenVerifier for Google tokens.
    """
    global _google_verifier_instance
    if _google_verifier_instance is None:
        from unifiedui.core.config import settings

        _google_verifier_instance = JWKSTokenVerifier(
            jwks_url="https://www.googleapis.com/oauth2/v3/certs",
            algorithms=["RS256"],
            audience=settings.google_client_id,
        )
    return _google_verifier_instance


def _get_cognito_token_verifier(issuer_url: str) -> JWKSTokenVerifier:
    """Get or create a JWKS token verifier for a specific Cognito User Pool.

    Args:
        issuer_url: The Cognito issuer URL (https://cognito-idp.{region}.amazonaws.com/{pool_id}).

    Returns:
        Configured JWKSTokenVerifier for the Cognito User Pool.
    """
    global _cognito_verifier_instances
    if issuer_url not in _cognito_verifier_instances:
        from unifiedui.core.config import settings

        jwks_url = f"{issuer_url}/.well-known/jwks.json"
        _cognito_verifier_instances[issuer_url] = JWKSTokenVerifier(
            jwks_url=jwks_url,
            algorithms=["RS256"],
            audience=settings.aws_cognito_client_id,
        )
    return _cognito_verifier_instances[issuer_url]


def reset_google_token_verifier() -> None:
    """Reset the singleton Google token verifier (for testing)."""
    global _google_verifier_instance
    _google_verifier_instance = None


def reset_cognito_token_verifiers() -> None:
    """Reset all Cognito token verifiers (for testing)."""
    global _cognito_verifier_instances
    _cognito_verifier_instances = {}


def _get_okta_token_verifier(issuer_url: str) -> JWKSTokenVerifier:
    """Get or create a JWKS token verifier for a specific Okta org.

    Args:
        issuer_url: The Okta issuer URL.

    Returns:
        Configured JWKSTokenVerifier for the Okta org.
    """
    global _okta_verifier_instances
    if issuer_url not in _okta_verifier_instances:
        from unifiedui.core.config import settings

        jwks_url = f"{issuer_url}/v1/keys"
        _okta_verifier_instances[issuer_url] = JWKSTokenVerifier(
            jwks_url=jwks_url,
            algorithms=["RS256"],
            audience=settings.okta_client_id,
        )
    return _okta_verifier_instances[issuer_url]


def _get_oidc_token_verifier() -> JWKSTokenVerifier:
    """Get or create a singleton generic OIDC JWKS token verifier.

    Returns:
        Configured JWKSTokenVerifier for the OIDC provider.
    """
    global _oidc_verifier_instance
    if _oidc_verifier_instance is None:
        from unifiedui.core.config import settings

        jwks_url = settings.oidc_jwks_url
        if not jwks_url and settings.oidc_issuer_url:
            jwks_url = f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/jwks.json"

        if not jwks_url:
            raise ValueError("OIDC_JWKS_URL or OIDC_ISSUER_URL is required for OIDC token verification")

        _oidc_verifier_instance = JWKSTokenVerifier(
            jwks_url=jwks_url,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
        )
    return _oidc_verifier_instance


def reset_okta_token_verifiers() -> None:
    """Reset all Okta token verifiers (for testing)."""
    global _okta_verifier_instances
    _okta_verifier_instances = {}


def reset_oidc_token_verifier() -> None:
    """Reset the singleton OIDC token verifier (for testing)."""
    global _oidc_verifier_instance
    _oidc_verifier_instance = None
