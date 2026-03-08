"""Kerberos identity token serializer for JWT claims extraction."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken


class KerberosIdentityTokenSerializer(BaseIdentityToken):
    """Extracts user identity from Kerberos-issued JWT tokens.

    Expected claims: sub, principal, realm, cn, givenName, sn, mail.
    Kerberos tokens are typically exchanged at the gateway level (SPNEGO)
    and converted to JWT by an intermediary authentication service.
    """

    def __init__(self, token: str, deserialized_token: dict):
        """Initialize with raw token and decoded claims.

        Args:
            token: Raw JWT token string.
            deserialized_token: Decoded JWT claims dictionary.
        """
        self._identity_provider = IdenityProviderEnum.KERBEROS.value
        super().__init__(token, deserialized_token)

    def get_token(self) -> str:
        """Return the raw JWT token string."""
        return self.token

    def get_deserialized_token(self) -> dict:
        """Return the decoded claims dictionary."""
        return self.deserialized_token

    def get_id(self) -> str:
        """Return the Kerberos user ID (sub or principal claim)."""
        return self.deserialized_token.get("sub", self.deserialized_token.get("principal", ""))

    def get_identity_tenant_id(self) -> str:
        """Return the Kerberos realm as tenant ID."""
        return self.deserialized_token.get("realm", "")

    def get_display_name(self) -> str:
        """Return the user display name."""
        return self.deserialized_token.get("cn", self.deserialized_token.get("name", ""))

    def get_principal_name(self) -> str:
        """Return the Kerberos principal name (user@REALM)."""
        return self.deserialized_token.get("principal", self.deserialized_token.get("sub", ""))

    def get_firstname(self) -> str:
        """Return the user's given name."""
        given_name = self.deserialized_token.get("givenName", self.deserialized_token.get("given_name", ""))
        if given_name:
            return given_name

        cn = self.deserialized_token.get("cn", "")
        if cn and " " in cn:
            return cn.split(" ", 1)[0]

        return ""

    def get_lastname(self) -> str:
        """Return the user's surname."""
        sn = self.deserialized_token.get("sn", self.deserialized_token.get("family_name", ""))
        if sn:
            return sn

        cn = self.deserialized_token.get("cn", "")
        if cn and " " in cn:
            return cn.split(" ", 1)[1]

        return ""

    def get_mail(self) -> str:
        """Return the user's email address."""
        return self.deserialized_token.get("mail", self.deserialized_token.get("email", ""))

    def get_identity_provider(self) -> str:
        """Return the identity provider enum value."""
        return self._identity_provider
