"""Generic OpenID Connect identity provider using UserInfo endpoint.

Provides user lookups via the standard OIDC UserInfo endpoint.
Group information is extracted from token claims (groups or roles).
Works with any OIDC-compliant identity provider.
"""

import requests

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class OIDCIdentityProvider(BaseIdentityProvider):
    """Generic OIDC identity provider using standard OIDC endpoints."""

    def __init__(
        self,
        identity_token: BaseIdentityToken,
        userinfo_url: str | None = None,
    ):
        """Initialize the Generic OIDC identity provider.

        Args:
            identity_token: The user's verified identity token.
            userinfo_url: OIDC UserInfo endpoint URL.
        """
        super().__init__(identity_token)
        self._userinfo_url = userinfo_url

    def _get_headers(self) -> dict[str, str]:
        """Build authorization headers for OIDC API calls."""
        return {
            "Authorization": f"Bearer {self.identity_token.token}",
            "Content-Type": "application/json",
        }

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get groups from token claims.

        Args:
            query: Optional filter/pagination query.

        Returns:
            List of group responses from token groups/roles claims.
        """
        claims = self.identity_token.deserialized_token
        groups_claim = claims.get("groups", claims.get("roles", []))
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
        """Get all groups known from token claims.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, None).
        """
        return self.get_current_user_security_groups(query), None

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Get users — returns the current user from UserInfo or token.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (single user list, None).
        """
        user = self._get_current_user_info()
        return [user], None

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get user by ID — returns current user if ID matches.

        Args:
            user_id: User identifier.

        Returns:
            User identity response.

        Raises:
            requests.RequestException: If the user ID doesn't match.
        """
        current_user = self._get_current_user_info()
        if user_id != current_user.id:
            raise requests.RequestException(f"OIDC user not found: {user_id}")
        return current_user

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get group by ID from token claims.

        Args:
            group_id: Group identifier.

        Returns:
            Group identity response.

        Raises:
            requests.RequestException: If the group is not in the claims.
        """
        groups = self.get_current_user_security_groups()
        for group in groups:
            if group.id == group_id:
                return group

        raise requests.RequestException(f"OIDC group not found: {group_id}")

    def _get_current_user_info(self) -> IdentityUserResponse:
        """Get current user info from UserInfo endpoint or token claims.

        Returns:
            User identity response.
        """
        if self._userinfo_url:
            try:
                response = requests.get(self._userinfo_url, headers=self._get_headers(), timeout=30)
                response.raise_for_status()
                data = response.json()
                return IdentityUserResponse(
                    id=data.get("sub", self.identity_token.get_id()),
                    identity_provider=self.identity_token.get_identity_provider(),
                    display_name=data.get("name", ""),
                    principal_name=data.get("preferred_username", data.get("email")),
                    mail=data.get("email"),
                    firstname=data.get("given_name"),
                    lastname=data.get("family_name"),
                )
            except requests.RequestException:
                pass

        return IdentityUserResponse(
            id=self.identity_token.get_id(),
            identity_provider=self.identity_token.get_identity_provider(),
            display_name=self.identity_token.get_display_name(),
            principal_name=self.identity_token.get_principal_name(),
            mail=self.identity_token.get_mail(),
            firstname=self.identity_token.get_firstname(),
            lastname=self.identity_token.get_lastname(),
        )
