"""Google Workspace / Cloud Identity provider using Admin SDK Directory API.

Provides user and group lookups via the Google Workspace Admin SDK.
Requires a service account with domain-wide delegation OR OAuth2 credentials
with admin directory scopes.
"""

import requests

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class GoogleIdentityProvider(BaseIdentityProvider):
    """Google Workspace identity provider using Admin SDK Directory API."""

    DIRECTORY_BASE_URL = "https://admin.googleapis.com/admin/directory/v1"

    def __init__(
        self,
        identity_token: BaseIdentityToken,
        service_account_token: str | None = None,
    ):
        """Initialize the Google identity provider.

        Args:
            identity_token: The user's verified identity token.
            service_account_token: Service account access token for Admin SDK calls.
                                   If None, falls back to identity_token for basic profile.
        """
        super().__init__(identity_token)
        self._api_token = service_account_token or identity_token.token

    def _get_headers(self) -> dict[str, str]:
        """Build authorization headers for Google API calls."""
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get groups the current user is a member of.

        Args:
            query: Optional filter/pagination query.

        Returns:
            List of group responses.
        """
        user_email = self.identity_token.get_mail()
        if not user_email:
            return []

        url = f"{self.DIRECTORY_BASE_URL}/groups"
        params: dict[str, str | int] = {"userKey": user_email}

        if query and query.top:
            params["maxResults"] = query.top

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return []

        data = response.json()
        return self._parse_groups_response(data)

    def get_security_groups(
        self, query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get all groups in the Google Workspace domain.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, next_page_token).
        """
        query = query or APIFilterQuery()
        domain = self.identity_token.get_identity_tenant_id()

        url = f"{self.DIRECTORY_BASE_URL}/groups"
        params: dict[str, str | int] = {}

        if domain:
            params["domain"] = domain
        if query.top:
            params["maxResults"] = query.top
        if query.search:
            params["query"] = f"name:{query.search}* email:{query.search}*"
        if query.next_link:
            params["pageToken"] = query.next_link

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return [], None

        data = response.json()
        groups = self._parse_groups_response(data)
        next_page_token = data.get("nextPageToken")
        return groups, next_page_token

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Get users in the Google Workspace domain.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (users, next_page_token).
        """
        query = query or APIFilterQuery()
        domain = self.identity_token.get_identity_tenant_id()

        url = f"{self.DIRECTORY_BASE_URL}/users"
        params: dict[str, str | int] = {}

        if domain:
            params["domain"] = domain
        if query.top:
            params["maxResults"] = query.top
        if query.search:
            params["query"] = query.search
        if query.next_link:
            params["pageToken"] = query.next_link

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return [], None

        data = response.json()
        users = self._parse_users_response(data)
        next_page_token = data.get("nextPageToken")
        return users, next_page_token

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get a single user by ID or email.

        Args:
            user_id: Google user ID or email address.

        Returns:
            User identity response.
        """
        url = f"{self.DIRECTORY_BASE_URL}/users/{user_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        return IdentityUserResponse(
            id=data.get("id", user_id),
            identity_provider=self.identity_token.get_identity_provider(),
            identity_tenant_id=self.identity_token.get_identity_tenant_id(),
            display_name=data.get("name", {}).get("fullName", ""),
            firstname=data.get("name", {}).get("givenName"),
            lastname=data.get("name", {}).get("familyName"),
            mail=data.get("primaryEmail"),
            principal_name=data.get("primaryEmail"),
        )

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get a single group by ID or email.

        Args:
            group_id: Google group ID or email address.

        Returns:
            Group identity response.
        """
        url = f"{self.DIRECTORY_BASE_URL}/groups/{group_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        return IdentityGroupResponse(
            id=data.get("id", group_id),
            display_name=data.get("name", group_id),
        )

    def _parse_groups_response(self, data: dict) -> list[IdentityGroupResponse]:
        """Parse Google Directory API groups response."""
        return [
            IdentityGroupResponse(
                id=group.get("id", group.get("email", "")),
                display_name=group.get("name", group.get("email", "")),
            )
            for group in data.get("groups", [])
        ]

    def _parse_users_response(self, data: dict) -> list[IdentityUserResponse]:
        """Parse Google Directory API users response."""
        return [
            IdentityUserResponse(
                id=user.get("id", ""),
                identity_provider=self.identity_token.get_identity_provider(),
                display_name=user.get("name", {}).get("fullName", user.get("primaryEmail", "")),
                principal_name=user.get("primaryEmail"),
            )
            for user in data.get("users", [])
        ]
