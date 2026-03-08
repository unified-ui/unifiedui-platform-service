"""SAML 2.0 identity provider."""

from unifiedui.identity.saml.provider import SAMLIdentityProvider
from unifiedui.identity.saml.token import SAMLIdentityTokenSerializer

__all__ = ["SAMLIdentityProvider", "SAMLIdentityTokenSerializer"]
