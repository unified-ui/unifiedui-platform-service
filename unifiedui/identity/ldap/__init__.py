"""LDAP identity provider."""

from unifiedui.identity.ldap.provider import LDAPIdentityProvider
from unifiedui.identity.ldap.token import LDAPIdentityTokenSerializer

__all__ = ["LDAPIdentityProvider", "LDAPIdentityTokenSerializer"]
