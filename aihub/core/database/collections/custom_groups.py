from abc import ABC, abstractmethod
from aihub.core.database.models.custom_groups import CustomGroupModel
from aihub.core.schema.users import IdentityProviderUserModel


class BaseCustomGroupsCollectionClient(ABC):
    """Abstract base class for custom groups collection clients in the database."""

    @abstractmethod
    def get(self, group_id: str) -> CustomGroupModel:
        """Retrieve a custom group by its ID.

        Args:
            group_id (str): The ID of the custom group to retrieve.

        Returns:
            CustomGroupModel: The custom group data.
        """
        pass

    @abstractmethod
    def get_list(self) -> list[CustomGroupModel]:
        """List all custom groups in the collection.

        Returns:
            list[CustomGroupModel]: A list of all custom groups.
        """
        pass

    @abstractmethod
    def create(self, custom_group: CustomGroupModel) -> CustomGroupModel:
        """Create a new custom group in the collection.

        Args:
            custom_group (CustomGroupModel): The custom group data to create.

        Returns:
            CustomGroupModel: The created custom group.
        """
        pass

    @abstractmethod
    def update(self, group_id: str, custom_group: CustomGroupModel) -> CustomGroupModel:
        """Update an existing custom group in the collection (PATCH).

        Args:
            group_id (str): The ID of the custom group to update.
            custom_group (CustomGroupModel): The new custom group data.

        Returns:
            CustomGroupModel: The updated custom group.
        """
        pass

    @abstractmethod
    def delete(self, group_id: str) -> None:
        """Delete a custom group from the collection.

        Args:
            group_id (str): The ID of the custom group to delete.
        """
        pass

    @abstractmethod
    def get_users(self, group_id: str) -> list[IdentityProviderUserModel]:
        """Retrieve all users that are members of a specific custom group.

        Args:
            group_id (str): The ID of the custom group.

        Returns:
            list[UserModel]: A list of users in the custom group.
        """
        pass

    @abstractmethod
    def add_users(self, group_id: str, users: list[IdentityProviderUserModel]) -> None:
        """Add users to a custom group.

        Args:
            group_id (str): The ID of the custom group.
            users (list[IdentityProviderUserModel]): List of users to add to the group.
        """
        pass

    @abstractmethod
    def remove_user(self, group_id: str, user: IdentityProviderUserModel) -> None:
        """Remove a user from a custom group.

        Args:
            group_id (str): The ID of the custom group.
            user (IdentityProviderUserModel): The user to remove from the group.
        """
        pass

    @abstractmethod
    def get_permissions(self, group_id: str) -> dict:
        """Retrieve permissions for a specific custom group.
        TODO: Define permission model.

        Args:
            group_id (str): The ID of the custom group.

        Returns:
            dict: The permissions associated with the custom group.
        """
        pass
