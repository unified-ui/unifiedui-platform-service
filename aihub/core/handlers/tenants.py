"""Business logic handlers for tenant operations."""
from typing import Optional, List

from aihub.database.client import DatabaseClient
from aihub.caching.client import CacheClient
from aihub.core.database.models.tenants import TenantModel
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse
from aihub.exc.tenants import TenantNotFoundError
from aihub.core.handlers.permissions import PermissionHandler
from aihub.logger import get_logger

logger = get_logger(__name__)


class TenantHandler:
    """Handler class for tenant business logic."""

    def __init__(self, db_client: DatabaseClient, cache_client: Optional[CacheClient] = None):
        """
        Initialize the tenant handler.
        
        Args:
            db_client: Database client instance
            cache_client: Cache client instance (optional)
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_tenants(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100,
        tenant_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        route: Optional[str] = None
    ) -> List[TenantResponse]:
        """
        Get a list of tenants (filtered by tenant IDs).
        
        Args:
            filters: Optional MongoDB filter criteria
            skip: Number of items to skip
            limit: Maximum number of items to return
            tenant_ids: List of tenant IDs to filter by (for permission filtering)
            user_id: User ID for caching
            route: Request route for caching
            
        Returns:
            List of tenant responses
        """
        logger.info("Listing tenants", extra={"filters": filters, "skip": skip, "limit": limit})
        
        # Check cache if enabled
        if self.cache_client and user_id and route:
            cached = self.cache_client.tenants.get_tenant_list(user_id, route)
            if cached is not None:
                logger.debug("Returning cached tenant list")
                return cached
        
        # Apply tenant_ids filter if provided
        if tenant_ids is not None:
            if not tenant_ids:
                logger.info("No accessible tenants")
                return []
            
            filters = filters or {}
            filters["id"] = {"$in": tenant_ids}
        
        tenants = self.db_client.tenants.get_list(
            filters=filters,
            skip=skip,
            limit=limit
        )
        
        logger.info("Retrieved tenants", extra={"count": len(tenants)})
        result = [self._model_to_response(tenant) for tenant in tenants]
        
        # Cache result if enabled
        if self.cache_client and user_id and route:
            self.cache_client.tenants.set_tenant_list(user_id, route, result)
            logger.debug("Cached tenant list")
        
        return result

    def get_tenant(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        route: Optional[str] = None
    ) -> TenantResponse:
        """
        Get a specific tenant by ID.
        
        Args:
            tenant_id: The ID of the tenant
            user_id: User ID for caching
            route: Request route for caching
            
        Returns:
            Tenant response
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Fetching tenant", extra={"tenant_id": tenant_id})
        
        # Check cache if enabled
        if self.cache_client and user_id and route:
            cached = self.cache_client.tenants.get_tenant(tenant_id, user_id, route)
            if cached is not None:
                logger.debug("Returning cached tenant")
                return cached
        
        tenant = self.db_client.tenants.get(tenant_id)
        if not tenant:
            logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
            raise TenantNotFoundError(tenant_id)
        
        logger.info("Tenant retrieved", extra={"tenant_id": tenant_id})
        result = self._model_to_response(tenant)
        
        # Cache result if enabled
        if self.cache_client and user_id and route:
            self.cache_client.tenants.set_tenant(tenant_id, user_id, route, result)
            logger.debug("Cached tenant")
        
        return result

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
        
        # Invalidate cache for tenant lists (all users might see this new tenant)
        if self.cache_client:
            # Invalidate route-based tenant caches
            invalidated = self.cache_client.tenants.invalidate_all()
            logger.debug(f"Invalidated {invalidated} tenant list caches after creation")
            
            # Also invalidate identity-based tenant caches
            identity_invalidated = self.cache_client._client._cache.delete_pattern("identity:tenants:*")
            logger.debug(f"Invalidated {identity_invalidated} identity tenant caches after creation")
        
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
        
        # Invalidate cache for this tenant and all list caches
        if self.cache_client:
            # Invalidate route-based tenant caches
            invalidated = self.cache_client.tenants.invalidate_tenant(tenant_id)
            logger.debug(f"Invalidated {invalidated} cache entries for tenant {tenant_id}")
            
            # Also invalidate identity-based tenant caches
            identity_invalidated = self.cache_client._client._cache.delete_pattern("identity:tenants:*")
            logger.debug(f"Invalidated {identity_invalidated} identity tenant caches after update")
        
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
        
        # Invalidate cache for this tenant and all list caches
        if self.cache_client:
            # Invalidate route-based tenant caches
            invalidated = self.cache_client.tenants.invalidate_tenant(tenant_id)
            logger.debug(f"Invalidated {invalidated} cache entries for tenant {tenant_id}")
            
            # Also invalidate identity-based tenant caches
            identity_invalidated = self.cache_client._client._cache.delete_pattern("identity:tenants:*")
            logger.debug(f"Invalidated {identity_invalidated} identity tenant caches after deletion")

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
