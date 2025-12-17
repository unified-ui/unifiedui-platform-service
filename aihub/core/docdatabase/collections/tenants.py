"""Abstract interface for Tenants collection."""
from abc import ABC, abstractmethod
from typing import Optional, List

from aihub.core.database.models.tenants import TenantModel


class TenantsCollection(ABC):
    """
    Abstract base class for Tenants collection operations.
    Provides standard CRUD operations for tenant management.
    """

    @abstractmethod
    def get(self, id: str) -> Optional[TenantModel]:
        """
        Get a single tenant by ID.
        
        Args:
            id: The unique identifier of the tenant
            
        Returns:
            The tenant if found, None otherwise
        """
        pass

    @abstractmethod
    def get_list(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TenantModel]:
        """
        Get a list of tenants with optional filters.
        
        Args:
            filters: Optional filter criteria
            skip: Number of items to skip (pagination)
            limit: Maximum number of items to return
            
        Returns:
            List of tenants matching the criteria
        """
        pass

    @abstractmethod
    def create(self, data: TenantModel) -> TenantModel:
        """
        Create a new tenant.
        
        Args:
            data: The tenant data to create
            
        Returns:
            The created tenant
        """
        pass

    @abstractmethod
    def update(self, id: str, data: dict) -> Optional[TenantModel]:
        """
        Update an existing tenant.
        
        Args:
            id: The unique identifier of the tenant
            data: The data to update
            
        Returns:
            The updated tenant if found, None otherwise
        """
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """
        Delete a tenant by ID.
        
        Args:
            id: The unique identifier of the tenant
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
