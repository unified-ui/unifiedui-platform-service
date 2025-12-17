"""Business logic handlers for tenant operations using SQLAlchemy."""
from typing import Optional, List
import uuid
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import Tenant, TenantPrincipal
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse
from aihub.exc.tenants import TenantNotFoundError
from aihub.caching.client import CacheClient
from aihub.logger import get_logger

logger = get_logger(__name__)


class TenantHandler:
    """Handler class for tenant business logic using SQLAlchemy."""

    def __init__(self, db_client: SQLAlchemyClient, cache_client: Optional[CacheClient] = None):
        """
        Initialize the tenant handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

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
            tenant_role = TenantPrincipal(
                id=role_id,
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type="IDENTITY_USER",
                role="GLOBAL_ADMIN",
                name=f"Global Admin for {request.name}",
                description=f"Global administrator role for user {user_id} on tenant {request.name}",
                created_by=user_id,
                updated_by=user_id
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
                select(Tenant, TenantPrincipal)
                .join(TenantPrincipal, Tenant.id == TenantPrincipal.tenant_id)
                .where(TenantPrincipal.principal_id.in_(principal_ids))
                .order_by(Tenant.name, TenantPrincipal.role)
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
    
    def get_user_tenants_with_roles(
        self,
        user_id: str,
        identity_group_ids: List[str],
        custom_group_ids: List[str],
        use_cache: bool = True
    ) -> List[dict]:
        """
        Get all tenants and roles for a user based on their user ID, identity groups, and custom groups.
        
        Args:
            user_id: The identity user ID
            identity_group_ids: List of identity group IDs the user belongs to
            custom_group_ids: List of custom group IDs the user belongs to
            use_cache: Whether to use caching (default: True)
            
        Returns:
            List of dicts with 'tenant' and 'roles' keys, where roles are deduplicated
        """
        logger.info(
            "Getting user tenants with roles",
            extra={
                "user_id": user_id,
                "identity_groups_count": len(identity_group_ids),
                "custom_groups_count": len(custom_group_ids)
            }
        )
        
        cache_key = f"tenants:user:{user_id}:with_roles"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached tenants with roles for user {user_id}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Failed to get cached user tenants: {e}")
        
        with self.db_client.get_session() as session:
            # Build conditions for all principal types
            conditions = []
            
            # Add user condition
            conditions.append(
                and_(
                    TenantPrincipal.principal_id == user_id,
                    TenantPrincipal.principal_type == "IDENTITY_USER"
                )
            )
            
            # Add identity group conditions
            if identity_group_ids:
                for group_id in identity_group_ids:
                    conditions.append(
                        and_(
                            TenantPrincipal.principal_id == group_id,
                            TenantPrincipal.principal_type == "IDENTITY_GROUP"
                        )
                    )
            
            # Add custom group conditions
            if custom_group_ids:
                for group_id in custom_group_ids:
                    conditions.append(
                        and_(
                            TenantPrincipal.principal_id == group_id,
                            TenantPrincipal.principal_type == "CUSTOM_GROUP"
                        )
                    )
            
            # Query to get all tenant principals matching any condition
            query = (
                select(Tenant, TenantPrincipal)
                .join(TenantPrincipal, Tenant.id == TenantPrincipal.tenant_id)
                .where(or_(*conditions))
                .order_by(Tenant.name, TenantPrincipal.role)
            )
            
            results = session.execute(query).all()
            
            # Group by tenant and deduplicate roles
            tenants_dict = {}
            for tenant, principal in results:
                if tenant.id not in tenants_dict:
                    tenants_dict[tenant.id] = {
                        "tenant": tenant,
                        "roles": set()  # Use set for deduplication
                    }
                # Add role to set (automatically deduplicates)
                tenants_dict[tenant.id]["roles"].add(principal.role)
            
            # Convert to response format
            response = []
            for tenant_data in tenants_dict.values():
                tenant_response = self._model_to_response(tenant_data["tenant"])
                # Convert set of roles to sorted list
                roles_list = sorted(list(tenant_data["roles"]))
                response.append({
                    "tenant": tenant_response.model_dump(),
                    "roles": roles_list
                })
            
            logger.info(
                "Retrieved user tenants with roles",
                extra={"user_id": user_id, "tenant_count": len(response)}
            )
            
            # Cache the result
            if self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, response, ttl=300)  # Cache for 5 minutes
                    logger.debug(f"Cached user tenants with roles for {user_id} (TTL: 300s)")
                except Exception as e:
                    logger.warning(f"Failed to cache user tenants: {e}")
            
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
    
    def list_tenant_principals(
        self,
        tenant_id: str
    ) -> dict:
        """
        Get all principals and their roles for a specific tenant.
        
        Args:
            tenant_id: The ID of the tenant
            
        Returns:
            Dict with tenant_id and list of principals with their roles
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Listing all principals for tenant", extra={"tenant_id": tenant_id})
        
        with self.db_client.get_session() as session:
            # Check if tenant exists
            tenant = session.get(Tenant, tenant_id)
            if not tenant:
                logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            # Query all roles for this tenant
            query = (
                select(TenantPrincipal)
                .where(TenantPrincipal.tenant_id == tenant_id)
                .order_by(TenantPrincipal.principal_id, TenantPrincipal.role)
            )
            
            roles = session.execute(query).scalars().all()
            
            # Group roles by principal_id
            principals_dict = {}
            for role in roles:
                if role.principal_id not in principals_dict:
                    principals_dict[role.principal_id] = {
                        "principal_id": role.principal_id,
                        "roles": []
                    }
                principals_dict[role.principal_id]["roles"].append(self._role_to_response(role))
            
            # Convert to list
            principals = list(principals_dict.values())
            
            logger.info(
                "Retrieved tenant principals",
                extra={"tenant_id": tenant_id, "principal_count": len(principals)}
            )
            
            return {
                "tenant_id": tenant_id,
                "principals": principals
            }
    
    def get_principal_roles(
        self,
        tenant_id: str,
        principal_id: str
    ) -> dict:
        """
        Get all roles for a specific principal on a tenant.
        
        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal
            
        Returns:
            Dict with tenant_id, principal_id, and roles list
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info(
            "Getting principal roles",
            extra={"tenant_id": tenant_id, "principal_id": principal_id}
        )
        
        with self.db_client.get_session() as session:
            # Check if tenant exists
            tenant = session.get(Tenant, tenant_id)
            if not tenant:
                logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            # Query roles for this principal on this tenant
            query = (
                select(TenantPrincipal)
                .where(
                    TenantPrincipal.tenant_id == tenant_id,
                    TenantPrincipal.principal_id == principal_id
                )
                .order_by(TenantPrincipal.role)
            )
            
            roles = session.execute(query).scalars().all()
            
            logger.info(
                "Retrieved principal roles",
                extra={"tenant_id": tenant_id, "principal_id": principal_id, "role_count": len(roles)}
            )
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "roles": [self._role_to_response(role) for role in roles]
            }
    
    def set_principal_role(
        self,
        tenant_id: str,
        principal_id: str,
        principal_type: str,
        role: str,
        user_id: str
    ) -> dict:
        """
        Add or update a role for a principal on a tenant.
        
        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            role: The role to assign
            user_id: The ID of the user making the change
            
        Returns:
            Dict with tenant_id, principal_id, and updated roles list
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info(
            "Setting principal role",
            extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "role": role, "user_id": user_id}
        )
        
        with self.db_client.get_session() as session:
            # Check if tenant exists
            tenant = session.get(Tenant, tenant_id)
            if not tenant:
                logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            # Check if role already exists
            query = (
                select(TenantPrincipal)
                .where(
                    TenantPrincipal.tenant_id == tenant_id,
                    TenantPrincipal.principal_id == principal_id,
                    TenantPrincipal.principal_type == principal_type,
                    TenantPrincipal.role == role
                )
            )
            existing_role = session.execute(query).scalar_one_or_none()
            
            if not existing_role:
                # Create new role
                role_id = str(uuid.uuid4())
                new_role = TenantPrincipal(
                    id=role_id,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    principal_type=principal_type,
                    role=role,
                    name=f"{role} for {principal_id} ({principal_type}) on {tenant.name}",
                    description=f"{role} role for {principal_type} principal {principal_id} on tenant {tenant.name}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(new_role)
                logger.info(
                    "Created new principal role",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "role": role, "role_id": role_id}
                )
            else:
                # Update existing role
                existing_role.updated_by = user_id
                logger.info(
                    "Updated existing principal role",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "role": role}
                )
            
            session.flush()
            
            # Get all roles for this principal
            query = (
                select(TenantPrincipal)
                .where(
                    TenantPrincipal.tenant_id == tenant_id,
                    TenantPrincipal.principal_id == principal_id
                )
                .order_by(TenantPrincipal.role)
            )
            roles = session.execute(query).scalars().all()
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "roles": [self._role_to_response(role) for role in roles]
            }
    
    def delete_principal_role(
        self,
        tenant_id: str,
        principal_id: str,
        principal_type: str,
        role: str
    ) -> dict:
        """
        Remove a specific role from a principal on a tenant.
        
        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            role: The role to remove
            
        Returns:
            Dict with tenant_id, principal_id, and remaining roles list
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info(
            "Deleting principal role",
            extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "role": role}
        )
        
        with self.db_client.get_session() as session:
            # Check if tenant exists
            tenant = session.get(Tenant, tenant_id)
            if not tenant:
                logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            # Find and delete the role
            query = (
                select(TenantPrincipal)
                .where(
                    TenantPrincipal.tenant_id == tenant_id,
                    TenantPrincipal.principal_id == principal_id,
                    TenantPrincipal.principal_type == principal_type,
                    TenantPrincipal.role == role
                )
            )
            role_to_delete = session.execute(query).scalar_one_or_none()
            
            if role_to_delete:
                session.delete(role_to_delete)
                logger.info(
                    "Deleted principal role",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "role": role}
                )
            else:
                logger.info(
                    "Role not found, nothing to delete",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "role": role}
                )
            
            session.flush()
            
            # Get remaining roles for this principal
            query = (
                select(TenantPrincipal)
                .where(
                    TenantPrincipal.tenant_id == tenant_id,
                    TenantPrincipal.principal_id == principal_id
                )
                .order_by(TenantPrincipal.role)
            )
            remaining_roles = session.execute(query).scalars().all()
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "roles": [self._role_to_response(role) for role in remaining_roles]
            }
    
    @staticmethod
    def _role_to_response(role: TenantPrincipal):
        """
        Convert a tenant role model to a response object.
        
        Args:
            role: TenantPrincipal SQLAlchemy model
            
        Returns:
            TenantRoleResponse
        """
        from aihub.schema.responses.tenants import TenantRoleResponse
        return TenantRoleResponse(
            id=role.id,
            principal_type=role.principal_type,
            role=role.role,
            name=role.name,
            description=role.description,
            created_at=role.created_at
        )
