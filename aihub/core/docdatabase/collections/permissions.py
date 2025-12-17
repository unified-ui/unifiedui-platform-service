"""Abstract interface for Permissions collection."""
from abc import ABC, abstractmethod
from typing import Optional, List

from aihub.core.database.models.permissions import PermissionModel, AssignedTo


class PermissionsCollection(ABC):
    """
    Abstract base class for Permissions collection operations.
    Provides operations for permission management.
    """

    @abstractmethod
    def get(self, id: str) -> Optional[PermissionModel]:
        """
        Get a single permission by ID.
        
        Args:
            id: The unique identifier of the permission
            
        Returns:
            The permission if found, None otherwise
        """
        pass

    @abstractmethod
    def get_list(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PermissionModel]:
        """
        Get a list of permissions with optional filters.
        
        Args:
            filters: Optional filter criteria
            skip: Number of items to skip (pagination)
            limit: Maximum number of items to return
            
        Returns:
            List of permissions matching the criteria
        """
        pass

    @abstractmethod
    def get_resource_permissions(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str
    ) -> List[PermissionModel]:
        """
        Get all permissions for a specific resource.
        
        Args:
            resource_type: Type of resource (e.g., 'tenants')
            resource_id: ID of the resource
            tenant_id: Tenant ID
            
        Returns:
            List of permissions for the resource
        """
        pass

    @abstractmethod
    def get_user_accessible_resources(
        self,
        resource_type: str,
        tenant_id: str,
        assigned_to_list: List[AssignedTo],
        action: Optional[str] = None
    ) -> List[str]:
        """
        Get list of resource IDs that a user (or their groups) can access.
        
        Args:
            resource_type: Type of resource (e.g., 'tenants')
            tenant_id: Tenant ID
            assigned_to_list: List of user/group assignments to check
            action: Optional specific action to filter (e.g., 'read')
            
        Returns:
            List of resource IDs the user can access
        """
        pass

    @abstractmethod
    def check_permission(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str,
        assigned_to_list: List[AssignedTo],
        action: str
    ) -> bool:
        """
        Check if user has specific permission on a resource.
        
        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            tenant_id: Tenant ID
            assigned_to_list: List of user/group assignments to check
            action: Action to check (e.g., 'read', 'write', 'admin')
            
        Returns:
            True if permission exists, False otherwise
        """
        pass

    @abstractmethod
    def create(self, data: PermissionModel) -> PermissionModel:
        """
        Create a new permission.
        
        Args:
            data: The permission data to create
            
        Returns:
            The created permission
        """
        pass

    @abstractmethod
    def create_many(self, permissions: List[PermissionModel]) -> List[PermissionModel]:
        """
        Create multiple permissions at once.
        
        Args:
            permissions: List of permissions to create
            
        Returns:
            List of created permissions
        """
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """
        Delete a permission by ID.
        
        Args:
            id: The unique identifier of the permission
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass

    @abstractmethod
    def delete_resource_permissions(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str,
        assigned_to: Optional[AssignedTo] = None
    ) -> int:
        """
        Delete permissions for a resource, optionally filtered by assigned_to.
        
        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            tenant_id: Tenant ID
            assigned_to: Optional filter to delete only specific assignments
            
        Returns:
            Number of deleted permissions
        """
        pass
