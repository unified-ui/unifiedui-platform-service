"""Google Identity token serializer for JWT claims extraction."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken


class GoogleIdentityTokenSerializer(BaseIdentityToken):
    """Extracts user identity from Google-issued JWT tokens."""

    def __init__(self, token: str, deserialized_token: dict):
        """Initialize with raw token and decoded claims.

        Args:
            token: Raw JWT token string.
            deserialized_token: Decoded JWT claims dictionary.
        """
        self._identity_provider = IdenityProviderEnum.GOOGLE_IDENTITY.value
        super().__init__(token, deserialized_token)

    def get_token(self) -> str:
        """Return the raw JWT token string."""
        return self.token

    def get_deserialized_token(self) -> dict:
        """Return the decoded claims dictionary."""
        return self.deserialized_token

    def get_id(self) -> str:
        """Return the Google user ID (sub claim)."""
        return self.deserialized_token.get("sub", "")

    def get_identity_tenant_id(self) -> str:
        """Return the Google Workspace domain (hd claim)."""
        return self.deserialized_token.get("hd", "")

    def get_display_name(self) -> str:
        """Return the user display name."""
        return self.deserialized_token.get("name", "")

    def get_principal_name(self) -> str:
        """Return the user email as principal name."""
        return self.deserialized_token.get("email", "")

    def get_firstname(self) -> str:
        """Return the user's given name."""
        given_name = self.deserialized_token.get("given_name", "")
        if given_name:
            return given_name

        name = self.deserialized_token.get("name", "")
        if name and " " in name:
            return name.split(" ", 1)[0]

        return ""

    def get_lastname(self) -> str:
        """Return the user's family name."""
        family_name = self.deserialized_token.get("family_name", "")
        if family_name:
            return family_name

        name = self.deserialized_token.get("name", "")
        if name and " " in name:
            return name.split(" ", 1)[1]

        return ""

    def get_mail(self) -> str:
        """Return the user's email address."""
        return self.deserialized_token.get("email", "")

    def get_identity_provider(self) -> str:
        """Return the identity provider enum value."""
        return self._identity_provider
