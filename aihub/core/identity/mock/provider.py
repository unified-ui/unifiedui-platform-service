from aihub.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from aihub.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from aihub.utils.api_query import APIFilterQuery


class MockIdentityProvider(BaseIdentityProvider):
    """Mock identity provider for testing."""
    
    def __init__(self, identity_token: BaseIdentityToken):
        super().__init__(identity_token)
        # Mock data storage
        self._users = {}
        self._groups = {}
    
    def get_current_user_security_groups(
        self,
        query: APIFilterQuery | None = None
    ) -> list[IdentityGroupResponse]:
        """Get security groups for current user."""
        return []
    
    def get_security_groups(
        self,
        query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get all security groups."""
        return [], None
    
    def get_users(
        self,
        query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityUserResponse], str | None]:
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
            user_principal_name=f"{user_id}@test.com"
        )
    
    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get group by ID."""
        return IdentityGroupResponse(
            id=group_id,
            display_name="Mock Group"
        )
