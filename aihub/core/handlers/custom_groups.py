"""Handler for custom group operations."""
from typing import Optional

from aihub.docdatabase.client import DatabaseClient
from aihub.core.docdatabase.models.custom_groups import CustomGroupModel
from aihub.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    UpdateCustomGroupRequest,
    AddMembersRequest,
    RemoveMembersRequest
)
from aihub.schema.responses.custom_groups import CustomGroupResponse
from aihub.exc.custom_groups import CustomGroupNotFoundError
from aihub.logger import get_logger

logger = get_logger(__name__)


class CustomGroupHandler:
    """Handler for custom group business logic."""

    def __init__(self, db_client: DatabaseClient):
        self.db_client = db_client

    @staticmethod
    def _model_to_response(group: CustomGroupModel) -> CustomGroupResponse:
        """Convert database model to response model."""
        return CustomGroupResponse(
            id=group.id,
            tenant_id=group.tenant_id,
            name=group.name,
            description=group.description,
            member_ids=group.member_ids,
            created_at=group.created_at.isoformat(),
            updated_at=group.updated_at.isoformat(),
            created_by=group.created_by,
            updated_by=group.updated_by
        )

    def list_custom_groups(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None
    ) -> list[CustomGroupResponse]:
        """
        List custom groups for a tenant.
        
        Args:
            tenant_id: Tenant ID to filter groups
            skip: Number of items to skip
            limit: Maximum number of items to return
            name: Optional name filter (regex)
        
        Returns:
            List of custom group responses
        """
        filters = {"tenant_id": tenant_id}
        
        if name:
            filters["name"] = {"$regex": name, "$options": "i"}
        
        groups = self.db_client.custom_groups.get_list(
            filters=filters,
            skip=skip,
            limit=limit
        )
        
        return [self._model_to_response(g) for g in groups]

    def get_custom_group(self, group_id: str) -> CustomGroupResponse:
        """
        Get a specific custom group by ID.
        
        Args:
            group_id: The custom group ID
        
        Returns:
            Custom group response
        
        Raises:
            CustomGroupNotFoundError: If group not found
        """
        group = self.db_client.custom_groups.get(group_id)
        
        if not group:
            raise CustomGroupNotFoundError(group_id)
        
        return self._model_to_response(group)

    def create_custom_group(
        self,
        tenant_id: str,
        data: CreateCustomGroupRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """
        Create a new custom group.
        
        Args:
            tenant_id: Tenant ID this group belongs to
            data: Group creation data
            user_id: ID of user creating the group
        
        Returns:
            Created custom group response
        """
        group = self.db_client.custom_groups.create(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            member_ids=data.member_ids,
            created_by=user_id
        )
        
        return self._model_to_response(group)

    def update_custom_group(
        self,
        group_id: str,
        data: UpdateCustomGroupRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """
        Update an existing custom group.
        
        Args:
            group_id: The custom group ID
            data: Group update data
            user_id: ID of user updating the group
        
        Returns:
            Updated custom group response
        
        Raises:
            CustomGroupNotFoundError: If group not found
        """
        group = self.db_client.custom_groups.update(
            group_id=group_id,
            name=data.name,
            description=data.description,
            updated_by=user_id
        )
        
        if not group:
            raise CustomGroupNotFoundError(group_id)
        
        return self._model_to_response(group)

    def add_members(
        self,
        group_id: str,
        data: AddMembersRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """
        Add members to a custom group.
        
        Args:
            group_id: The custom group ID
            data: Members to add
            user_id: ID of user performing the action
        
        Returns:
            Updated custom group response
        
        Raises:
            CustomGroupNotFoundError: If group not found
        """
        group = self.db_client.custom_groups.add_members(
            group_id=group_id,
            user_ids=data.member_ids,
            updated_by=user_id
        )
        
        if not group:
            raise CustomGroupNotFoundError(group_id)
        
        return self._model_to_response(group)

    def remove_members(
        self,
        group_id: str,
        data: RemoveMembersRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """
        Remove members from a custom group.
        
        Args:
            group_id: The custom group ID
            data: Members to remove
            user_id: ID of user performing the action
        
        Returns:
            Updated custom group response
        
        Raises:
            CustomGroupNotFoundError: If group not found
        """
        group = self.db_client.custom_groups.remove_members(
            group_id=group_id,
            user_ids=data.member_ids,
            updated_by=user_id
        )
        
        if not group:
            raise CustomGroupNotFoundError(group_id)
        
        return self._model_to_response(group)

    def delete_custom_group(self, group_id: str) -> None:
        """
        Delete a custom group.
        
        Args:
            group_id: The custom group ID
        
        Raises:
            CustomGroupNotFoundError: If group not found
        """
        success = self.db_client.custom_groups.delete(group_id)
        
        if not success:
            raise CustomGroupNotFoundError(group_id)
