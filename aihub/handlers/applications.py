"""Business logic handlers for application operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import select, or_

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import Application, ApplicationMember
from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from aihub.caching.client import CacheClient

if TYPE_CHECKING:
    from aihub.core.identity.users import ContextIdentityUser

from aihub.schema.requests.applications import CreateApplicationRequest, UpdateApplicationRequest
from aihub.schema.requests.application_permissions import SetApplicationPermissionRequest
from aihub.schema.responses.applications import ApplicationResponse
from aihub.schema.responses.application_permissions import (
    ApplicationPermissionResponse,
    ApplicationPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.applications import ApplicationNotFoundError
from aihub.logger import get_logger

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
        use_cache: bool = True
    ) -> List[ApplicationResponse]:
        """
        Get a list of applications for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by application name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            use_cache: Whether to use caching
            
        Returns:
            List of application responses
        """
        from aihub.core.database.enums import TenantPermissionEnum
        
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
                TenantPermissionEnum.GLOBAL_ADMIN.value,
                TenantPermissionEnum.APPLICATIONS_ADMIN.value
            ]
            is_admin = any(perm in user_roles for perm in admin_permissions)
        
        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]
        
        # Build cache key
        filter_key = name_filter or "all"
        active_key = "all" if is_active is None else str(is_active)
        cache_key = f"applications:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:filter:{filter_key}:active:{active_key}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached application list")
                    return [ApplicationResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached application list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Application).where(Application.tenant_id == tenant_id)
            
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
            
            query = query.offset(skip).limit(limit)
            applications = session.execute(query).scalars().all()
            
            logger.info("Retrieved applications", extra={"count": len(applications)})
            result = [self._model_to_response(app) for app in applications]
            
            # Cache the result
            if use_cache and self.cache_client:
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
            query = select(Application).where(
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
        user_id: str
    ) -> ApplicationResponse:
        """
        Create a new application.
        
        Args:
            tenant_id: The ID of the tenant
            request: Application creation data
            user_id: The ID of the user creating the application
            
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
                config=request.config or {},
                created_by=user_id,
                updated_by=user_id
            )
            session.add(application)
            
            # Add creator as admin member
            member_id = str(uuid.uuid4())
            member = ApplicationMember(
                id=member_id,
                tenant_id=tenant_id,
                application_id=application_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER,
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
            query = select(Application).where(
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
            if request.config is not None:
                application.config = request.config
            
            application.updated_by = user_id
            
            session.commit()
            session.refresh(application)
            
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
            principal_type = members[0].principal_type
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
        user_id: str
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
            
            # Find or create member with this role
            # Note: A principal can only have ONE role per application (enforced by unique constraint)
            # So we need to update or insert
            member_query = (
                select(ApplicationMember)
                .where(
                    ApplicationMember.application_id == application_id,
                    ApplicationMember.principal_id == request.principal_id,
                    ApplicationMember.principal_type == request.principal_type.value
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
                    ApplicationMember.principal_type == principal_type,
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
        return ApplicationResponse(
            id=application.id,
            tenant_id=application.tenant_id,
            name=application.name,
            description=application.description,
            is_active=application.is_active,
            config=application.config,
            created_at=application.created_at,
            updated_at=application.updated_at,
            created_by=application.created_by,
            updated_by=application.updated_by
        )
