"""Okta identity provider using Okta Management API.

Provides user and group lookups via the Okta API v1.
Requires an Okta domain and API token for administrative operations.
"""

import requests

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class OktaIdentityProvider(BaseIdentityProvider):
    """Okta identity provider using the Okta Management API v1."""

    def __init__(
        self,
        identity_token: BaseIdentityToken,
        okta_domain: str,
        api_token: str | None = None,
    ):
        """Initialize the Okta identity provider.

        Args:
            identity_token: The user's verified identity token.
            okta_domain: Okta org domain (e.g. dev-12345.okta.com).
            api_token: Okta API token for admin operations.
        """
        super().__init__(identity_token)
        self._base_url = f"https://{okta_domain}/api/v1"
        self._api_token = api_token

    def _get_headers(self) -> dict[str, str]:
        """Build authorization headers for Okta API calls."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_token:
            headers["Authorization"] = f"SSWS {self._api_token}"
        return headers

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get groups the current Okta user is a member of.

        Args:
            query: Optional filter/pagination query.

        Returns:
            List of group responses.
        """
        user_id = self.identity_token.get_id()
        if not user_id:
            return []

        url = f"{self._base_url}/users/{user_id}/groups"

        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return []

        data = response.json()
        return [
            IdentityGroupResponse(
                id=group.get("id", ""),
                display_name=group.get("profile", {}).get("name", ""),
            )
            for group in data
            if isinstance(group, dict)
        ]

    def get_security_groups(
        self, query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get all groups in the Okta organization.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, next_cursor).
        """
        query = query or APIFilterQuery()
        url = f"{self._base_url}/groups"
        params: dict[str, str | int] = {}

        if query.top:
            params["limit"] = query.top
        if query.search:
            params["q"] = query.search
        if query.next_link:
            url = query.next_link

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return [], None

        data = response.json()
        groups = [
            IdentityGroupResponse(
                id=group.get("id", ""),
                display_name=group.get("profile", {}).get("name", ""),
            )
            for group in data
            if isinstance(group, dict)
        ]

        next_link = self._extract_next_link(response)
        return groups, next_link

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Get users in the Okta organization.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (users, next_cursor).
        """
        query = query or APIFilterQuery()
        url = f"{self._base_url}/users"
        params: dict[str, str | int] = {}

        if query.top:
            params["limit"] = query.top
        if query.search:
            params["q"] = query.search
        if query.next_link:
            url = query.next_link

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return [], None

        data = response.json()
        users = self._parse_users(data)
        next_link = self._extract_next_link(response)
        return users, next_link

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get a single user by Okta user ID or login.

        Args:
            user_id: Okta user ID or login email.

        Returns:
            User identity response.
        """
        url = f"{self._base_url}/users/{user_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        profile = data.get("profile", {})

        return IdentityUserResponse(
            id=data.get("id", user_id),
            identity_provider=self.identity_token.get_identity_provider(),
            display_name=f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
            principal_name=profile.get("login"),
            mail=profile.get("email"),
            firstname=profile.get("firstName"),
            lastname=profile.get("lastName"),
        )

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get a single group by Okta group ID.

        Args:
            group_id: Okta group ID.

        Returns:
            Group identity response.
        """
        url = f"{self._base_url}/groups/{group_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        return IdentityGroupResponse(
            id=data.get("id", group_id),
            display_name=data.get("profile", {}).get("name", group_id),
        )

    def _parse_users(self, data: list) -> list[IdentityUserResponse]:
        """Parse Okta users response list."""
        return [
            IdentityUserResponse(
                id=user.get("id", ""),
                identity_provider=self.identity_token.get_identity_provider(),
                display_name=f"{user.get('profile', {}).get('firstName', '')} {user.get('profile', {}).get('lastName', '')}".strip(),
                principal_name=user.get("profile", {}).get("login"),
                mail=user.get("profile", {}).get("email"),
            )
            for user in data
            if isinstance(user, dict)
        ]

    @staticmethod
    def _extract_next_link(response: requests.Response) -> str | None:
        """Extract next page link from Okta Link headers."""
        link_header = response.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url_part = part.split(";")[0].strip()
                if url_part.startswith("<") and url_part.endswith(">"):
                    return url_part[1:-1]
        return None
