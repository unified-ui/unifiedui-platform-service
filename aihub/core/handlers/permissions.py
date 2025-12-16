"""Business logic handlers for permission operations."""
import logging
from typing import List
from collections import defaultdict

from aihub.database.client import DatabaseClient
from aihub.core.database.models.permissions import PermissionModel, AssignedTo
from aihub.schema.requests.permissions import SetPermissionsRequest, DeletePermissionRequest
from aihub.schema.responses.permissions import ResourcePermissionsResponse, PermissionAssignmentResponse
from aihub.utils.default_factory_functions import current_iso_datetime, generate_id

logger = logging.getLogger(__name__)


class PermissionHandler:
    """Handler class for permission business logic."""

    def __init__(self, db_client: DatabaseClient):
        """
        Initialize the permission handler.
        
        Args:
            db_client: Database client instance
        """
        self.db_client = db_client

    def get_resource_permissions(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str
    ) -> ResourcePermissionsResponse:
        """
        Get all permissions for a specific resource.
        
        Args:
            resource_type: Type of resource (e.g., 'tenants')
            resource_id: ID of the resource
            tenant_id: Tenant ID
            
        Returns:
            ResourcePermissionsResponse with grouped permissions
        """
        logger.info(
            "Fetching resource permissions",
            extra={"resource_type": resource_type, "resource_id": resource_id}
        )
        
        permissions = self.db_client.permissions.get_resource_permissions(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id
        )
        
        # Group permissions by assigned_to
        grouped = defaultdict(list)
        for perm in permissions:
            key = f"{perm.assigned_to.type}:{perm.assigned_to.id}"
            grouped[key].append(perm.action)
        
        # Convert to response format
        assignments = []
        for key, actions in grouped.items():
            entity_type, entity_id = key.split(":", 1)
            assignments.append(PermissionAssignmentResponse(
                type=entity_type,
                id=entity_id,
                actions=actions
            ))
        
        logger.info(
            "Resource permissions retrieved",
            extra={"resource_type": resource_type, "resource_id": resource_id, "count": len(assignments)}
        )
        
        return ResourcePermissionsResponse(
            resource_type=resource_type,
            resource_id=resource_id,
            permissions=assignments
        )

    def set_resource_permissions(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str,
        request: SetPermissionsRequest,
        user_id: str
    ) -> ResourcePermissionsResponse:
        """
        Set permissions for a resource (replaces existing permissions).
        
        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            tenant_id: Tenant ID
            request: Permission assignments
            user_id: User ID performing the operation
            
        Returns:
            Updated permissions
        """
        logger.info(
            "Setting resource permissions",
            extra={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "assignments_count": len(request.assignments)
            }
        )
        
        # Delete all existing permissions for this resource
        deleted_count = self.db_client.permissions.delete_resource_permissions(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id
        )
        
        logger.debug(f"Deleted {deleted_count} existing permissions")
        
        # Create new permissions
        new_permissions = []
        for assignment in request.assignments:
            for action in assignment.actions:
                perm = PermissionModel(
                    id=generate_id(),
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    scope="specific",
                    assigned_to=AssignedTo(type=assignment.type, id=assignment.id),
                    created_at=current_iso_datetime(),
                    created_by=user_id
                )
                new_permissions.append(perm)
        
        if new_permissions:
            self.db_client.permissions.create_many(new_permissions)
        
        logger.info(
            "Resource permissions set",
            extra={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "new_count": len(new_permissions)
            }
        )
        
        # Return updated permissions
        return self.get_resource_permissions(resource_type, resource_id, tenant_id)

    def delete_resource_permission(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str,
        request: DeletePermissionRequest
    ) -> ResourcePermissionsResponse:
        """
        Delete specific permissions for a user/group on a resource.
        
        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            tenant_id: Tenant ID
            request: Entity to remove permissions for
            
        Returns:
            Updated permissions
        """
        logger.info(
            "Deleting resource permissions",
            extra={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "entity_type": request.type,
                "entity_id": request.id
            }
        )
        
        deleted_count = self.db_client.permissions.delete_resource_permissions(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id,
            assigned_to=AssignedTo(type=request.type, id=request.id)
        )
        
        logger.info(
            "Resource permissions deleted",
            extra={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "deleted_count": deleted_count
            }
        )
        
        # Return updated permissions
        return self.get_resource_permissions(resource_type, resource_id, tenant_id)

    def create_initial_permissions(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str,
        user_id: str,
        actions: List[str]
    ) -> None:
        """
        Create initial permissions for a resource owner.
        Used when creating new resources.
        
        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            tenant_id: Tenant ID
            user_id: Owner user ID
            actions: List of actions to grant (e.g., ['read', 'write', 'admin'])
        """
        logger.info(
            "Creating initial permissions",
            extra={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": user_id,
                "actions": actions
            }
        )
        
        permissions = []
        for action in actions:
            perm = PermissionModel(
                id=generate_id(),
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                scope="specific",
                assigned_to=AssignedTo(type="user", id=user_id),
                created_at=current_iso_datetime(),
                created_by=user_id
            )
            permissions.append(perm)
        
        self.db_client.permissions.create_many(permissions)
        
        logger.info(
            "Initial permissions created",
            extra={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "count": len(permissions)
            }
        )
