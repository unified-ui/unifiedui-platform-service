"""Business logic handlers for application operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List, Union

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import Application, ApplicationMember, ApplicationTag, Tag
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.caching.client import CacheClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler

from unifiedui.schema.requests.applications import CreateApplicationRequest, UpdateApplicationRequest
from unifiedui.schema.requests.application_permissions import SetApplicationPermissionRequest
from unifiedui.schema.responses.applications import ApplicationResponse
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.application_permissions import (
    ApplicationPermissionResponse,
    ApplicationPrincipalsResponse,
    PrincipalPermissionsResponse
)
from unifiedui.exc.applications import ApplicationNotFoundError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class ApplicationHandler:
    """Handler class for application business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None,
        permissions_handler: Optional[ResourcePermissionsHandler] = None,
        tags_handler: Optional[ResourceTagsHandler] = None
    ):
        """
        Initialize the application handler.
        
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

    def list_applications(
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
    ) -> Union[List[ApplicationResponse], List[QuickListItemResponse]]:
        """
        Get a list of applications for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by application name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (applications must have ALL specified tags)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching
            
        Returns:
            List of application responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum
        
        logger.info("Listing applications", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        # Check if user is admin (has GLOBAL_ADMIN or APPLICATIONS_ADMIN)
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
                TenantRolesEnum.APPLICATIONS_ADMIN.value
            ]
            is_admin = any(perm in user_roles for perm in admin_permissions)
        
        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]
        
        # Build cache key with order and is_active parameters
        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"applications:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"
        
        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None
        
        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached application list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [ApplicationResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached application list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Application).options(
                selectinload(Application.tags).selectinload(ApplicationTag.tag)
            ).where(Application.tenant_id == tenant_id)
            
            # Filter by permissions if not admin
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)
                
                # Subquery for applications where user is a member
                member_subquery = (
                    select(ApplicationMember.application_id)
                    .where(
                        ApplicationMember.tenant_id == tenant_id,
                        ApplicationMember.principal_id.in_(principal_ids)
                    )
                    .distinct()
                )
                
                query = query.where(Application.id.in_(member_subquery))
            
            if name_filter:
                query = query.where(Application.name.ilike(f"%{name_filter}%"))
            
            # Filter by is_active status
            if is_active is not None:
                query = query.where(Application.is_active == bool(is_active))
            
            # Filter by tags (applications must have ALL specified tags)
            if tag_ids:
                for tag_id in tag_ids:
                    tag_subquery = (
                        select(ApplicationTag.application_id)
                        .where(
                            ApplicationTag.tenant_id == tenant_id,
                            ApplicationTag.tag_id == tag_id
                        )
                    )
                    query = query.where(Application.id.in_(tag_subquery))
            
            # Apply ordering if specified
            if order_by and hasattr(Application, order_by):
                column = getattr(Application, order_by)
                if order_direction == "desc":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            
            query = query.offset(skip).limit(limit)
            applications = session.execute(query).scalars().all()
            
            logger.info("Retrieved applications", extra={"count": len(applications)})
            
            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=app.id, name=app.name) for app in applications]
            
            result = [self._model_to_response(app) for app in applications]
            
            # Cache the result (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug(f"Cached application list")
                except Exception as e:
                    logger.warning(f"Failed to cache application list: {e}")
            
            return result

    def get_application(
        self,
        tenant_id: str,
        application_id: str,
        use_cache: bool = True
    ) -> ApplicationResponse:
        """
        Get a specific application by ID.
        
        Args:
            tenant_id: The ID of the tenant
            application_id: The ID of the application
            use_cache: Whether to use caching
            
        Returns:
            Application response
            
        Raises:
            ApplicationNotFoundError: If application not found
        """
        logger.info("Fetching application", extra={"tenant_id": tenant_id, "application_id": application_id})
        
        # Build cache key
        cache_key = f"applications:detail:tenant:{tenant_id}:app:{application_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached application")
                    return ApplicationResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached application: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Application).options(
                selectinload(Application.tags).selectinload(ApplicationTag.tag)
            ).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(query).scalar_one_or_none()
            
            if not application:
                raise ApplicationNotFoundError(application_id)
            
            result = self._model_to_response(application)
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug(f"Cached application detail")
                except Exception as e:
                    logger.warning(f"Failed to cache application: {e}")
            
            return result

    def create_application(
        self,
        tenant_id: str,
        request: CreateApplicationRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> ApplicationResponse:
        """
        Create a new application.
        
        Args:
            tenant_id: The ID of the tenant
            request: Application creation data
            user_id: The ID of the user creating the application
            user: The authenticated user context (for IDP access)
            
        Returns:
            Created application response
        """
        logger.info("Creating application", extra={"tenant_id": tenant_id, "app_name": request.name})
        
        application_id = str(uuid.uuid4())
        
        with self.db_client.get_session() as session:
            # Create application
            application = Application(
                id=application_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value,
                config=request.config or {},
                is_active=request.is_active,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(application)
            
            # Add creator as admin member using central handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="application",
                tenant_id=tenant_id,
                resource_id=application_id,
                user_id=user_id,
                user=user
            )
            
            session.commit()
            session.refresh(application)
            
            logger.info("Application created", extra={"application_id": application_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            
            return self._model_to_response(application)

    def update_application(
        self,
        tenant_id: str,
        application_id: str,
        request: UpdateApplicationRequest,
        user_id: str
    ) -> ApplicationResponse:
        """
        Update an existing application.
        
        Args:
            tenant_id: The ID of the tenant
            application_id: The ID of the application
            request: Application update data
            user_id: The ID of the user updating the application
            
        Returns:
            Updated application response
            
        Raises:
            ApplicationNotFoundError: If application not found
        """
        logger.info("Updating application", extra={"tenant_id": tenant_id, "application_id": application_id})
        
        with self.db_client.get_session() as session:
            query = select(Application).options(
                selectinload(Application.tags).selectinload(ApplicationTag.tag)
            ).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(query).scalar_one_or_none()
            
            if not application:
                raise ApplicationNotFoundError(application_id)
            
            # Update fields if provided
            if request.name is not None:
                application.name = request.name
            if request.description is not None:
                application.description = request.description
            if request.type is not None:
                application.type = request.type.value
            if request.config is not None:
                application.config = request.config
            if request.is_active is not None:
                application.is_active = request.is_active
            
            application.updated_by = user_id
            
            session.commit()
            session.refresh(application)
            
            # Re-fetch with tags for response
            query = select(Application).options(
                selectinload(Application.tags).selectinload(ApplicationTag.tag)
            ).where(Application.id == application_id)
            application = session.execute(query).scalar_one()
            
            logger.info("Application updated", extra={"application_id": application_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, application_id)
            
            return self._model_to_response(application)

    def delete_application(
        self,
        tenant_id: str,
        application_id: str
    ) -> None:
        """
        Delete an application.
        
        Args:
            tenant_id: The ID of the tenant
            application_id: The ID of the application
            
        Raises:
            ApplicationNotFoundError: If application not found
        """
        logger.info("Deleting application", extra={"tenant_id": tenant_id, "application_id": application_id})
        
        with self.db_client.get_session() as session:
            query = select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(query).scalar_one_or_none()
            
            if not application:
                raise ApplicationNotFoundError(application_id)
            
            session.delete(application)
            session.commit()
            
            logger.info("Application deleted", extra={"application_id": application_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, application_id)
            self._invalidate_permissions_cache(tenant_id, application_id)

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        if self.cache_client:
            pattern = f"applications:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, application_id: str) -> None:
        """Invalidate detail cache for an application."""
        if self.cache_client:
            cache_key = f"applications:detail:tenant:{tenant_id}:app:{application_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, application_id: str) -> None:
        """Invalidate permissions cache for an application."""
        if self.cache_client:
            pattern = f"applications:permissions:tenant:{tenant_id}:app:{application_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    # ========== Permission Management Methods ==========

    def list_application_permissions(
        self,
        tenant_id: str,
        application_id: str,
        use_cache: bool = True
    ) -> ApplicationPrincipalsResponse:
        """
        List all permissions for an application, grouped by principal.
        
        Args:
            tenant_id: The ID of the tenant
            application_id: The ID of the application
            use_cache: Whether to use caching
            
        Returns:
            Grouped principals with their permissions
            
        Raises:
            ApplicationNotFoundError: If application not found
        """
        logger.info("Listing application permissions", extra={"tenant_id": tenant_id, "application_id": application_id})
        
        try:
            result = self.permissions_handler.list_permissions(
                resource_type="application",
                tenant_id=tenant_id,
                resource_id=application_id,
                use_cache=use_cache
            )
        except ValueError as e:
            raise ApplicationNotFoundError(application_id) from e
        
        # Convert to response schema
        principals = [
            PrincipalPermissionsResponse(
                application_id=application_id,
                tenant_id=tenant_id,
                principal_id=p["principal_id"],
                principal_type=p["principal_type"],
                roles=p["roles"]
            )
            for p in result["principals"]
        ]
        
        return ApplicationPrincipalsResponse(
            application_id=application_id,
            tenant_id=tenant_id,
            principals=principals
        )

    def get_application_permission(
        self,
        tenant_id: str,
        application_id: str,
        principal_id: str
    ) -> PrincipalPermissionsResponse:
        """
        Get all permissions for a specific principal on an application.
        
        Args:
            tenant_id: The ID of the tenant
            application_id: The ID of the application
            principal_id: The ID of the principal
            
        Returns:
            Principal with all their permissions
            
        Raises:
            ApplicationNotFoundError: If application or permission not found
        """
        logger.info(
            "Getting application permission",
            extra={"tenant_id": tenant_id, "application_id": application_id, "principal_id": principal_id}
        )
        
        try:
            result = self.permissions_handler.get_permission(
                resource_type="application",
                tenant_id=tenant_id,
                resource_id=application_id,
                principal_id=principal_id
            )
        except ValueError as e:
            raise ApplicationNotFoundError(str(e)) from e
        
        return PrincipalPermissionsResponse(
            application_id=application_id,
            tenant_id=tenant_id,
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"]
        )

    def set_application_permission(
        self,
        tenant_id: str,
        application_id: str,
        request: SetApplicationPermissionRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> ApplicationPermissionResponse:
        """
        Set or update a permission for a principal on an application.
        
        Args:
            tenant_id: The ID of the tenant
            application_id: The ID of the application
            request: Permission data
            user_id: The ID of the user setting the permission
            
        Returns:
            Created or updated permission
            
        Raises:
            ApplicationNotFoundError: If application not found
        """
        logger.info(
            "Setting application permission",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "principal_id": request.principal_id
            }
        )
        
        try:
            result = self.permissions_handler.set_permission(
                resource_type="application",
                tenant_id=tenant_id,
                resource_id=application_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user
            )
        except ValueError as e:
            raise ApplicationNotFoundError(str(e)) from e
        
        return ApplicationPermissionResponse(
            id=result["id"],
            application_id=application_id,
            tenant_id=tenant_id,
            principal_id=result["principal_id"],
            principal_type=request.principal_type,
            role=request.role,
            created_at=result["created_at"],
            updated_at=result["updated_at"]
        )

    def delete_application_permission(
        self,
        tenant_id: str,
        application_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
    ) -> None:
        """
        Delete a specific permission for a principal on an application.
        
        Args:
            tenant_id: The ID of the tenant
            application_id: The ID of the application
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to delete
            
        Raises:
            ApplicationNotFoundError: If application or permission not found
        """
        logger.info(
            "Deleting application permission",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "principal_id": principal_id,
                "permission": permission
            }
        )
        
        try:
            self.permissions_handler.delete_permission(
                resource_type="application",
                tenant_id=tenant_id,
                resource_id=application_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission
            )
        except ValueError as e:
            raise ApplicationNotFoundError(str(e)) from e

    @staticmethod
    def _model_to_response(application: Application) -> ApplicationResponse:
        """Convert Application model to ApplicationResponse."""
        # Extract tags from the application's tags relationship
        tags = []
        if hasattr(application, 'tags') and application.tags:
            for app_tag in application.tags:
                if app_tag.tag:
                    tags.append(TagSummary(
                        id=app_tag.tag.id,
                        name=app_tag.tag.name
                    ))
        
        return ApplicationResponse(
            id=application.id,
            tenant_id=application.tenant_id,
            name=application.name,
            description=application.description,
            type=application.type,
            is_active=application.is_active,
            config=application.config,
            tags=tags,
            created_at=application.created_at,
            updated_at=application.updated_at,
            created_by=application.created_by,
            updated_by=application.updated_by
        )
