"""Generic OpenID Connect identity provider."""

from unifiedui.identity.oidc.provider import OIDCIdentityProvider
from unifiedui.identity.oidc.token import OIDCIdentityTokenSerializer

__all__ = ["OIDCIdentityProvider", "OIDCIdentityTokenSerializer"]
