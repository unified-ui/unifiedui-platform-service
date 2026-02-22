"""SAML 2.0 identity provider.

Provides user and group lookups. Since SAML itself does not define a
standard user/group directory API, this provider returns identity
information extracted from the SAML assertion attributes.
For directory lookups, an optional SCIM endpoint can be configured.
"""

import requests

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class SAMLIdentityProvider(BaseIdentityProvider):
    """SAML 2.0 identity provider.

    Extracts identity from SAML assertions. Directory lookups return
    data from the authenticated assertion since SAML does not provide
    a standard directory API.
    """

    def __init__(
        self,
        identity_token: BaseIdentityToken,
    ):
        """Initialize the SAML identity provider.

        Args:
            identity_token: The user's verified identity token.
        """
        super().__init__(identity_token)

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get groups from the SAML assertion.

        Args:
            query: Optional filter/pagination query.

        Returns:
            List of group responses from assertion groups claim.
        """
        groups_claim = self.identity_token.get_deserialized_token().get("groups", [])
        if not isinstance(groups_claim, list):
            return []

        groups = []
        for group in groups_claim:
            if isinstance(group, str):
                groups.append(IdentityGroupResponse(id=group, display_name=group))
            elif isinstance(group, dict):
                groups.append(
                    IdentityGroupResponse(
                        id=group.get("id", group.get("value", "")),
                        display_name=group.get("display_name", group.get("name", "")),
                    )
                )

        return groups

    def get_security_groups(
        self, query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get all groups known from the SAML assertion.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, None).
        """
        return self.get_current_user_security_groups(query), None

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Get users — returns only the current user from assertion.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (single user list, None).
        """
        current_user = IdentityUserResponse(
            id=self.identity_token.get_id(),
            identity_provider=self.identity_token.get_identity_provider(),
            display_name=self.identity_token.get_display_name(),
            principal_name=self.identity_token.get_principal_name(),
            mail=self.identity_token.get_mail(),
            firstname=self.identity_token.get_firstname(),
            lastname=self.identity_token.get_lastname(),
        )
        return [current_user], None

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get user by ID — only the current user is available.

        Args:
            user_id: User identifier.

        Returns:
            User identity response.

        Raises:
            requests.RequestException: If the user ID doesn't match the current user.
        """
        if user_id != self.identity_token.get_id():
            raise requests.RequestException(f"SAML user not found: {user_id}")

        return IdentityUserResponse(
            id=self.identity_token.get_id(),
            identity_provider=self.identity_token.get_identity_provider(),
            display_name=self.identity_token.get_display_name(),
            principal_name=self.identity_token.get_principal_name(),
            mail=self.identity_token.get_mail(),
            firstname=self.identity_token.get_firstname(),
            lastname=self.identity_token.get_lastname(),
        )

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get group by ID from assertion groups.

        Args:
            group_id: Group identifier.

        Returns:
            Group identity response.

        Raises:
            requests.RequestException: If the group is not in the assertion.
        """
        groups = self.get_current_user_security_groups()
        for group in groups:
            if group.id == group_id:
                return group

        raise requests.RequestException(f"SAML group not found: {group_id}")
