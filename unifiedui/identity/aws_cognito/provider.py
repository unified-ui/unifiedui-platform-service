"""AWS Cognito identity provider using Cognito User Pools API.

Provides user and group lookups via the AWS Cognito Identity Provider API (boto3).
Requires AWS credentials (access key / secret key) with cognito-idp permissions,
or an IAM role with the necessary permissions.
"""

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class AWSCognitoIdentityProvider(BaseIdentityProvider):
    """AWS Cognito identity provider using Cognito User Pools API via REST."""

    def __init__(
        self,
        identity_token: BaseIdentityToken,
        aws_region: str,
        user_pool_id: str,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ):
        """Initialize the AWS Cognito identity provider.

        Args:
            identity_token: The user's verified identity token.
            aws_region: AWS region of the Cognito User Pool.
            user_pool_id: Cognito User Pool ID.
            aws_access_key_id: AWS access key (optional if using IAM role).
            aws_secret_access_key: AWS secret key (optional if using IAM role).
        """
        super().__init__(identity_token)
        self._aws_region = aws_region
        self._user_pool_id = user_pool_id
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._boto_client = None

    def _get_boto_client(self):
        """Lazily initialize the boto3 Cognito IDP client."""
        if self._boto_client is not None:
            return self._boto_client

        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for AWS Cognito identity provider. Install it with: pip install boto3")

        kwargs: dict = {
            "service_name": "cognito-idp",
            "region_name": self._aws_region,
        }

        if self._aws_access_key_id and self._aws_secret_access_key:
            kwargs["aws_access_key_id"] = self._aws_access_key_id
            kwargs["aws_secret_access_key"] = self._aws_secret_access_key

        self._boto_client = boto3.client(**kwargs)
        return self._boto_client

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get groups the current user belongs to.

        Args:
            query: Optional filter/pagination query.

        Returns:
            List of group responses.
        """
        username = self.identity_token.get_principal_name()
        if not username:
            return []

        try:
            client = self._get_boto_client()
            response = client.admin_list_groups_for_user(
                UserPoolId=self._user_pool_id,
                Username=username,
            )
        except Exception:
            return []

        return [
            IdentityGroupResponse(
                id=group["GroupName"],
                display_name=group.get("Description", group["GroupName"]),
            )
            for group in response.get("Groups", [])
        ]

    def get_security_groups(
        self, query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get all groups in the Cognito User Pool.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, next_token).
        """
        query = query or APIFilterQuery()

        try:
            client = self._get_boto_client()
            kwargs: dict = {"UserPoolId": self._user_pool_id}

            if query.top:
                kwargs["Limit"] = min(query.top, 60)
            if query.next_link:
                kwargs["NextToken"] = query.next_link

            response = client.list_groups(**kwargs)
        except Exception:
            return [], None

        groups = [
            IdentityGroupResponse(
                id=group["GroupName"],
                display_name=group.get("Description", group["GroupName"]),
            )
            for group in response.get("Groups", [])
        ]

        next_token = response.get("NextToken")
        return groups, next_token

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Get users in the Cognito User Pool.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (users, next_token).
        """
        query = query or APIFilterQuery()

        try:
            client = self._get_boto_client()
            kwargs: dict = {"UserPoolId": self._user_pool_id}

            if query.top:
                kwargs["Limit"] = min(query.top, 60)
            if query.search:
                kwargs["Filter"] = f'email ^= "{query.search}"'
            if query.next_link:
                kwargs["PaginationToken"] = query.next_link

            response = client.list_users(**kwargs)
        except Exception:
            return [], None

        users = [self._parse_cognito_user(user) for user in response.get("Users", [])]
        next_token = response.get("PaginationToken")
        return users, next_token

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get a single user by username.

        Args:
            user_id: Cognito username or sub.

        Returns:
            User identity response.
        """
        client = self._get_boto_client()
        response = client.admin_get_user(
            UserPoolId=self._user_pool_id,
            Username=user_id,
        )

        attrs = {attr["Name"]: attr["Value"] for attr in response.get("UserAttributes", [])}

        return IdentityUserResponse(
            id=attrs.get("sub", user_id),
            identity_provider=self.identity_token.get_identity_provider(),
            identity_tenant_id=self.identity_token.get_identity_tenant_id(),
            display_name=attrs.get("name", attrs.get("email", response.get("Username", ""))),
            firstname=attrs.get("given_name"),
            lastname=attrs.get("family_name"),
            mail=attrs.get("email"),
            principal_name=attrs.get("email", response.get("Username")),
        )

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get a single group by name.

        Args:
            group_id: Cognito group name.

        Returns:
            Group identity response.
        """
        client = self._get_boto_client()
        response = client.get_group(
            UserPoolId=self._user_pool_id,
            GroupName=group_id,
        )

        group = response.get("Group", {})
        return IdentityGroupResponse(
            id=group.get("GroupName", group_id),
            display_name=group.get("Description", group.get("GroupName", group_id)),
        )

    def _parse_cognito_user(self, user: dict) -> IdentityUserResponse:
        """Parse a Cognito user record into a response."""
        attrs = {attr["Name"]: attr["Value"] for attr in user.get("Attributes", [])}

        display_name = attrs.get("name", attrs.get("email", user.get("Username", "")))

        return IdentityUserResponse(
            id=attrs.get("sub", user.get("Username", "")),
            identity_provider=self.identity_token.get_identity_provider(),
            display_name=display_name,
            principal_name=attrs.get("email", user.get("Username")),
        )
