from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class MockIdentityProvider(BaseIdentityProvider):
    """Mock identity provider for testing."""

    def __init__(self, identity_token: BaseIdentityToken):
        super().__init__(identity_token)
        self._users: dict[str, dict[str, str]] = {}
        self._groups: dict[str, dict[str, str]] = {}

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get security groups for current user."""
        # Get groups from token if it has get_groups method (MockIdentityToken)
        if hasattr(self.identity_token, "get_groups"):
            group_ids = self.identity_token.get_groups()
            return [
                IdentityGroupResponse(
                    id=group_id,
                    display_name=self._groups.get(group_id, {}).get("display_name", f"Mock Group {group_id}"),
                )
                for group_id in group_ids
            ]
        return []

    def get_security_groups(
        self, query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get all security groups."""
        return [], None

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Get users from directory."""
        return [], None

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get user by ID."""
        return IdentityUserResponse(
            id=user_id,
            identity_provider=self.identity_token.get_identity_provider(),
            identity_tenant_id=self.identity_token.get_identity_tenant_id(),
            display_name="Mock User",
            firstname="Mock",
            lastname="User",
            mail=f"{user_id}@test.com",
            principal_name=f"{user_id}@test.com",
        )

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get group by ID."""
        group = self._groups.get(group_id, {})
        return IdentityGroupResponse(id=group_id, display_name=group.get("display_name", f"Mock Group {group_id}"))

    def get_principal_name(self, principal_id: str, principal_type: str) -> str:
        """
        Get the principal name for a user or group.

        For users, returns the email (principal_name).
        For groups, returns the display name.

        Args:
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER or IDENTITY_GROUP)

        Returns:
            The principal name string
        """
        if principal_type == "IDENTITY_USER":
            user = self.get_user_by_id(principal_id)
            return user.principal_name or user.mail or user.display_name
        else:  # IDENTITY_GROUP
            group = self.get_group_by_id(principal_id)
            return group.display_name

    def add_group(self, group_id: str, display_name: str):
        """Add a mock group (for testing)."""
        self._groups[group_id] = {"display_name": display_name}
