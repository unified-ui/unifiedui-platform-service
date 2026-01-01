"""Business logic handlers for development platform operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List, Union

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import DevelopmentPlatform, DevelopmentPlatformMember, DevelopmentPlatformTag, Tag
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.caching.client import CacheClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler

from unifiedui.schema.requests.development_platforms import CreateDevelopmentPlatformRequest, UpdateDevelopmentPlatformRequest
from unifiedui.schema.requests.development_platform_permissions import SetDevelopmentPlatformPermissionRequest
from unifiedui.schema.responses.development_platforms import DevelopmentPlatformResponse
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.principals import (
    PrincipalWithRolesResponse,
    ResourcePrincipalsResponse
)
from unifiedui.exc.development_platforms import DevelopmentPlatformNotFoundError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class DevelopmentPlatformHandler:
    """Handler class for development platform business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None,
        permissions_handler: Optional[ResourcePermissionsHandler] = None,
        tags_handler: Optional[ResourceTagsHandler] = None
    ):
        """
        Initialize the development platform handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
            permissions_handler: Optional central permissions handler
            tags_handler: Optional central tags handler
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self._permissions_handler = permissions_handler
        self._tags_handler = tags_handler

    @property
    def permissions_handler(self) -> ResourcePermissionsHandler:
        """Get the permissions handler, creating one if needed."""
        if self._permissions_handler is None:
            from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
            self._permissions_handler = ResourcePermissionsHandler(self.db_client, self.cache_client)
        return self._permissions_handler

    @property
    def tags_handler(self) -> ResourceTagsHandler:
        """Get the tags handler, creating one if needed."""
        if self._tags_handler is None:
            from unifiedui.handlers.resource_tags import ResourceTagsHandler
            self._tags_handler = ResourceTagsHandler(self.db_client, self.cache_client)
        return self._tags_handler

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
        view: Optional[str] = None,
        use_cache: bool = True
    ) -> Union[List[DevelopmentPlatformResponse], List[QuickListItemResponse]]:
        """
        Get a list of development platforms for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by development platform name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (platforms must have AT LEAST ONE of the tags - OR logic)
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
        
        # Build cache key with order and is_active parameters
        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"development_platforms:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"
        
        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None
        
        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached development platform list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
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
            
            # Filter by tags (platforms must have AT LEAST ONE of the specified tags - OR logic)
            if tag_ids:
                tag_subquery = (
                    select(DevelopmentPlatformTag.development_platform_id)
                    .where(
                        DevelopmentPlatformTag.tenant_id == tenant_id,
                        DevelopmentPlatformTag.tag_id.in_(tag_ids)
                    )
                    .distinct()
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
            
            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=dp.id, name=dp.name) for dp in development_platforms]
            
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
        user_id: str,
        user: ContextIdentityUser
    ) -> DevelopmentPlatformResponse:
        """
        Create a new development platform.
        
        Args:
            tenant_id: The ID of the tenant
            request: Development platform creation data
            user_id: The ID of the user creating the development platform
            user: The authenticated user context (for IDP access)
            
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
            
            # Add creator as admin member using central handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="development_platform",
                tenant_id=tenant_id,
                resource_id=development_platform_id,
                user_id=user_id,
                user=user
            )
            
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
            if request.is_active is not None:
                development_platform.is_active = request.is_active
            
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
        
        try:
            result = self.permissions_handler.list_permissions(
                resource_type="development_platform",
                tenant_id=tenant_id,
                resource_id=development_platform_id,
                use_cache=use_cache
            )
        except ValueError as e:
            raise DevelopmentPlatformNotFoundError(development_platform_id) from e
        
        # Convert to response schema
        principals = [
            PrincipalWithRolesResponse(
                principal_id=p["principal_id"],
                principal_type=p["principal_type"],
                roles=p["roles"],
                mail=p.get("mail"),
                display_name=p.get("display_name"),
                principal_name=p.get("principal_name"),
                description=p.get("description")
            )
            for p in result["principals"]
        ]
        
        return ResourcePrincipalsResponse(
            resource_id=development_platform_id,
            resource_type="development_platform",
            tenant_id=tenant_id,
            principals=principals
        )

    def get_development_platform_permission(
        self,
        tenant_id: str,
        development_platform_id: str,
        principal_id: str
    ) -> PrincipalWithRolesResponse:
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
        
        try:
            result = self.permissions_handler.get_permission(
                resource_type="development_platform",
                tenant_id=tenant_id,
                resource_id=development_platform_id,
                principal_id=principal_id
            )
        except ValueError as e:
            raise DevelopmentPlatformNotFoundError(str(e)) from e
        
        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description")
        )

    def set_development_platform_permission(
        self,
        tenant_id: str,
        development_platform_id: str,
        request: SetDevelopmentPlatformPermissionRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> PrincipalWithRolesResponse:
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
        
        try:
            self.permissions_handler.set_permission(
                resource_type="development_platform",
                tenant_id=tenant_id,
                resource_id=development_platform_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user
            )
        except ValueError as e:
            raise DevelopmentPlatformNotFoundError(str(e)) from e
        
        # Fetch and return the enriched principal data
        return self.get_development_platform_permission(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id,
            principal_id=request.principal_id
        )

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
        
        try:
            self.permissions_handler.delete_permission(
                resource_type="development_platform",
                tenant_id=tenant_id,
                resource_id=development_platform_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission
            )
        except ValueError as e:
            raise DevelopmentPlatformNotFoundError(str(e)) from e

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
