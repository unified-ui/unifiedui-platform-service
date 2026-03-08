"""Okta identity provider."""

from unifiedui.identity.okta.provider import OktaIdentityProvider
from unifiedui.identity.okta.token import OktaIdentityTokenSerializer

__all__ = ["OktaIdentityProvider", "OktaIdentityTokenSerializer"]
