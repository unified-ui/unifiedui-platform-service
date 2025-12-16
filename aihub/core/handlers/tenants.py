"""Business logic handlers for tenant operations."""
import logging
from typing import Optional, List

from aihub.database.client import DatabaseClient
from aihub.core.database.models.tenants import TenantModel
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse
from aihub.exc.tenants import TenantNotFoundError

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
        limit: int = 100
    ) -> List[TenantResponse]:
        """
        Get a list of tenants.
        
        Args:
            filters: Optional MongoDB filter criteria
            skip: Number of items to skip
            limit: Maximum number of items to return
            
        Returns:
            List of tenant responses
        """
        logger.info("Listing tenants", extra={"filters": filters, "skip": skip, "limit": limit})
        
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
