"""LDAP identity token serializer for JWT claims extraction."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken


class LDAPIdentityTokenSerializer(BaseIdentityToken):
    """Extracts user identity from LDAP-issued JWT tokens.

    Expected claims: sub, dn, cn, sn, givenName, mail, uid, o (organization).
    """

    def __init__(self, token: str, deserialized_token: dict):
        """Initialize with raw token and decoded claims.

        Args:
            token: Raw JWT token string.
            deserialized_token: Decoded JWT claims dictionary.
        """
        self._identity_provider = IdenityProviderEnum.LDAP.value
        super().__init__(token, deserialized_token)

    def get_token(self) -> str:
        """Return the raw JWT token string."""
        return self.token

    def get_deserialized_token(self) -> dict:
        """Return the decoded claims dictionary."""
        return self.deserialized_token

    def get_id(self) -> str:
        """Return the LDAP user ID (sub or uid claim)."""
        return self.deserialized_token.get("sub", self.deserialized_token.get("uid", ""))

    def get_identity_tenant_id(self) -> str:
        """Return the LDAP organization or base DN as tenant ID."""
        return self.deserialized_token.get("o", self.deserialized_token.get("dn", ""))

    def get_display_name(self) -> str:
        """Return the user display name (cn claim)."""
        return self.deserialized_token.get("cn", self.deserialized_token.get("name", ""))

    def get_principal_name(self) -> str:
        """Return the user principal name (uid or mail claim)."""
        return self.deserialized_token.get("uid", self.deserialized_token.get("mail", ""))

    def get_firstname(self) -> str:
        """Return the user's given name."""
        given_name = self.deserialized_token.get("givenName", "")
        if given_name:
            return given_name

        cn = self.deserialized_token.get("cn", "")
        if cn and " " in cn:
            return cn.split(" ", 1)[0]

        return ""

    def get_lastname(self) -> str:
        """Return the user's surname (sn claim)."""
        sn = self.deserialized_token.get("sn", "")
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
