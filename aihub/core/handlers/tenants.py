"""Business logic handlers for tenant operations using SQLAlchemy."""
from typing import Optional, List
import uuid
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import Tenant, TenantMember, TenantMemberPermission
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
        name_filter: Optional[str] = None,
        use_cache: bool = True
    ) -> List[TenantResponse]:
        """
        Get a list of tenants.
        
        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by tenant name (case-insensitive partial match)
            use_cache: Whether to use caching (default: True)
            
        Returns:
            List of tenant responses
        """
        logger.info("Listing tenants", extra={"skip": skip, "limit": limit, "name_filter": name_filter})
        
        # Build cache key
        filter_key = name_filter or "all"
        cache_key = f"tenants:list:skip:{skip}:limit:{limit}:filter:{filter_key}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached tenant list (skip={skip}, limit={limit}, filter={filter_key})")
                    return [TenantResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached tenant list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Tenant)
            
            # Apply name filter if provided
            if name_filter:
                query = query.where(Tenant.name.ilike(f"%{name_filter}%"))
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            tenants = session.execute(query).scalars().all()
            
            logger.info("Retrieved tenants", extra={"count": len(tenants)})
            result = [self._model_to_response(tenant) for tenant in tenants]
            
            # Cache the result
            if self.cache_client:
                try:
                    cache_data = [item.model_dump() for item in result]
                    self.cache_client.client.set(cache_key, cache_data, ttl=300)  # Cache for 5 minutes
                    logger.debug(f"Cached tenant list (TTL: 300s)")
                except Exception as e:
                    logger.warning(f"Failed to cache tenant list: {e}")
            
            return result

    def get_tenant(self, tenant_id: str, use_cache: bool = True) -> TenantResponse:
        """
        Get a specific tenant by ID.
        
        Args:
            tenant_id: The ID of the tenant
            use_cache: Whether to use caching (default: True)
            
        Returns:
            Tenant response
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Fetching tenant", extra={"tenant_id": tenant_id})
        
        # Build cache key
        cache_key = f"tenants:detail:{tenant_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached tenant {tenant_id}")
                    return TenantResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached tenant: {e}")
        
        with self.db_client.get_session() as session:
            tenant = session.get(Tenant, tenant_id)
            
            if not tenant:
                logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            logger.info("Tenant retrieved", extra={"tenant_id": tenant_id})
            result = self._model_to_response(tenant)
            
            # Cache the result
            if self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=600)  # Cache for 10 minutes
                    logger.debug(f"Cached tenant {tenant_id} (TTL: 600s)")
                except Exception as e:
                    logger.warning(f"Failed to cache tenant: {e}")
            
            return result

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
            session.flush()  # Flush to get the tenant ID for the member
            
            # Create tenant member for the creator
            member_id = str(uuid.uuid4())
            tenant_member = TenantMember(
                id=member_id,
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type="IDENTITY_USER",
                name=f"Member: {user_id}",
                description=f"Tenant member for user {user_id} on tenant {request.name}",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(tenant_member)
            session.flush()  # Flush to get the member ID for the permission
            
            # Create GLOBAL_ADMIN permission for the member
            permission_id = str(uuid.uuid4())
            tenant_permission = TenantMemberPermission(
                id=permission_id,
                tenant_member_id=member_id,
                permission="GLOBAL_ADMIN",
                name=f"GLOBAL_ADMIN permission",
                description=f"Global administrator permission for user {user_id} on tenant {request.name}",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(tenant_permission)
            
            # Commit happens automatically in context manager
            logger.info(
                "Tenant created with GLOBAL_ADMIN permission",
                extra={"tenant_id": tenant_id, "user_id": user_id, "member_id": member_id, "permission_id": permission_id}
            )
            
            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_tenant_list_cache()
                    # Clear user cache since permissions changed
                    self.cache_client.clear_cache_for_user(user_id)
                    logger.debug(f"Invalidated tenant list cache and user cache for {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
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
            
            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_tenant_list_cache()
                    # Invalidate specific tenant cache
                    self.cache_client.invalidate_tenant_cache(tenant_id)
                    logger.debug(f"Invalidated caches for tenant {tenant_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
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
            
            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_tenant_list_cache()
                    # Invalidate specific tenant cache
                    self.cache_client.invalidate_tenant_cache(tenant_id)
                    # Clear all user caches (all users who had access to this tenant)
                    pattern = "tenants:user:*:with_permissions"
                    self.cache_client.client.delete_pattern(pattern)
                    logger.debug(f"Invalidated caches for deleted tenant {tenant_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            logger.info("Tenant deleted", extra={"tenant_id": tenant_id})
    
    def get_user_tenants_with_permissions(
        self,
        user_id: str,
        identity_group_ids: List[str],
        custom_group_ids: List[str],
        use_cache: bool = True
    ) -> List[dict]:
        """
        Get all tenants and permissions for a user based on their user ID, identity groups, and custom groups.
        
        Args:
            user_id: The identity user ID
            identity_group_ids: List of identity group IDs the user belongs to
            custom_group_ids: List of custom group IDs the user belongs to
            use_cache: Whether to use caching (default: True)
            
        Returns:
            List of dicts with 'tenant' and 'permissions' keys, where permissions are deduplicated
        """
        logger.info(
            "Getting user tenants with permissions",
            extra={
                "user_id": user_id,
                "identity_groups_count": len(identity_group_ids),
                "custom_groups_count": len(custom_group_ids)
            }
        )
        
        cache_key = f"tenants:user:{user_id}:with_permissions"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached tenants with permissions for user {user_id}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Failed to get cached user tenants: {e}")
        
        with self.db_client.get_session() as session:
            # Build conditions for all principal types
            conditions = []
            
            # Add user condition
            conditions.append(
                and_(
                    TenantMember.principal_id == user_id,
                    TenantMember.principal_type == "IDENTITY_USER"
                )
            )
            
            # Add identity group conditions
            if identity_group_ids:
                for group_id in identity_group_ids:
                    conditions.append(
                        and_(
                            TenantMember.principal_id == group_id,
                            TenantMember.principal_type == "IDENTITY_GROUP"
                        )
                    )
            
            # Add custom group conditions
            if custom_group_ids:
                for group_id in custom_group_ids:
                    conditions.append(
                        and_(
                            TenantMember.principal_id == group_id,
                            TenantMember.principal_type == "CUSTOM_GROUP"
                        )
                    )
            
            # Query to get all tenant members and their permissions matching any condition
            query = (
                select(Tenant, TenantMember, TenantMemberPermission)
                .join(TenantMember, Tenant.id == TenantMember.tenant_id)
                .join(TenantMemberPermission, TenantMember.id == TenantMemberPermission.tenant_member_id)
                .where(or_(*conditions))
                .order_by(Tenant.name, TenantMemberPermission.permission)
            )
            
            results = session.execute(query).all()
            
            # Group by tenant and deduplicate permissions
            tenants_dict = {}
            for tenant, member, permission in results:
                if tenant.id not in tenants_dict:
                    tenants_dict[tenant.id] = {
                        "tenant": tenant,
                        "permissions": set()  # Use set for deduplication
                    }
                # Add permission to set (automatically deduplicates)
                tenants_dict[tenant.id]["permissions"].add(permission.permission)
            
            # Convert to response format
            response = []
            for tenant_data in tenants_dict.values():
                tenant_response = self._model_to_response(tenant_data["tenant"])
                # Convert set of permissions to sorted list
                permissions_list = sorted(list(tenant_data["permissions"]))
                response.append({
                    "tenant": tenant_response.model_dump(),
                    "permissions": permissions_list
                })
            
            logger.info(
                "Retrieved user tenants with permissions",
                extra={"user_id": user_id, "tenant_count": len(response)}
            )
            
            # Cache the result
            if self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, response, ttl=300)  # Cache for 5 minutes
                    logger.debug(f"Cached user tenants with permissions for {user_id} (TTL: 300s)")
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
            
            # Query all members and their permissions for this tenant
            query = (
                select(TenantMember, TenantMemberPermission)
                .join(TenantMemberPermission, TenantMember.id == TenantMemberPermission.tenant_member_id)
                .where(TenantMember.tenant_id == tenant_id)
                .order_by(TenantMember.principal_id, TenantMemberPermission.permission)
            )
            
            results = session.execute(query).all()
            
            # Group permissions by principal_id
            principals_dict = {}
            for member, permission in results:
                if member.principal_id not in principals_dict:
                    principals_dict[member.principal_id] = {
                        "principal_id": member.principal_id,
                        "permissions": []
                    }
                principals_dict[member.principal_id]["permissions"].append(self._permission_to_response(permission))
            
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
    
    def get_principal_permissions(
        self,
        tenant_id: str,
        principal_id: str
    ) -> dict:
        """
        Get all permissions for a specific principal on a tenant.
        
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
            
            # Query member and their permissions
            query = (
                select(TenantMember)
                .where(
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.principal_id == principal_id
                )
            )
            
            member = session.execute(query).scalar_one_or_none()
            
            if member:
                # Get permissions for this member
                query = (
                    select(TenantMemberPermission)
                    .where(TenantMemberPermission.tenant_member_id == member.id)
                    .order_by(TenantMemberPermission.permission)
                )
                permissions = session.execute(query).scalars().all()
            else:
                permissions = []
            
            logger.info(
                "Retrieved principal permissions",
                extra={"tenant_id": tenant_id, "principal_id": principal_id, "permission_count": len(permissions)}
            )
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "permissions": [self._permission_to_response(permission) for permission in permissions]
            }
    
    def set_principal_permission(
        self,
        tenant_id: str,
        principal_id: str,
        principal_type: str,
        permission: str,
        user_id: str
    ) -> dict:
        """
        Add or update a permission for a principal on a tenant.
        
        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            permission: The permission to assign
            user_id: The ID of the user making the change
            
        Returns:
            Dict with tenant_id, principal_id, and updated roles list
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info(
            "Setting principal permission",
            extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "permission": permission, "user_id": user_id}
        )
        
        with self.db_client.get_session() as session:
            # Check if tenant exists
            tenant = session.get(Tenant, tenant_id)
            if not tenant:
                logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            # Check if member exists
            query = (
                select(TenantMember)
                .where(
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.principal_id == principal_id,
                    TenantMember.principal_type == principal_type
                )
            )
            member = session.execute(query).scalar_one_or_none()
            
            if not member:
                # Create new member
                member_id = str(uuid.uuid4())
                member = TenantMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    principal_type=principal_type,
                    name=f"Member: {principal_id} ({principal_type})",
                    description=f"Tenant member for {principal_type} {principal_id} on tenant {tenant.name}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(member)
                session.flush()  # Flush to get member ID
                logger.info(
                    "Created new tenant member",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "member_id": member_id}
                )
            
            # Check if permission already exists
            query = (
                select(TenantMemberPermission)
                .where(
                    TenantMemberPermission.tenant_member_id == member.id,
                    TenantMemberPermission.permission == permission
                )
            )
            existing_permission = session.execute(query).scalar_one_or_none()
            
            if not existing_permission:
                # Create new permission
                permission_id = str(uuid.uuid4())
                new_permission = TenantMemberPermission(
                    id=permission_id,
                    tenant_member_id=member.id,
                    permission=permission,
                    name=f"{permission} permission",
                    description=f"{permission} permission for {principal_type} {principal_id} on tenant {tenant.name}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(new_permission)
                logger.info(
                    "Created new permission",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "permission": permission, "permission_id": permission_id}
                )
            
            session.flush()
            
            # Invalidate user cache if this is a user principal
            if self.cache_client:
                try:
                    if principal_type == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(principal_id)
                        logger.debug(f"Cleared cache for user {principal_id} after permission change")
                    # Also clear cache for the user making the change
                    self.cache_client.clear_cache_for_user(user_id)
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")
            
            # Get all permissions for this member
            query = (
                select(TenantMemberPermission)
                .where(TenantMemberPermission.tenant_member_id == member.id)
                .order_by(TenantMemberPermission.permission)
            )
            permissions = session.execute(query).scalars().all()
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "permissions": [self._permission_to_response(permission) for permission in permissions]
            }
    
    def delete_principal_permission(
        self,
        tenant_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
    ) -> dict:
        """
        Remove a specific permission from a principal on a tenant.
        
        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            permission: The permission to remove
            
        Returns:
            Dict with tenant_id, principal_id, and remaining roles list
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info(
            "Deleting principal permission",
            extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "permission": permission}
        )
        
        with self.db_client.get_session() as session:
            # Check if tenant exists
            tenant = session.get(Tenant, tenant_id)
            if not tenant:
                logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)
            
            # Find the member
            query = (
                select(TenantMember)
                .where(
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.principal_id == principal_id,
                    TenantMember.principal_type == principal_type
                )
            )
            member = session.execute(query).scalar_one_or_none()
            
            if member:
                # Find and delete the permission
                query = (
                    select(TenantMemberPermission)
                    .where(
                        TenantMemberPermission.tenant_member_id == member.id,
                        TenantMemberPermission.permission == permission
                    )
                )
                permission_to_delete = session.execute(query).scalar_one_or_none()
                
                if permission_to_delete:
                    session.delete(permission_to_delete)
                    logger.info(
                        "Deleted principal permission",
                        extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "permission": permission}
                    )
                else:
                    logger.info(
                        "Permission not found, nothing to delete",
                        extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "permission": permission}
                    )
                
                session.flush()
                
                # Get remaining permissions for this member
                query = (
                    select(TenantMemberPermission)
                    .where(TenantMemberPermission.tenant_member_id == member.id)
                    .order_by(TenantMemberPermission.permission)
                )
                remaining_permissions = session.execute(query).scalars().all()
            else:
                logger.info(
                    "Member not found, nothing to delete",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type}
                )
                remaining_permissions = []
            
            # Invalidate user cache if this is a user principal
            if self.cache_client:
                try:
                    if principal_type == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(principal_id)
                        logger.debug(f"Cleared cache for user {principal_id} after permission removal")
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "permissions": [self._permission_to_response(perm) for perm in remaining_permissions]
            }
    
    @staticmethod
    def _permission_to_response(permission: TenantMemberPermission):
        """
        Convert a tenant member permission model to a response object.
        
        Args:
            permission: TenantMemberPermission SQLAlchemy model
            
        Returns:
            TenantPermissionResponse
        """
        from aihub.schema.responses.tenants import TenantPermissionResponse
        return TenantPermissionResponse(
            id=permission.id,
            principal_type="",  # Not available at permission level
            permission=permission.permission,
            name=permission.name,
            description=permission.description,
            created_at=permission.created_at
        )
