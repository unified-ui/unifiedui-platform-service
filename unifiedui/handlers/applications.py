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
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class ApplicationHandler:
    """Handler class for application business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None
    ):
        """
        Initialize the application handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

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
        
        # Build cache key (without filters - caching only for unfiltered results)
        view_key = view or "full"
        cache_key = f"applications:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}"
        
        # Check if any filters are applied
        has_filters = name_filter is not None or is_active is not None or tag_ids is not None or order_by is not None
        
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
            
            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                user=user
            )
            
            # Add creator as admin member
            member_id = str(uuid.uuid4())
            member = ApplicationMember(
                id=member_id,
                tenant_id=tenant_id,
                application_id=application_id,
                principal_id=user_id,
                role=PermissionActionEnum.ADMIN,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(member)
            
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
        
        # Build cache key
        cache_key = f"applications:permissions:tenant:{tenant_id}:app:{application_id}:list"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached permissions list")
                    return ApplicationPrincipalsResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached permissions: {e}")
        
        with self.db_client.get_session() as session:
            # Verify application exists
            app_query = select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(app_query).scalar_one_or_none()
            
            if not application:
                raise ApplicationNotFoundError(application_id)
            
            # Get all members and their roles
            members_query = (
                select(ApplicationMember)
                .where(ApplicationMember.application_id == application_id)
            )
            members = session.execute(members_query).scalars().all()
            
            # Group roles by principal
            principals_dict = {}
            for member in members:
                key = (member.principal_id, member.principal.principal_type)
                if key not in principals_dict:
                    principals_dict[key] = {
                        "principal_id": member.principal_id,
                        "principal_type": member.principal.principal_type,
                        "roles": []
                    }
                
                # Add role from member
                principals_dict[key]["roles"].append(member.role)
            
            principals = [
                PrincipalPermissionsResponse(
                    application_id=application_id,
                    tenant_id=tenant_id,
                    **data
                )
                for data in principals_dict.values()
            ]
            
            result = ApplicationPrincipalsResponse(
                application_id=application_id,
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
        
        with self.db_client.get_session() as session:
            # Verify application exists
            app_query = select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(app_query).scalar_one_or_none()
            
            if not application:
                raise ApplicationNotFoundError(application_id)
            
            # Get member for this principal
            member_query = (
                select(ApplicationMember)
                .where(
                    ApplicationMember.application_id == application_id,
                    ApplicationMember.principal_id == principal_id
                )
            )
            members = session.execute(member_query).scalars().all()
            
            if not members:
                raise ApplicationNotFoundError(f"No permissions found for principal {principal_id}")
            
            # Collect all roles and get principal_type from first member
            permissions = []
            principal_type = members[0].principal.principal_type
            for member in members:
                if member.role not in permissions:
                    permissions.append(member.role)
            
            return PrincipalPermissionsResponse(
                application_id=application_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                roles=permissions
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
        
        with self.db_client.get_session() as session:
            # Verify application exists
            app_query = select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(app_query).scalar_one_or_none()
            
            if not application:
                raise ApplicationNotFoundError(application_id)
            
            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                user=user
            )
            
            # Find or create member with this role
            # Note: A principal can only have ONE role per application (enforced by unique constraint)
            # So we need to update or insert
            member_query = (
                select(ApplicationMember)
                .where(
                    ApplicationMember.application_id == application_id,
                    ApplicationMember.principal_id == request.principal_id
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                # Create new member with role
                member_id = str(uuid.uuid4())
                member = ApplicationMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    application_id=application_id,
                    principal_id=request.principal_id,
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
            
            result = ApplicationPermissionResponse(
                id=member.id,
                application_id=application_id,
                tenant_id=tenant_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type,
                role=request.role,
                created_at=member.created_at,
                updated_at=member.updated_at
            )
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, application_id)
            
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
        
        with self.db_client.get_session() as session:
            # Verify application exists
            app_query = select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(app_query).scalar_one_or_none()
            
            if not application:
                raise ApplicationNotFoundError(application_id)
            
            # Find member with this role
            member_query = (
                select(ApplicationMember)
                .where(
                    ApplicationMember.application_id == application_id,
                    ApplicationMember.principal_id == principal_id,
                    ApplicationMember.role == permission
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                raise ApplicationNotFoundError(f"Member with role {permission} not found for principal {principal_id}")
            
            session.delete(member)
            session.commit()
            
            logger.info("Member with role deleted")
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, application_id)
            
            # Invalidate user cache so list operations reflect removed permissions
            if self.cache_client:
                try:
                    if principal_type == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(principal_id)
                        logger.debug(f"Cleared cache for user {principal_id} after permission removal")
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")

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
