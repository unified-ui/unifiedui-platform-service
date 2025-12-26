import requests

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_client import APIJSONBearerClient
from unifiedui.utils.api_query import APIFilterQuery


class ExtraIDIdentityProvider(BaseIdentityProvider, APIJSONBearerClient):
    """Microsoft Entra ID (formerly Azure AD) identity provider implementation."""
    
    def __init__(self, identity_token: BaseIdentityToken):
        BaseIdentityProvider.__init__(self, identity_token)
        APIJSONBearerClient.__init__(self, base_url="https://graph.microsoft.com/v1.0")

    def get_current_user_security_groups(
        self,
        query: APIFilterQuery | None = None
    ) -> list[IdentityGroupResponse]:
        """
        Get security groups for the current authenticated user.
        
        Args:
            identity_token: User's identity token
            query: Query parameters (search, top, next_link)
            
        Returns:
            List of identity groups the user belongs to
        """
        query = query or APIFilterQuery()
        headers = self._get_headers(self.identity_token.token)
        
        if query.next_link:
            url = query.next_link
            params = {}
        else:
            url = self._url("/me/memberOf/microsoft.graph.group")
            params = {
                "$select": "displayName,id",
                "$top": query.top
            }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return self._parse_groups_response(response.json())

    def get_security_groups(
        self,
        query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """
        Get all security groups from the directory.
        
        Args:
            identity_token: User's identity token
            query: Query parameters (search, top, next_link)
            
        Returns:
            Tuple of (list of security groups, next_link)
        """
        query = query or APIFilterQuery()
        headers = self._get_headers(self.identity_token.token)
        
        if query.search:
            headers["ConsistencyLevel"] = "eventual"
        
        if query.next_link:
            url = query.next_link
            params = {}
        else:
            url = self._url("/groups")
            params = {
                "$select": "displayName,id",
                "$top": query.top,
                "$filter": "securityEnabled eq true"
            }
            if query.search:
                params["$search"] = f'"displayName:{query.search}"'
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        groups = self._parse_groups_response(data)
        next_link = data.get("@odata.nextLink")
        
        return groups, next_link

    def get_users(
        self,
        query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityUserResponse], str | None]:
        """
        Get users from the directory.
        
        Args:
            identity_token: User's identity token
            query: Query parameters (search, top, next_link)
            
        Returns:
            Tuple of (list of users, next_link)
        """
        query = query or APIFilterQuery()
        headers = self._get_headers(self.identity_token.token)
        
        if query.search:
            headers["ConsistencyLevel"] = "eventual"
        
        if query.next_link:
            url = query.next_link
            params = {}
        else:
            url = self._url("/users")
            params = {
                "$select": "displayName,id,userPrincipalName",
                "$top": query.top
            }
            if query.search:
                params["$search"] = f'"displayName:{query.search}" OR "userPrincipalName:{query.search}"'

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        users = self._parse_users_response(data)
        next_link = data.get("@odata.nextLink")
        
        return users, next_link

    def _parse_groups_response(self, data: dict) -> list[IdentityGroupResponse]:
        """Parse Microsoft Graph API groups response."""
        return [
            IdentityGroupResponse(
                id=item["id"],
                display_name=item["displayName"]
            )
            for item in data.get("value", [])
        ]

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """
        Get a specific user by ID.
        
        Args:
            user_id: The user ID to retrieve
            
        Returns:
            IdentityUserResponse with user details
        """
        headers = self._get_headers(self.identity_token.token)
        url = self._url(f"/users/{user_id}")
        params = {
            "$select": "displayName,id,userPrincipalName,givenName,surname,mail"
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        return IdentityUserResponse(
            id=data["id"],
            identity_provider=self.identity_token.get_identity_provider(),
            identity_tenant_id=self.identity_token.get_identity_tenant_id(),
            display_name=data.get("displayName", data.get("userPrincipalName", "")),
            firstname=data.get("givenName"),
            lastname=data.get("surname"),
            mail=data.get("mail"),
            user_principal_name=data.get("userPrincipalName")
        )

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """
        Get a specific group by ID.
        
        Args:
            group_id: The group ID to retrieve
            
        Returns:
            IdentityGroupResponse with group details
        """
        headers = self._get_headers(self.identity_token.token)
        url = self._url(f"/groups/{group_id}")
        params = {
            "$select": "displayName,id"
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        return IdentityGroupResponse(
            id=data["id"],
            display_name=data["displayName"]
        )

    def get_principal_name(self, principal_id: str, principal_type: str) -> str:
        """
        Get the principal name for a user or group.
        
        For users, returns userPrincipalName (e.g., user@domain.com).
        For groups, returns the display name.
        
        Args:
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER or IDENTITY_GROUP)
            
        Returns:
            The principal name string
        """
        if principal_type == "IDENTITY_USER":
            user = self.get_user_by_id(principal_id)
            # Prefer userPrincipalName, fallback to mail, then display_name
            return user.user_principal_name or user.mail or user.display_name
        else:  # IDENTITY_GROUP
            group = self.get_group_by_id(principal_id)
            return group.display_name

    def _parse_users_response(self, data: dict) -> list[IdentityUserResponse]:
        """Parse Microsoft Graph API users response."""
        return [
            IdentityUserResponse(
                id=item["id"],
                identity_provider=self.identity_token.get_identity_provider(),
                display_name=item.get("displayName", item.get("userPrincipalName", "")),
                user_principal_name=item.get("userPrincipalName")
            )
            for item in data.get("value", [])
        ]