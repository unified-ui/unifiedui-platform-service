"""Business logic handlers for development platform operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import DevelopmentPlatform, DevelopmentPlatformMember, DevelopmentPlatformTag, Tag
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.caching.client import CacheClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

from unifiedui.schema.requests.development_platforms import CreateDevelopmentPlatformRequest, UpdateDevelopmentPlatformRequest
from unifiedui.schema.requests.development_platform_permissions import SetDevelopmentPlatformPermissionRequest
from unifiedui.schema.responses.development_platforms import DevelopmentPlatformResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.development_platform_permissions import (
    DevelopmentPlatformPermissionResponse,
    DevelopmentPlatformPrincipalsResponse,
    PrincipalPermissionsResponse
)
from unifiedui.exc.development_platforms import DevelopmentPlatformNotFoundError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class DevelopmentPlatformHandler:
    """Handler class for development platform business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None
    ):
        """
        Initialize the development platform handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_development_platforms(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None,
        is_active: Optional[int] = None,
        tag_ids: Optional[List[int]] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        use_cache: bool = True
    ) -> List[DevelopmentPlatformResponse]:
        """
        Get a list of development platforms for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by development platform name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (platforms must have ALL specified tags)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching
            
        Returns:
            List of development platform responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum
        
        logger.info("Listing development platforms", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        # Check if user is admin (has GLOBAL_ADMIN or DEVELOPMENT_PLATFORMS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next(
            (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
            None
        )
        
        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            admin_permissions = [
                TenantRolesEnum.GLOBAL_ADMIN.value,
                TenantRolesEnum.DEVELOPMENT_PLATFORMS_ADMIN.value
            ]
            is_admin = any(perm in user_roles for perm in admin_permissions)
        
        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            # groups now contains both IDENTITY_GROUP and CUSTOM_GROUP with principal_type attribute
            identity_group_ids = [
                g.id for g in user.groups 
                if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
            ]
            custom_group_ids = [
                g.id for g in user.groups 
                if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value
            ]
        
        # Build cache key (without filters - caching only for unfiltered results)
        cache_key = f"development_platforms:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}"
        
        # Check if any filters are applied
        has_filters = name_filter is not None or is_active is not None or tag_ids is not None or order_by is not None
        
        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached development platform list")
                    return [DevelopmentPlatformResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached development platform list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(DevelopmentPlatform).options(
                selectinload(DevelopmentPlatform.tags).selectinload(DevelopmentPlatformTag.tag)
            ).where(DevelopmentPlatform.tenant_id == tenant_id)
            
            # Filter by permissions if not admin
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)
                
                # Subquery for development platforms where user is a member
                member_subquery = (
                    select(DevelopmentPlatformMember.development_platform_id)
                    .where(
                        DevelopmentPlatformMember.tenant_id == tenant_id,
                        DevelopmentPlatformMember.principal_id.in_(principal_ids)
                    )
                    .distinct()
                )
                
                query = query.where(DevelopmentPlatform.id.in_(member_subquery))
            
            if name_filter:
                query = query.where(DevelopmentPlatform.name.ilike(f"%{name_filter}%"))
            
            if is_active is not None:
                query = query.where(DevelopmentPlatform.is_active == bool(is_active))
            
            # Filter by tags (platforms must have ALL specified tags)
            if tag_ids:
                for tag_id in tag_ids:
                    tag_subquery = (
                        select(DevelopmentPlatformTag.development_platform_id)
                        .where(
                            DevelopmentPlatformTag.tenant_id == tenant_id,
                            DevelopmentPlatformTag.tag_id == tag_id
                        )
                    )
                    query = query.where(DevelopmentPlatform.id.in_(tag_subquery))
            
            # Apply ordering if specified
            if order_by and hasattr(DevelopmentPlatform, order_by):
                column = getattr(DevelopmentPlatform, order_by)
                if order_direction == "desc":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            
            query = query.offset(skip).limit(limit)
            development_platforms = session.execute(query).scalars().all()
            
            logger.info("Retrieved development platforms", extra={"count": len(development_platforms)})
            result = [self._model_to_response(dp) for dp in development_platforms]
            
            # Cache the result (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug(f"Cached development platform list")
                except Exception as e:
                    logger.warning(f"Failed to cache development platform list: {e}")
            
            return result

    def get_development_platform(
        self,
        tenant_id: str,
        development_platform_id: str,
        use_cache: bool = True
    ) -> DevelopmentPlatformResponse:
        """
        Get a specific development platform by ID.
        
        Args:
            tenant_id: The ID of the tenant
            development_platform_id: The ID of the development platform
            use_cache: Whether to use caching
            
        Returns:
            Development platform response
            
        Raises:
            DevelopmentPlatformNotFoundError: If development platform not found
        """
        logger.info("Fetching development platform", extra={"tenant_id": tenant_id, "development_platform_id": development_platform_id})
        
        # Build cache key
        cache_key = f"development_platforms:detail:tenant:{tenant_id}:dp:{development_platform_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached development platform")
                    return DevelopmentPlatformResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached development platform: {e}")
        
        with self.db_client.get_session() as session:
            query = select(DevelopmentPlatform).options(
                selectinload(DevelopmentPlatform.tags).selectinload(DevelopmentPlatformTag.tag)
            ).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(query).scalar_one_or_none()
            
            if not development_platform:
                raise DevelopmentPlatformNotFoundError(development_platform_id)
            
            result = self._model_to_response(development_platform)
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug(f"Cached development platform detail")
                except Exception as e:
                    logger.warning(f"Failed to cache development platform: {e}")
            
            return result

    def create_development_platform(
        self,
        tenant_id: str,
        request: CreateDevelopmentPlatformRequest,
        user_id: str
    ) -> DevelopmentPlatformResponse:
        """
        Create a new development platform.
        
        Args:
            tenant_id: The ID of the tenant
            request: Development platform creation data
            user_id: The ID of the user creating the development platform
            
        Returns:
            Created development platform response
        """
        logger.info("Creating development platform", extra={"tenant_id": tenant_id, "dp_name": request.name})
        
        development_platform_id = str(uuid.uuid4())
        
        with self.db_client.get_session() as session:
            # Create development platform
            development_platform = DevelopmentPlatform(
                id=development_platform_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type,
                iframe_url=request.iframe_url,
                config=request.config or {},
                created_by=user_id,
                updated_by=user_id
            )
            session.add(development_platform)
            
            # Add creator as admin member
            member_id = str(uuid.uuid4())
            member = DevelopmentPlatformMember(
                id=member_id,
                tenant_id=tenant_id,
                development_platform_id=development_platform_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER,
                role=PermissionActionEnum.ADMIN,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(member)
            
            session.commit()
            session.refresh(development_platform)
            
            logger.info("Development platform created", extra={"development_platform_id": development_platform_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            
            return self._model_to_response(development_platform)

    def update_development_platform(
        self,
        tenant_id: str,
        development_platform_id: str,
        request: UpdateDevelopmentPlatformRequest,
        user_id: str
    ) -> DevelopmentPlatformResponse:
        """
        Update an existing development platform.
        
        Args:
            tenant_id: The ID of the tenant
            development_platform_id: The ID of the development platform
            request: Development platform update data
            user_id: The ID of the user updating the development platform
            
        Returns:
            Updated development platform response
            
        Raises:
            DevelopmentPlatformNotFoundError: If development platform not found
        """
        logger.info("Updating development platform", extra={"tenant_id": tenant_id, "development_platform_id": development_platform_id})
        
        with self.db_client.get_session() as session:
            query = select(DevelopmentPlatform).options(
                selectinload(DevelopmentPlatform.tags).selectinload(DevelopmentPlatformTag.tag)
            ).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(query).scalar_one_or_none()
            
            if not development_platform:
                raise DevelopmentPlatformNotFoundError(development_platform_id)
            
            # Update fields if provided
            if request.name is not None:
                development_platform.name = request.name
            if request.description is not None:
                development_platform.description = request.description
            if request.type is not None:
                development_platform.type = request.type
            if request.iframe_url is not None:
                development_platform.iframe_url = request.iframe_url
            if request.config is not None:
                development_platform.config = request.config
            
            development_platform.updated_by = user_id
            
            session.commit()
            
            # Re-fetch with tags to ensure they are loaded
            query = select(DevelopmentPlatform).options(
                selectinload(DevelopmentPlatform.tags).selectinload(DevelopmentPlatformTag.tag)
            ).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(query).scalar_one_or_none()
            
            logger.info("Development platform updated", extra={"development_platform_id": development_platform_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, development_platform_id)
            
            return self._model_to_response(development_platform)

    def delete_development_platform(
        self,
        tenant_id: str,
        development_platform_id: str
    ) -> None:
        """
        Delete a development platform.
        
        Args:
            tenant_id: The ID of the tenant
            development_platform_id: The ID of the development platform
            
        Raises:
            DevelopmentPlatformNotFoundError: If development platform not found
        """
        logger.info("Deleting development platform", extra={"tenant_id": tenant_id, "development_platform_id": development_platform_id})
        
        with self.db_client.get_session() as session:
            query = select(DevelopmentPlatform).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(query).scalar_one_or_none()
            
            if not development_platform:
                raise DevelopmentPlatformNotFoundError(development_platform_id)
            
            session.delete(development_platform)
            session.commit()
            
            logger.info("Development platform deleted", extra={"development_platform_id": development_platform_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, development_platform_id)
            self._invalidate_permissions_cache(tenant_id, development_platform_id)

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        if self.cache_client:
            pattern = f"development_platforms:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, development_platform_id: str) -> None:
        """Invalidate detail cache for a development platform."""
        if self.cache_client:
            cache_key = f"development_platforms:detail:tenant:{tenant_id}:dp:{development_platform_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, development_platform_id: str) -> None:
        """Invalidate permissions cache for a development platform."""
        if self.cache_client:
            pattern = f"development_platforms:permissions:tenant:{tenant_id}:dp:{development_platform_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    # ========== Permission Management Methods ==========

    def list_development_platform_permissions(
        self,
        tenant_id: str,
        development_platform_id: str,
        use_cache: bool = True
    ) -> DevelopmentPlatformPrincipalsResponse:
        """
        List all permissions for a development platform, grouped by principal.
        
        Args:
            tenant_id: The ID of the tenant
            development_platform_id: The ID of the development platform
            use_cache: Whether to use caching
            
        Returns:
            Grouped principals with their permissions
            
        Raises:
            DevelopmentPlatformNotFoundError: If development platform not found
        """
        logger.info("Listing development platform permissions", extra={"tenant_id": tenant_id, "development_platform_id": development_platform_id})
        
        # Build cache key
        cache_key = f"development_platforms:permissions:tenant:{tenant_id}:dp:{development_platform_id}:list"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached permissions list")
                    return DevelopmentPlatformPrincipalsResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached permissions: {e}")
        
        with self.db_client.get_session() as session:
            # Verify development platform exists
            dp_query = select(DevelopmentPlatform).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(dp_query).scalar_one_or_none()
            
            if not development_platform:
                raise DevelopmentPlatformNotFoundError(development_platform_id)
            
            # Get all members and their roles
            members_query = (
                select(DevelopmentPlatformMember)
                .where(DevelopmentPlatformMember.development_platform_id == development_platform_id)
            )
            members = session.execute(members_query).scalars().all()
            
            # Group roles by principal
            principals_dict = {}
            for member in members:
                key = (member.principal_id, member.principal_type)
                if key not in principals_dict:
                    principals_dict[key] = {
                        "principal_id": member.principal_id,
                        "principal_type": member.principal_type,
                        "roles": []
                    }
                
                # Add role from member
                principals_dict[key]["roles"].append(member.role)
            
            principals = [
                PrincipalPermissionsResponse(
                    development_platform_id=development_platform_id,
                    tenant_id=tenant_id,
                    **data
                )
                for data in principals_dict.values()
            ]
            
            result = DevelopmentPlatformPrincipalsResponse(
                development_platform_id=development_platform_id,
                tenant_id=tenant_id,
                principals=principals
            )
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug(f"Cached permissions list")
                except Exception as e:
                    logger.warning(f"Failed to cache permissions: {e}")
            
            return result

    def get_development_platform_permission(
        self,
        tenant_id: str,
        development_platform_id: str,
        principal_id: str
    ) -> PrincipalPermissionsResponse:
        """
        Get all permissions for a specific principal on a development platform.
        
        Args:
            tenant_id: The ID of the tenant
            development_platform_id: The ID of the development platform
            principal_id: The ID of the principal
            
        Returns:
            Principal with all their permissions
            
        Raises:
            DevelopmentPlatformNotFoundError: If development platform or permission not found
        """
        logger.info(
            "Getting development platform permission",
            extra={"tenant_id": tenant_id, "development_platform_id": development_platform_id, "principal_id": principal_id}
        )
        
        with self.db_client.get_session() as session:
            # Verify development platform exists
            dp_query = select(DevelopmentPlatform).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(dp_query).scalar_one_or_none()
            
            if not development_platform:
                raise DevelopmentPlatformNotFoundError(development_platform_id)
            
            # Get member for this principal
            member_query = (
                select(DevelopmentPlatformMember)
                .where(
                    DevelopmentPlatformMember.development_platform_id == development_platform_id,
                    DevelopmentPlatformMember.principal_id == principal_id
                )
            )
            members = session.execute(member_query).scalars().all()
            
            if not members:
                raise DevelopmentPlatformNotFoundError(f"No permissions found for principal {principal_id}")
            
            # Collect all roles and get principal_type from first member
            permissions = []
            principal_type = members[0].principal_type
            for member in members:
                if member.role not in permissions:
                    permissions.append(member.role)
            
            return PrincipalPermissionsResponse(
                development_platform_id=development_platform_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                roles=permissions
            )

    def set_development_platform_permission(
        self,
        tenant_id: str,
        development_platform_id: str,
        request: SetDevelopmentPlatformPermissionRequest,
        user_id: str
    ) -> DevelopmentPlatformPermissionResponse:
        """
        Set or update a permission for a principal on a development platform.
        
        Args:
            tenant_id: The ID of the tenant
            development_platform_id: The ID of the development platform
            request: Permission data
            user_id: The ID of the user setting the permission
            
        Returns:
            Created or updated permission
            
        Raises:
            DevelopmentPlatformNotFoundError: If development platform not found
        """
        logger.info(
            "Setting development platform permission",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "principal_id": request.principal_id
            }
        )
        
        with self.db_client.get_session() as session:
            # Verify development platform exists
            dp_query = select(DevelopmentPlatform).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(dp_query).scalar_one_or_none()
            
            if not development_platform:
                raise DevelopmentPlatformNotFoundError(development_platform_id)
            
            # Find or create member with this role
            # Note: A principal can only have ONE role per development platform (enforced by unique constraint)
            # So we need to update or insert
            member_query = (
                select(DevelopmentPlatformMember)
                .where(
                    DevelopmentPlatformMember.development_platform_id == development_platform_id,
                    DevelopmentPlatformMember.principal_id == request.principal_id,
                    DevelopmentPlatformMember.principal_type == request.principal_type.value
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                # Create new member with role
                member_id = str(uuid.uuid4())
                member = DevelopmentPlatformMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    development_platform_id=development_platform_id,
                    principal_id=request.principal_id,
                    principal_type=request.principal_type,
                    role=request.role,
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(member)
                session.commit()
                session.refresh(member)
                
                logger.info("Member with role created", extra={"member_id": member_id})
            elif member.role != request.role:
                # Update existing member's role
                member.role = request.role
                member.updated_by = user_id
                session.commit()
                session.refresh(member)
                
                logger.info("Member role updated", extra={"member_id": member.id})
            else:
                # Member with role already exists
                logger.info("Member with role already exists", extra={"member_id": member.id})
            
            result = DevelopmentPlatformPermissionResponse(
                id=member.id,
                development_platform_id=development_platform_id,
                tenant_id=tenant_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type,
                role=request.role,
                created_at=member.created_at,
                updated_at=member.updated_at
            )
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, development_platform_id)
            
            # Invalidate user cache so list operations reflect new permissions
            if self.cache_client:
                try:
                    if request.principal_type.value == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(request.principal_id)
                        logger.debug(f"Cleared cache for user {request.principal_id} after permission change")
                    # Also clear cache for the user making the change
                    self.cache_client.clear_cache_for_user(user_id)
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")
            
            return result

    def delete_development_platform_permission(
        self,
        tenant_id: str,
        development_platform_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
    ) -> None:
        """
        Delete a specific permission for a principal on a development platform.
        
        Args:
            tenant_id: The ID of the tenant
            development_platform_id: The ID of the development platform
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to delete
            
        Raises:
            DevelopmentPlatformNotFoundError: If development platform or permission not found
        """
        logger.info(
            "Deleting development platform permission",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "principal_id": principal_id,
                "permission": permission
            }
        )
        
        with self.db_client.get_session() as session:
            # Verify development platform exists
            dp_query = select(DevelopmentPlatform).where(
                DevelopmentPlatform.id == development_platform_id,
                DevelopmentPlatform.tenant_id == tenant_id
            )
            development_platform = session.execute(dp_query).scalar_one_or_none()
            
            if not development_platform:
                raise DevelopmentPlatformNotFoundError(development_platform_id)
            
            # Find member with this role
            member_query = (
                select(DevelopmentPlatformMember)
                .where(
                    DevelopmentPlatformMember.development_platform_id == development_platform_id,
                    DevelopmentPlatformMember.principal_id == principal_id,
                    DevelopmentPlatformMember.principal_type == principal_type,
                    DevelopmentPlatformMember.role == permission
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                raise DevelopmentPlatformNotFoundError(f"Member with role {permission} not found for principal {principal_id}")
            
            session.delete(member)
            session.commit()
            
            logger.info("Member with role deleted")
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, development_platform_id)
            
            # Invalidate user cache so list operations reflect removed permissions
            if self.cache_client:
                try:
                    if principal_type == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(principal_id)
                        logger.debug(f"Cleared cache for user {principal_id} after permission removal")
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")

    @staticmethod
    def _model_to_response(development_platform: DevelopmentPlatform) -> DevelopmentPlatformResponse:
        """Convert DevelopmentPlatform model to DevelopmentPlatformResponse."""
        # Extract tags from the development platform's tags relationship
        tags = []
        if hasattr(development_platform, 'tags') and development_platform.tags:
            for dp_tag in development_platform.tags:
                if dp_tag.tag:
                    tags.append(TagSummary(
                        id=dp_tag.tag.id,
                        name=dp_tag.tag.name
                    ))
        
        return DevelopmentPlatformResponse(
            id=development_platform.id,
            tenant_id=development_platform.tenant_id,
            name=development_platform.name,
            description=development_platform.description,
            is_active=development_platform.is_active,
            type=development_platform.type,
            iframe_url=development_platform.iframe_url,
            config=development_platform.config,
            tags=tags,
            created_at=development_platform.created_at,
            updated_at=development_platform.updated_at,
            created_by=development_platform.created_by,
            updated_by=development_platform.updated_by
        )
