"""Zitadel-specific OIDC identity provider with Management API user search.

Extends the generic OIDC provider with Zitadel Management API support
for searching users and groups across the entire organization directory.
Uses a service user PAT (Personal Access Token) for admin-level access.
"""

import requests

from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.identity.oidc.provider import OIDCIdentityProvider
from unifiedui.logger import get_logger
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery

logger = get_logger(__name__)


class ZitadelIdentityProvider(OIDCIdentityProvider):
    """Zitadel OIDC identity provider with Management API user/group search."""

    def __init__(
        self,
        identity_token: BaseIdentityToken,
        userinfo_url: str | None = None,
        extra_headers: dict[str, str] | None = None,
        management_api_url: str | None = None,
        service_token: str | None = None,
    ):
        """Initialize the Zitadel identity provider.

        Args:
            identity_token: The user's verified identity token.
            userinfo_url: OIDC UserInfo endpoint URL.
            extra_headers: Additional HTTP headers (e.g. Host override for Docker).
            management_api_url: Zitadel Management API base URL.
            service_token: Zitadel service user PAT for Management API calls.
        """
        super().__init__(identity_token, userinfo_url, extra_headers)
        self._management_api_url = management_api_url
        self._service_token = service_token

    def _get_management_headers(self) -> dict[str, str]:
        """Build authorization headers for Zitadel Management API calls."""
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "Content-Type": "application/json",
        }
        headers.update(self._extra_headers)
        return headers

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Search users via Zitadel Management API.

        Falls back to the generic OIDC behavior (current user only)
        if Management API is not configured.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (user list, None).
        """
        if not self._management_api_url or not self._service_token:
            return super().get_users(query)

        query = query or APIFilterQuery()
        url = f"{self._management_api_url}/users/_search"
        headers = self._get_management_headers()

        payload: dict = {
            "limit": query.top,
            "queries": [{"typeQuery": {"type": "TYPE_HUMAN"}}],
        }
        if query.search:
            payload["queries"].append(
                {
                    "displayNameQuery": {
                        "displayName": query.search,
                        "method": "TEXT_QUERY_METHOD_CONTAINS_IGNORE_CASE",
                    },
                },
            )

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            users = self._parse_zitadel_users(data)
            return users, None
        except requests.RequestException as exc:
            logger.warning("Zitadel Management API user search failed: %s", exc)
            return super().get_users(query)

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get user by ID via Zitadel Management API.

        Falls back to the generic OIDC behavior if Management API
        is not configured.

        Args:
            user_id: User identifier.

        Returns:
            User identity response.

        Raises:
            requests.RequestException: If the user is not found.
        """
        if not self._management_api_url or not self._service_token:
            return super().get_user_by_id(user_id)

        url = f"{self._management_api_url}/users/{user_id}"
        headers = self._get_management_headers()

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            user_data = data.get("user", data)
            return self._parse_single_zitadel_user(user_data)
        except requests.RequestException as exc:
            logger.warning("Zitadel Management API get user failed: %s", exc)
            return super().get_user_by_id(user_id)

    def get_security_groups(
        self, query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get groups — delegates to token claims (Zitadel uses project roles).

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, None).
        """
        return super().get_security_groups(query)

    def _parse_zitadel_users(self, data: dict) -> list[IdentityUserResponse]:
        """Parse Zitadel Management API users search response.

        Args:
            data: Raw JSON response from /users/_search.

        Returns:
            List of parsed user identity responses.
        """
        users = []
        for item in data.get("result", []):
            user = self._parse_single_zitadel_user(item)
            users.append(user)
        return users

    def _parse_single_zitadel_user(self, item: dict) -> IdentityUserResponse:
        """Parse a single Zitadel user object.

        Args:
            item: Single user object from Zitadel API.

        Returns:
            Parsed user identity response.
        """
        human = item.get("human", {})
        profile = human.get("profile", {})
        email_data = human.get("email", {})

        display_name = profile.get("displayName", "")
        first_name = profile.get("firstName", "")
        last_name = profile.get("lastName", "")
        email = email_data.get("email", "")
        preferred_username = item.get("preferredLoginName", email)

        return IdentityUserResponse(
            id=item.get("userId", item.get("id", "")),
            identity_provider=self.identity_token.get_identity_provider(),
            display_name=display_name,
            principal_name=preferred_username,
            mail=email,
            firstname=first_name,
            lastname=last_name,
        )
