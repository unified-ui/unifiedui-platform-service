"""SAML 2.0 identity token serializer for assertion attributes extraction."""

from unifiedui.core.identity.enums import IdenityProviderEnum
from unifiedui.core.identity.providers import BaseIdentityToken


class SAMLIdentityTokenSerializer(BaseIdentityToken):
    """Extracts user identity from SAML-issued JWT tokens.

    SAML assertions are typically converted to JWT by an intermediary
    authentication gateway or service. The claims map to SAML assertion
    attributes based on the configured attribute mapping.
    """

    def __init__(
        self,
        token: str,
        deserialized_token: dict,
        attribute_map_id: str = "uid",
        attribute_map_email: str = "email",
        attribute_map_display_name: str = "displayName",
        attribute_map_first_name: str = "firstName",
        attribute_map_last_name: str = "lastName",
    ):
        """Initialize with raw token and decoded claims.

        Args:
            token: Raw JWT token string.
            deserialized_token: Decoded JWT claims dictionary.
            attribute_map_id: Claim key for user ID.
            attribute_map_email: Claim key for email.
            attribute_map_display_name: Claim key for display name.
            attribute_map_first_name: Claim key for first name.
            attribute_map_last_name: Claim key for last name.
        """
        self._identity_provider = IdenityProviderEnum.SAML.value
        self._attr_id = attribute_map_id
        self._attr_email = attribute_map_email
        self._attr_display_name = attribute_map_display_name
        self._attr_first_name = attribute_map_first_name
        self._attr_last_name = attribute_map_last_name
        super().__init__(token, deserialized_token)

    def get_token(self) -> str:
        """Return the raw JWT token string."""
        return self.token

    def get_deserialized_token(self) -> dict:
        """Return the decoded claims dictionary."""
        return self.deserialized_token

    def get_id(self) -> str:
        """Return the SAML user ID from configured attribute."""
        return self.deserialized_token.get(self._attr_id, self.deserialized_token.get("sub", ""))

    def get_identity_tenant_id(self) -> str:
        """Return the SAML issuer as tenant ID."""
        return self.deserialized_token.get("iss", "")

    def get_display_name(self) -> str:
        """Return the user display name from configured attribute."""
        return self.deserialized_token.get(self._attr_display_name, self.deserialized_token.get("name", ""))

    def get_principal_name(self) -> str:
        """Return the user principal name (email or nameID)."""
        return self.deserialized_token.get(self._attr_email, self.deserialized_token.get("nameID", ""))

    def get_firstname(self) -> str:
        """Return the user's first name from configured attribute."""
        first_name = self.deserialized_token.get(self._attr_first_name, self.deserialized_token.get("given_name", ""))
        if first_name:
            return first_name

        display_name = self.get_display_name()
        if display_name and " " in display_name:
            return display_name.split(" ", 1)[0]

        return ""

    def get_lastname(self) -> str:
        """Return the user's last name from configured attribute."""
        last_name = self.deserialized_token.get(self._attr_last_name, self.deserialized_token.get("family_name", ""))
        if last_name:
            return last_name

        display_name = self.get_display_name()
        if display_name and " " in display_name:
            return display_name.split(" ", 1)[1]

        return ""

    def get_mail(self) -> str:
        """Return the user's email address from configured attribute."""
        return self.deserialized_token.get(self._attr_email, self.deserialized_token.get("email", ""))

    def get_identity_provider(self) -> str:
        """Return the identity provider enum value."""
        return self._identity_provider
