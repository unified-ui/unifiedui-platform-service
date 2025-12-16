"""Business logic handlers for tenant operations."""
import logging
from typing import Optional, List

from aihub.database.client import DatabaseClient
from aihub.core.database.models.tenants import TenantModel
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse
from aihub.exc.tenants import TenantNotFoundError
from aihub.core.handlers.permissions import PermissionHandler

logger = logging.getLogger(__name__)


class TenantHandler:
    """Handler class for tenant business logic."""

    def __init__(self, db_client: DatabaseClient):
        """
        Initialize the tenant handler.
        
        Args:
            db_client: Database client instance
        """
        self.db_client = db_client

    def list_tenants(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[str] = None,
        user_groups: Optional[List[dict]] = None
    ) -> List[TenantResponse]:
        """
        Get a list of tenants (filtered by user permissions).
        
        Args:
            filters: Optional MongoDB filter criteria
            skip: Number of items to skip
            limit: Maximum number of items to return
            user_id: User ID for permission filtering
            user_groups: List of user groups for permission filtering
            
        Returns:
            List of tenant responses
        """
        logger.info("Listing tenants", extra={"filters": filters, "skip": skip, "limit": limit})
        
        # Build assigned_to list for permission check
        if user_id:
            from aihub.core.database.models.permissions import AssignedTo
            
            assigned_to_list = [AssignedTo(type="user", id=user_id)]
            
            # Add identity groups
            if user_groups:
                for group in user_groups:
                    assigned_to_list.append(AssignedTo(
                        type="identity_group",
                        id=group.get("id")
                    ))
            
            # Get all permissions for this user on "tenants" resources
            # Extract distinct resource_ids (these are the tenant IDs)
            # Build $or query for MongoDB
            or_conditions = []
            for at in assigned_to_list:
                or_conditions.append({
                    "assigned_to.type": at.type,
                    "assigned_to.id": at.id
                })
            
            permissions = self.db_client.permissions.get_list(
                filters={
                    "resource_type": "tenants",
                    "$or": or_conditions,
                    "action": "read"
                },
                limit=1000
            )
            
            accessible_ids = list(set([p.resource_id for p in permissions]))
            
            logger.debug(f"User can access {len(accessible_ids)} tenants")
            
            # Add id filter to only show accessible tenants
            if not accessible_ids:
                logger.info("User has no accessible tenants")
                return []
            
            filters = filters or {}
            filters["id"] = {"$in": accessible_ids}
        
        tenants = self.db_client.tenants.get_list(
            filters=filters,
            skip=skip,
            limit=limit
        )
        
        logger.info("Retrieved tenants", extra={"count": len(tenants)})
        return [self._model_to_response(tenant) for tenant in tenants]

    def get_tenant(self, tenant_id: str) -> TenantResponse:
        """
        Get a specific tenant by ID.
        
        Args:
            tenant_id: The ID of the tenant
            
        Returns:
            Tenant response
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Fetching tenant", extra={"tenant_id": tenant_id})
        
        tenant = self.db_client.tenants.get(tenant_id)
        if not tenant:
            logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
            raise TenantNotFoundError(tenant_id)
        
        logger.info("Tenant retrieved", extra={"tenant_id": tenant_id})
        return self._model_to_response(tenant)

    def create_tenant(
        self,
        request: CreateTenantRequest,
        user_id: str
    ) -> TenantResponse:
        """
        Create a new tenant.
        
        Args:
            request: Tenant creation data
            user_id: ID of the user creating the tenant
            
        Returns:
            Created tenant response
        """
        logger.info("Creating tenant", extra={"tenant_name": request.name, "user_id": user_id})
        
        tenant = TenantModel(
            name=request.name,
            description=request.description,
            meta=request.meta,
            created_by=user_id,
            updated_by=user_id
        )
        
        created_tenant = self.db_client.tenants.create(tenant)
        logger.info("Tenant created", extra={"tenant_id": created_tenant.id, "user_id": user_id})
        
        # Create initial permissions for the creator (read, write, admin)
        # Use the created tenant's ID as the tenant_id for the permission context
        permission_handler = PermissionHandler(self.db_client)
        permission_handler.create_initial_permissions(
            resource_type="tenants",
            resource_id=created_tenant.id,
            tenant_id=created_tenant.id,  # Self-referential: the tenant is its own context
            user_id=user_id,
            actions=["read", "write", "admin"]
        )
        logger.info(
            "Initial permissions created for tenant",
            extra={"tenant_id": created_tenant.id, "user_id": user_id}
        )
        
        return self._model_to_response(created_tenant)

    def update_tenant(
        self,
        tenant_id: str,
        request: UpdateTenantRequest,
        user_id: str
    ) -> TenantResponse:
        """
        Update an existing tenant.
        
        Args:
            tenant_id: The ID of the tenant to update
            request: Tenant update data
            user_id: ID of the user updating the tenant
            
        Returns:
            Updated tenant response
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Updating tenant", extra={"tenant_id": tenant_id, "user_id": user_id})
        
        # Build update data
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.meta is not None:
            update_data["meta"] = request.meta
        
        # Always set updated_by
        update_data["updated_by"] = user_id
        
        updated_tenant = self.db_client.tenants.update(tenant_id, update_data)
        if not updated_tenant:
            logger.warning("Tenant not found for update", extra={"tenant_id": tenant_id})
            raise TenantNotFoundError(tenant_id)
        
        logger.info("Tenant updated", extra={"tenant_id": tenant_id, "user_id": user_id})
        return self._model_to_response(updated_tenant)

    def delete_tenant(self, tenant_id: str) -> None:
        """
        Delete a tenant by ID.
        
        Args:
            tenant_id: The ID of the tenant to delete
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Deleting tenant", extra={"tenant_id": tenant_id})
        
        success = self.db_client.tenants.delete(tenant_id)
        if not success:
            logger.warning("Tenant not found for deletion", extra={"tenant_id": tenant_id})
            raise TenantNotFoundError(tenant_id)
        
        logger.info("Tenant deleted", extra={"tenant_id": tenant_id})

    @staticmethod
    def _model_to_response(tenant: TenantModel) -> TenantResponse:
        """
        Convert a tenant model to a response object.
        
        Args:
            tenant: Tenant model
            
        Returns:
            Tenant response
        """
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            meta=tenant.meta,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            created_by=tenant.created_by,
            updated_by=tenant.updated_by
        )
