"""Business logic handlers for tenant operations."""
from typing import Optional, List

from aihub.database.client import DatabaseClient
from aihub.core.database.models.tenants import TenantModel
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse


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
        tenants = self.db_client.tenants.get_list(
            filters=filters,
            skip=skip,
            limit=limit
        )
        
        return [self._model_to_response(tenant) for tenant in tenants]

    def get_tenant(self, tenant_id: str) -> Optional[TenantResponse]:
        """
        Get a specific tenant by ID.
        
        Args:
            tenant_id: The ID of the tenant
            
        Returns:
            Tenant response if found, None otherwise
        """
        tenant = self.db_client.tenants.get(tenant_id)
        if not tenant:
            return None
        
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
        tenant = TenantModel(
            name=request.name,
            description=request.description,
            meta=request.meta,
            created_by=user_id,
            updated_by=user_id
        )
        
        created_tenant = self.db_client.tenants.create(tenant)
        return self._model_to_response(created_tenant)

    def update_tenant(
        self,
        tenant_id: str,
        request: UpdateTenantRequest,
        user_id: str
    ) -> Optional[TenantResponse]:
        """
        Update an existing tenant.
        
        Args:
            tenant_id: The ID of the tenant to update
            request: Tenant update data
            user_id: ID of the user updating the tenant
            
        Returns:
            Updated tenant response if found, None otherwise
        """
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
            return None
        
        return self._model_to_response(updated_tenant)

    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Delete a tenant by ID.
        
        Args:
            tenant_id: The ID of the tenant to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        return self.db_client.tenants.delete(tenant_id)

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
