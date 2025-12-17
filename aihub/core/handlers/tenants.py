"""Business logic handlers for tenant operations using SQLAlchemy."""
from typing import Optional, List
import uuid
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import Tenant, TenantRole
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse
from aihub.exc.tenants import TenantNotFoundError
from aihub.logger import get_logger

logger = get_logger(__name__)


class TenantHandler:
    """Handler class for tenant business logic using SQLAlchemy."""

    def __init__(self, db_client: SQLAlchemyClient):
        """
        Initialize the tenant handler.
        
        Args:
            db_client: SQLAlchemy database client instance
        """
        self.db_client = db_client

    def list_tenants(
        self,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None
    ) -> List[TenantResponse]:
        """
        Get a list of tenants.
        
        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by tenant name (case-insensitive partial match)
            
        Returns:
            List of tenant responses
        """
        logger.info("Listing tenants", extra={"skip": skip, "limit": limit, "name_filter": name_filter})
        
        with self.db_client.get_session() as session:
            query = select(Tenant)
            
            # Apply name filter if provided
            if name_filter:
                query = query.where(Tenant.name.ilike(f"%{name_filter}%"))
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            tenants = session.execute(query).scalars().all()
            
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
        
        with self.db_client.get_session() as session:
            tenant = session.get(Tenant, tenant_id)
            
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
        Create a new tenant and assign the creator as GLOBAL_ADMIN.
        
        Args:
            request: Tenant creation data
            user_id: ID of the user creating the tenant (principal_id)
            
        Returns:
            Created tenant response
        """
        logger.info("Creating tenant", extra={"tenant_name": request.name, "user_id": user_id})
        
        tenant_id = str(uuid.uuid4())
        
        with self.db_client.get_session() as session:
            # Create tenant
            tenant = Tenant(
                id=tenant_id,
                name=request.name,
                description=request.description,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(tenant)
            session.flush()  # Flush to get the tenant ID for the role
            
            # Create GLOBAL_ADMIN role for the creator
            role_id = str(uuid.uuid4())
            tenant_role = TenantRole(
                id=role_id,
                tenant_id=tenant_id,
                principal_id=user_id,
                role="GLOBAL_ADMIN",
                name=f"Global Admin for {request.name}",
                description=f"Global administrator role for user {user_id} on tenant {request.name}"
            )
            session.add(tenant_role)
            
            # Commit happens automatically in context manager
            logger.info(
                "Tenant created with GLOBAL_ADMIN role",
                extra={"tenant_id": tenant_id, "user_id": user_id, "role_id": role_id}
            )
            
            return self._model_to_response(tenant)

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
        
        with self.db_client.get_session() as session:
            tenant = session.get(Tenant, tenant_id)
            
            if not tenant:
                logger.warning("Tenant not found for update", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            # Update fields if provided
            if request.name is not None:
                tenant.name = request.name
            if request.description is not None:
                tenant.description = request.description
            
            # Set updated_by
            tenant.updated_by = user_id
            
            # Commit happens automatically in context manager
            logger.info("Tenant updated", extra={"tenant_id": tenant_id, "user_id": user_id})
            
            return self._model_to_response(tenant)

    def delete_tenant(self, tenant_id: str) -> None:
        """
        Delete a tenant by ID.
        
        Args:
            tenant_id: The ID of the tenant to delete
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Deleting tenant", extra={"tenant_id": tenant_id})
        
        with self.db_client.get_session() as session:
            tenant = session.get(Tenant, tenant_id)
            
            if not tenant:
                logger.warning("Tenant not found for deletion", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            session.delete(tenant)
            # Commit happens automatically in context manager
            
            logger.info("Tenant deleted", extra={"tenant_id": tenant_id})

    def list_tenants_by_principal_id(
        self,
        principal_ids: List[str]
    ) -> List[dict]:
        """
        Get all tenants where the given principals have roles, including their roles.
        
        Args:
            principal_ids: List of principal IDs to search for
            
        Returns:
            List of dicts with 'tenant' and 'roles' keys
        """
        logger.info(
            "Listing tenants by principal IDs",
            extra={"principal_ids": principal_ids, "count": len(principal_ids)}
        )
        
        if not principal_ids:
            logger.info("No principal IDs provided, returning empty list")
            return []
        
        with self.db_client.get_session() as session:
            # Query to get all tenant_roles for the given principal_ids
            query = (
                select(Tenant, TenantRole)
                .join(TenantRole, Tenant.id == TenantRole.tenant_id)
                .where(TenantRole.principal_id.in_(principal_ids))
                .order_by(Tenant.name, TenantRole.role)
            )
            
            results = session.execute(query).all()
            
            # Group roles by tenant
            tenants_dict = {}
            for tenant, role in results:
                if tenant.id not in tenants_dict:
                    tenants_dict[tenant.id] = {
                        "tenant": tenant,
                        "roles": []
                    }
                tenants_dict[tenant.id]["roles"].append(role)
            
            # Convert to response format
            response = []
            for tenant_data in tenants_dict.values():
                tenant_response = self._model_to_response(tenant_data["tenant"])
                roles_response = [
                    self._role_to_response(role) for role in tenant_data["roles"]
                ]
                response.append({
                    "tenant": tenant_response,
                    "roles": roles_response
                })
            
            logger.info(
                "Retrieved tenants by principal IDs",
                extra={"tenant_count": len(response)}
            )
            return response
    
    @staticmethod
    def _model_to_response(tenant: Tenant) -> TenantResponse:
        """
        Convert a tenant model to a response object.
        
        Args:
            tenant: Tenant SQLAlchemy model
            
        Returns:
            Tenant response
        """
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            created_by=tenant.created_by,
            updated_by=tenant.updated_by
        )
    
    @staticmethod
    def _role_to_response(role: TenantRole):
        """
        Convert a tenant role model to a response object.
        
        Args:
            role: TenantRole SQLAlchemy model
            
        Returns:
            TenantRoleResponse
        """
        from aihub.schema.responses.tenants import TenantRoleResponse
        return TenantRoleResponse(
            id=role.id,
            role=role.role,
            name=role.name,
            description=role.description,
            created_at=role.created_at
        )
