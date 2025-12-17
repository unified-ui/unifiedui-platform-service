from abc import ABC, abstractmethod
from aihub.core.database.models.applications import ApplicationModel
from aihub.core.database.models.conversations import ConversationModel


class BaseApplicationsCollectionClient(ABC):
    """Abstract base class for application collection clients in the database."""

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
    def get_list(self) -> list[ApplicationModel]:
        """List all applications in the collection.

        Returns:
            list: A list of all applications.
        """
        pass

    @abstractmethod
    def create(self, application: ApplicationModel) -> ApplicationModel:
        """Create a new application in the collection.

        Args:
            application (ApplicationModel): The application data to create.

        Returns:
            ApplicationModel: The created application.
        """
        pass

    @abstractmethod
    def update(self, app_id: str, application: ApplicationModel) -> ApplicationModel:
        """Update an existing application in the collection (PATCH).

        Args:
            app_id (str): The ID of the application to update.
            application (ApplicationModel): The new application data.

        Returns:
            ApplicationModel: The updated application.
        """
        pass

    @abstractmethod
    def delete(self, app_id: str) -> None:
        """Delete an application from the collection.

        Args:
            app_id (str): The ID of the application to delete.
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
