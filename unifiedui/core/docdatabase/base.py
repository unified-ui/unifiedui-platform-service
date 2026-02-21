'''
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Any

from unifiedui.core.docdatabase.models.base import BaseDatabaseModel


TModel = TypeVar('TModel', bound=BaseDatabaseModel)


class BaseCollection(ABC, Generic[TModel]):
    """
    Abstract base class for database collections.
    Provides standard CRUD operations.
    """

    @abstractmethod
    def get(self, id: str) -> Optional[TModel]:
        """Get a single document by ID."""
        pass

    @abstractmethod
    def get_list(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TModel]:
        """Get a list of documents with optional filters."""
        pass

    @abstractmethod
    def create(self, data: TModel) -> TModel:
        """Create a new document."""
        pass

    @abstractmethod
    def update(self, id: str, data: dict) -> Optional[TModel]:
        """Update an existing document."""
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete a document by ID."""
        pass


class BaseDatabaseClient(ABC):
    """
    Abstract base class for database clients.
    Each implementation provides access to collections via methods.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        pass

    @abstractmethod
    def tenants(self):
        """
        Get the tenants collection.

        Returns:
            TenantsCollection: The tenants collection interface
        """
        pass

    @abstractmethod
    def permissions(self):
        """
        Get the permissions collection.

        Returns:
            PermissionsCollection: The permissions collection interface
        """
        pass
'''
