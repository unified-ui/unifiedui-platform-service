from abc import ABC, abstractmethod
from aihub.core.database.models.credentials import CredentialModel


class BaseCredentialsCollectionClient(ABC):
    """Abstract base class for credentials collection clients in the database."""

    @abstractmethod
    def get(self, credential_id: str) -> CredentialModel:
        """Retrieve a credential by its ID.

        Args:
            credential_id (str): The ID of the credential to retrieve.

        Returns:
            CredentialModel: The credential data.
        """
        pass

    @abstractmethod
    def get_list(self, user_id: str | None = None) -> list[CredentialModel]:
        """List all credentials in the collection, optionally filtered by user.

        Args:
            user_id (str | None): Optional user ID to filter credentials.

        Returns:
            list[CredentialModel]: A list of credentials.
        """
        pass

    @abstractmethod
    def create(self, credential: CredentialModel) -> CredentialModel:
        """Create a new credential in the collection.

        Args:
            credential (CredentialModel): The credential data to create.

        Returns:
            CredentialModel: The created credential.
        """
        pass

    @abstractmethod
    def update(self, credential_id: str, credential: CredentialModel) -> CredentialModel:
        """Update an existing credential in the collection (PATCH).

        Args:
            credential_id (str): The ID of the credential to update.
            credential (CredentialModel): The updated credential data.

        Returns:
            CredentialModel: The updated credential.
        """
        pass

    @abstractmethod
    def delete(self, credential_id: str) -> None:
        """Delete a credential from the collection.

        Args:
            credential_id (str): The ID of the credential to delete.
        """
        pass
