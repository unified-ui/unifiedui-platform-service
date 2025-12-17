"""Abstract interface for custom groups collection."""
from abc import ABC, abstractmethod
from typing import Optional
from aihub.core.database.models.custom_groups import CustomGroupModel


class CustomGroupsCollection(ABC):
    """Abstract base class for custom groups collection."""

    @abstractmethod
    def get(self, group_id: str) -> Optional[CustomGroupModel]:
        """Retrieve a custom group by its ID.

        Args:
            group_id: The ID of the custom group to retrieve.

        Returns:
            CustomGroupModel or None if not found.
        """
        pass

    @abstractmethod
    def get_list(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[CustomGroupModel]:
        """List custom groups with optional filtering.

        Args:
            filters: MongoDB filter dictionary.
            skip: Number of documents to skip.
            limit: Maximum number of documents to return.

        Returns:
            List of custom groups.
        """
        pass

    @abstractmethod
    def create(
        self,
        tenant_id: str,
        name: str,
        description: Optional[str],
        member_ids: list[str],
        created_by: str
    ) -> CustomGroupModel:
        """Create a new custom group.

        Args:
            tenant_id: Tenant ID this group belongs to.
            name: Group name.
            description: Optional group description.
            member_ids: Initial list of member user IDs.
            created_by: User ID who created this group.

        Returns:
            Created custom group.
        """
        pass

    @abstractmethod
    def update(
        self,
        group_id: str,
        name: Optional[str],
        description: Optional[str],
        updated_by: str
    ) -> Optional[CustomGroupModel]:
        """Update an existing custom group.

        Args:
            group_id: The ID of the custom group to update.
            name: Optional new group name.
            description: Optional new description.
            updated_by: User ID who updated this group.

        Returns:
            Updated custom group or None if not found.
        """
        pass

    @abstractmethod
    def add_members(
        self,
        group_id: str,
        user_ids: list[str],
        updated_by: str
    ) -> Optional[CustomGroupModel]:
        """Add members to a custom group.

        Args:
            group_id: The ID of the custom group.
            user_ids: List of user IDs to add.
            updated_by: User ID who performed this action.

        Returns:
            Updated custom group or None if not found.
        """
        pass

    @abstractmethod
    def remove_members(
        self,
        group_id: str,
        user_ids: list[str],
        updated_by: str
    ) -> Optional[CustomGroupModel]:
        """Remove members from a custom group.

        Args:
            group_id: The ID of the custom group.
            user_ids: List of user IDs to remove.
            updated_by: User ID who performed this action.

        Returns:
            Updated custom group or None if not found.
        """
        pass

    @abstractmethod
    def delete(self, group_id: str) -> bool:
        """Delete a custom group by its ID.

        Args:
            group_id: The ID of the custom group to delete.

        Returns:
            True if deleted, False otherwise.
        """
        pass
