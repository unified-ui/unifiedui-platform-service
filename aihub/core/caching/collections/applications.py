from abc import ABC, abstractmethod
from aihub.core.database.models.applications import ApplicationModel
from aihub.core.database.models.conversations import ConversationModel


class BaseApplicationsCollectionCache(ABC):
    """Abstract base class for application collection caches in the database."""

    @abstractmethod
    def get(self, app_id: str) -> dict:
        """Retrieve an application by its ID.

        Args:
            app_id (str): The ID of the application to retrieve.

        Returns:
            dict: The application data.
        """
        pass

    @abstractmethod
    def set(self, key: str, data: ApplicationModel | list[ApplicationModel]) -> None:
        """Set or update an application by its ID.

        Args:
            app_id (str): The ID of the application to set or update.
            data (dict): The application data to store.
        """
        pass

    @abstractmethod
    def get_list(self) -> list[ApplicationModel]:
        """List all applications in the collection.

        Returns:
            list: A list of all applications.
        """
        pass


    @abstractmethod
    def get_conversations(self, app_id: str) -> list[ConversationModel]:
        """Retrieve all conversations associated with a specific application.

        Args:
            app_id (str): The ID of the application.

        Returns:
            list: A list of conversations related to the application.
        """
        pass

    @abstractmethod
    def get_permissions(self, app_id: str) -> dict:
        """Retrieve permissions for a specific application.
        TODO: Define permission model.

        Args:
            app_id (str): The ID of the application.
        Returns:
            dict: The permissions associated with the application.
        """
        pass
