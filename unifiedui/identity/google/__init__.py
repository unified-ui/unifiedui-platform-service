"""Google Workspace / Cloud Identity provider."""

from unifiedui.identity.google.provider import GoogleIdentityProvider
from unifiedui.identity.google.token import GoogleIdentityTokenSerializer

__all__ = ["GoogleIdentityProvider", "GoogleIdentityTokenSerializer"]
