import requests

from aihub.core.identity.base import BaseIdentityProvider, BaseIdentityToken
from aihub.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from aihub.utils.api_client import APIJSONBearerClient
from aihub.utils.api_query import APIFilterQuery


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

    def _parse_users_response(self, data: dict) -> list[IdentityUserResponse]:
        """Parse Microsoft Graph API users response."""
        return [
            IdentityUserResponse(
                id=item["id"],
                display_name=item.get("displayName", item.get("userPrincipalName", "")),
                user_principal_name=item.get("userPrincipalName")
            )
            for item in data.get("value", [])
        ]