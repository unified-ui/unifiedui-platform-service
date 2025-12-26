"""Business logic handlers for tenant operations using SQLAlchemy."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List
import uuid
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import Tenant, TenantMemberRole, Principal, CustomGroupMember
from unifiedui.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from unifiedui.schema.responses.tenants import TenantResponse
from unifiedui.exc.tenants import TenantNotFoundError
from unifiedui.caching.client import CacheClient
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

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
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        use_cache: bool = True
    ) -> List[TenantResponse]:
        """
        Get a list of tenants.
        
        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by tenant name (case-insensitive partial match)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching (default: True)
            
        Returns:
            List of tenant responses
        """
        logger.info("Listing tenants", extra={"skip": skip, "limit": limit, "name_filter": name_filter})
        
        # Build cache key (without filters - caching only for unfiltered results)
        cache_key = f"tenants:list:skip:{skip}:limit:{limit}"
        
        # Check if any filters are applied
        has_filters = name_filter is not None or order_by is not None
        
        # Check cache (disable caching when any filters are applied)
        cached_data = self._get_from_cache(cache_key, use_cache and not has_filters)
        if cached_data is not None:
            return [TenantResponse(**item) for item in cached_data]
        
        with self.db_client.get_session() as session:
            query = select(Tenant)
            
            # Apply name filter if provided
            if name_filter:
                query = query.where(Tenant.name.ilike(f"%{name_filter}%"))
            
            # Apply ordering if specified
            if order_by and hasattr(Tenant, order_by):
                column = getattr(Tenant, order_by)
                if order_direction == "desc":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            tenants = session.execute(query).scalars().all()
            
            logger.info("Retrieved tenants", extra={"count": len(tenants)})
            result = [self._model_to_response(tenant) for tenant in tenants]
            
            # Cache the result (only when no filters are applied)
            if not has_filters:
                cache_data = [item.model_dump() for item in result]
                self._set_to_cache(cache_key, cache_data, ttl=300)
            
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
        cached_data = self._get_from_cache(cache_key, use_cache)
        if cached_data is not None:
            return TenantResponse(**cached_data)
        
        with self.db_client.get_session() as session:
            tenant = self._validate_tenant_exists(session, tenant_id)
            
            logger.info("Tenant retrieved", extra={"tenant_id": tenant_id})
            result = self._model_to_response(tenant)
            
            # Cache the result
            self._set_to_cache(cache_key, result.model_dump(), ttl=600)
            
            return result

    def create_tenant(
        self,
        request: CreateTenantRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> TenantResponse:
        """
        Create a new tenant and assign the creator as GLOBAL_ADMIN.
        
        Args:
            request: Tenant creation data
            user_id: ID of the user creating the tenant (principal_id)
            user: The authenticated user context (for IDP access)
            
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
            
            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type="IDENTITY_USER",
                user=user
            )
            
            # Create GLOBAL_ADMIN role for the creator
            role_id = str(uuid.uuid4())
            tenant_role = TenantMemberRole(
                id=role_id,
                tenant_id=tenant_id,
                principal_id=user_id,
                role="GLOBAL_ADMIN",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(tenant_role)
            session.flush()
            
            # Commit happens automatically in context manager
            logger.info(
                "Tenant created with GLOBAL_ADMIN role",
                extra={"tenant_id": tenant_id, "user_id": user_id, "role_id": role_id}
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
        cached_data = self._get_from_cache(cache_key, use_cache)
        if cached_data is not None:
            return cached_data
        
        with self.db_client.get_session() as session:
            # Build conditions for all principal IDs
            # We now use the Principal table via JOIN to filter by principal_type
            all_principal_ids = [user_id] + identity_group_ids + custom_group_ids
            
            if not all_principal_ids:
                return []
            
            # Query to get all tenant member roles
            # TenantMemberRole now directly references tenant and principal
            query = (
                select(Tenant, TenantMemberRole)
                .join(TenantMemberRole, Tenant.id == TenantMemberRole.tenant_id)
                .where(TenantMemberRole.principal_id.in_(all_principal_ids))
                .order_by(Tenant.name, TenantMemberRole.role)
            )
            
            results = session.execute(query).all()
            
            # Group by tenant and deduplicate roles
            tenants_dict = {}
            for tenant, role in results:
                if tenant.id not in tenants_dict:
                    tenants_dict[tenant.id] = {
                        "tenant": tenant,
                        "roles": set()  # Use set for deduplication
                    }
                # Add role to set (automatically deduplicates)
                tenants_dict[tenant.id]["roles"].add(role.role)
            
            # Convert to response format
            response = []
            for tenant_data in tenants_dict.values():
                tenant_response = self._model_to_response(tenant_data["tenant"])
                # Convert set of permissions to sorted list
                roles_list = sorted(list(tenant_data["roles"]))
                response.append({
                    "tenant": tenant_response.model_dump(),
                    "roles": roles_list
                })
            
            logger.info(
                "Retrieved user tenants with permissions",
                extra={"user_id": user_id, "tenant_count": len(response)}
            )
            
            # Cache the result
            self._set_to_cache(cache_key, response, ttl=300)
            
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
            
            # Query all member roles for this tenant, joining with Principal
            query = (
                select(TenantMemberRole, Principal)
                .join(
                    Principal,
                    and_(
                        TenantMemberRole.tenant_id == Principal.tenant_id,
                        TenantMemberRole.principal_id == Principal.principal_id
                    )
                )
                .where(TenantMemberRole.tenant_id == tenant_id)
                .order_by(TenantMemberRole.principal_id, TenantMemberRole.role)
            )
            
            results = session.execute(query).all()
            
            # Group roles by principal_id
            principals_dict = {}
            for role, principal in results:
                if role.principal_id not in principals_dict:
                    principals_dict[role.principal_id] = {
                        "principal_id": role.principal_id,
                        "principal_type": principal.principal_type,
                        "roles": []
                    }
                # Just append the role string, not the full response object
                principals_dict[role.principal_id]["roles"].append(role.role)
            
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
            
            # Query member roles, joining with Principal to get principal_type
            query = (
                select(TenantMemberRole, Principal)
                .join(
                    Principal,
                    and_(
                        TenantMemberRole.tenant_id == Principal.tenant_id,
                        TenantMemberRole.principal_id == Principal.principal_id
                    )
                )
                .where(
                    TenantMemberRole.tenant_id == tenant_id,
                    TenantMemberRole.principal_id == principal_id
                )
            )
            
            results = session.execute(query).all()
            
            # Extract principal_type from first result's Principal (all should have same type)
            principal_type = results[0][1].principal_type if results else None
            # Extract just the role strings
            roles = [role.role for role, principal in results]
            
            logger.info(
                "Retrieved principal permissions",
                extra={"tenant_id": tenant_id, "principal_id": principal_id, "permission_count": len(roles)}
            )
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "roles": roles
            }
    
    def set_principal_permission(
        self,
        tenant_id: str,
        principal_id: str,
        principal_type: str,
        permission: str,
        user_id: str,
        user: ContextIdentityUser
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
            self._validate_tenant_exists(session, tenant_id)
            
            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                user=user
            )
            
            # Check if role already exists for this principal
            role_query = (
                select(TenantMemberRole)
                .where(
                    TenantMemberRole.tenant_id == tenant_id,
                    TenantMemberRole.principal_id == principal_id,
                    TenantMemberRole.role == permission
                )
            )
            existing_role = session.execute(role_query).scalar_one_or_none()
            
            if not existing_role:
                # Create new role
                role_id = str(uuid.uuid4())
                role = TenantMemberRole(
                    id=role_id,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    role=permission,
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(role)
                session.flush()
                logger.info(
                    "Created new tenant member role",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "role_id": role_id, "role": permission}
                )
            else:
                logger.info(
                    "Role already exists for this principal",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "role": permission}
                )
            
            # Commit the changes before invalidating cache
            session.commit()
            
            # Invalidate cache for affected users
            self._invalidate_cache_for_principal(session, principal_id, principal_type, user_id)
            
            # Get all roles for this principal
            query = (
                select(TenantMemberRole)
                .where(
                    TenantMemberRole.tenant_id == tenant_id,
                    TenantMemberRole.principal_id == principal_id
                )
                .order_by(TenantMemberRole.role)
            )
            results = session.execute(query).all()
            
            # Extract just the role strings
            roles = [role[0].role for role in results]
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "roles": roles
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
            self._validate_tenant_exists(session, tenant_id)
            
            # Find and delete the specific role
            role_query = (
                select(TenantMemberRole)
                .where(
                    TenantMemberRole.tenant_id == tenant_id,
                    TenantMemberRole.principal_id == principal_id,
                    TenantMemberRole.role == permission
                )
            )
            role = session.execute(role_query).scalar_one_or_none()
            
            if role:
                session.delete(role)
                logger.info(
                    "Deleted principal role",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "role": permission}
                )
            else:
                logger.info(
                    "Role not found, nothing to delete",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type, "role": permission}
                )
            
            session.flush()
            
            # Invalidate cache for affected users (uses admin user_id=None for tracking)
            self._invalidate_cache_for_principal(session, principal_id, principal_type, "")
            
            # Get remaining roles for this principal
            query = (
                select(TenantMemberRole)
                .where(
                    TenantMemberRole.tenant_id == tenant_id,
                    TenantMemberRole.principal_id == principal_id
                )
                .order_by(TenantMemberRole.role)
            )
            remaining_results = session.execute(query).all()
            
            # Extract just the role strings
            roles = [role[0].role for role in remaining_results]
            
            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "roles": roles
            }
    
    def _get_from_cache(self, cache_key: str, use_cache: bool = True):
        """
        Get data from cache if available.
        
        Args:
            cache_key: Cache key to retrieve
            use_cache: Whether to use cache
            
        Returns:
            Cached data or None
        """
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Failed to get from cache {cache_key}: {e}")
        return None
    
    def _set_to_cache(self, cache_key: str, data, ttl: int = 300):
        """
        Set data to cache.
        
        Args:
            cache_key: Cache key to set
            data: Data to cache
            ttl: Time to live in seconds
        """
        if self.cache_client:
            try:
                self.cache_client.client.set(cache_key, data, ttl=ttl)
                logger.debug(f"Cached: {cache_key} (TTL: {ttl}s)")
            except Exception as e:
                logger.warning(f"Failed to cache {cache_key}: {e}")
    
    def _validate_tenant_exists(self, session: Session, tenant_id: str) -> Tenant:
        """
        Validate that a tenant exists.
        
        Args:
            session: Database session
            tenant_id: ID of the tenant
            
        Returns:
            Tenant model
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        tenant = session.get(Tenant, tenant_id)
        if not tenant:
            logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
            raise TenantNotFoundError(tenant_id)
        return tenant
    
    def _invalidate_cache_for_principal(self, session: Session, principal_id: str, principal_type: str, user_id: str):
        """
        Invalidate cache for affected users based on principal type.
        
        Args:
            session: Database session
            principal_id: ID of the principal
            principal_type: Type of principal (IDENTITY_USER, CUSTOM_GROUP, IDENTITY_GROUP)
            user_id: ID of the user making the change
        """
        if not self.cache_client:
            return
        
        try:
            users_to_invalidate = []
            
            if principal_type == "IDENTITY_USER":
                # Direct user - invalidate their cache
                users_to_invalidate.append(principal_id)
            elif principal_type == "CUSTOM_GROUP":
                # Custom group - invalidate cache for all group members who are users
                member_query = (
                    select(CustomGroupMember.principal_id)
                    .join(Principal, and_(
                        CustomGroupMember.tenant_id == Principal.tenant_id,
                        CustomGroupMember.principal_id == Principal.principal_id
                    ))
                    .where(
                        CustomGroupMember.custom_group_id == principal_id,
                        Principal.principal_type == "IDENTITY_USER"
                    )
                )
                members = session.execute(member_query).scalars().all()
                users_to_invalidate.extend(members)
                logger.debug(f"Found {len(members)} users in custom group {principal_id} to invalidate")
            elif principal_type == "IDENTITY_GROUP":
                # Identity group - invalidate all group and permission caches
                pattern = "identity:groups:user:*"
                self.cache_client.client.delete_pattern(pattern)
                pattern = "tenants:user:*:with_permissions"
                self.cache_client.client.delete_pattern(pattern)
                logger.debug(f"Cleared identity group cache patterns for group {principal_id}")
            
            # Invalidate cache for each affected user
            for user_id_to_clear in users_to_invalidate:
                deleted_count = self.cache_client.clear_cache_for_user(user_id_to_clear)
                logger.debug(f"Cleared {deleted_count} cache entries for user {user_id_to_clear}")
            
            # Also clear cache for the user making the change
            self.cache_client.clear_cache_for_user(user_id)
            
            # Invalidate tenant list caches
            self.cache_client.invalidate_tenant_list_cache()
        except Exception as e:
            logger.warning(f"Failed to clear user cache: {e}")
    
    @staticmethod
    def _role_to_response(role: TenantMemberRole, principal: Principal):
        """
        Convert a tenant member role to a role response object.
        
        Args:
            role: TenantMemberRole SQLAlchemy model
            principal: Principal SQLAlchemy model
            
        Returns:
            TenantRoleResponse
        """
        from unifiedui.schema.responses.tenants import TenantRoleResponse
        # Generate a human-readable name from the role value
        role_name = role.role.replace("_", " ").title() if role.role else None
        return TenantRoleResponse(
            id=role.id,
            principal_type=principal.principal_type,
            role=role.role,
            name=role_name,
            description=None,
            created_at=role.created_at
        )
