"""Business logic handlers for external app operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import ExternalApp, ExternalAppMember, ExternalAppTag, RecentVisit
from unifiedui.handlers.cache_utils import ResourceCacheInvalidator
from unifiedui.handlers.permission_resolver import (
    check_is_admin,
    get_principal_ids,
    resolve_my_permission,
    resolve_my_permissions_bulk,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler
    from unifiedui.schema.requests.external_apps import CreateExternalAppRequest, UpdateExternalAppRequest
    from unifiedui.schema.requests.permissions import SetResourcePermissionRequest

from unifiedui.exc.external_apps import ExternalAppAlreadyExistsError, ExternalAppNotFoundError
from unifiedui.handlers.validators.external_app_config import ExternalAppConfigValidatorFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.external_apps import ExternalAppResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.tags import TagSummary

logger = get_logger(__name__)


class ExternalAppHandler:
    """Handler class for external app business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
    ):
        """Initialize the external app handler.

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
        self._cache = ResourceCacheInvalidator(cache_client, "external_apps", "ea")

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

    def list_external_apps(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        tag_ids: list[int] | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
        id_list: list[str] | None = None,
    ) -> list[ExternalAppResponse]:
        """Get a list of external apps for a tenant (filtered by permissions).

        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by app name
            tag_ids: Optional list of tag IDs to filter by (OR logic)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching
            id_list: Optional list of IDs to filter by

        Returns:
            List of external app responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing external apps", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        user_id = user.identity.get_id()
        is_admin = check_is_admin(
            user, tenant_id, [TenantRolesEnum.TENANT_GLOBAL_ADMIN, TenantRolesEnum.EXTERNAL_APPS_ADMIN]
        )

        principal_ids: list[str] = []
        if not is_admin:
            identity_group_ids = [
                g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
            ]
            custom_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]
            principal_ids = [user_id]
            if identity_group_ids:
                principal_ids.extend(identity_group_ids)
            if custom_group_ids:
                principal_ids.extend(custom_group_ids)

        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        cache_key = f"external_apps:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:order:{order_key}"
        has_filters = name_filter is not None or tag_ids is not None or id_list is not None

        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached external app list")
                    return [ExternalAppResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached external app list: %s", e)

        with self.db_client.get_session() as session:
            query = (
                select(ExternalApp)
                .options(selectinload(ExternalApp.tags).selectinload(ExternalAppTag.tag))
                .where(ExternalApp.tenant_id == tenant_id)
            )

            if not is_admin:
                member_subquery = (
                    select(ExternalAppMember.external_app_id)
                    .where(ExternalAppMember.tenant_id == tenant_id, ExternalAppMember.principal_id.in_(principal_ids))
                    .distinct()
                )
                query = query.where(ExternalApp.id.in_(member_subquery))

            if id_list:
                query = query.where(ExternalApp.id.in_(id_list))

            if name_filter:
                query = query.where(ExternalApp.name.ilike(f"%{name_filter}%"))

            if tag_ids:
                tag_subquery = (
                    select(ExternalAppTag.external_app_id)
                    .where(ExternalAppTag.tenant_id == tenant_id, ExternalAppTag.tag_id.in_(tag_ids))
                    .distinct()
                )
                query = query.where(ExternalApp.id.in_(tag_subquery))

            if order_by and hasattr(ExternalApp, order_by):
                column = getattr(ExternalApp, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())
            else:
                # MSSQL requires ORDER BY when using OFFSET/LIMIT
                query = query.order_by(ExternalApp.created_at.desc())

            query = query.offset(skip).limit(limit)
            external_apps = session.execute(query).scalars().all()

            logger.info("Retrieved external apps", extra={"count": len(external_apps)})

            result = [self._model_to_response(app) for app in external_apps]

            if is_admin:
                for r in result:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in result]
                if resource_ids:
                    permissions = resolve_my_permissions_bulk(
                        session, ExternalAppMember, "external_app_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in result:
                        r.my_permission = permissions.get(r.id)

            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached external app list")
                except Exception as e:
                    logger.warning("Failed to cache external app list: %s", e)

            return result

    def get_external_app(
        self, tenant_id: str, external_app_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> ExternalAppResponse:
        """Get a specific external app by ID.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            user: Optional user context for permission resolution
            use_cache: Whether to use caching

        Returns:
            External app response

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info("Fetching external app", extra={"tenant_id": tenant_id, "external_app_id": external_app_id})

        cache_key = f"external_apps:detail:tenant:{tenant_id}:ea:{external_app_id}"

        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached external app")
                    result = ExternalAppResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(
                                session, tenant_id, external_app_id, user
                            )
                    return result
            except Exception as e:
                logger.warning("Failed to get cached external app: %s", e)

        with self.db_client.get_session() as session:
            query = (
                select(ExternalApp)
                .options(selectinload(ExternalApp.tags).selectinload(ExternalAppTag.tag))
                .where(ExternalApp.id == external_app_id, ExternalApp.tenant_id == tenant_id)
            )
            external_app = session.execute(query).scalar_one_or_none()

            if not external_app:
                raise ExternalAppNotFoundError(external_app_id)

            result = self._model_to_response(external_app)

            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached external app detail")
                except Exception as e:
                    logger.warning("Failed to cache external app: %s", e)

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, external_app_id, user)

            return result

    def create_external_app(
        self, tenant_id: str, request: CreateExternalAppRequest, user_id: str, user: ContextIdentityUser
    ) -> ExternalAppResponse:
        """Create a new external app.

        Args:
            tenant_id: The ID of the tenant
            request: External app creation data
            user_id: The ID of the user creating the app
            user: The authenticated user context

        Returns:
            Created external app response
        """
        logger.info("Creating external app", extra={"tenant_id": tenant_id, "app_name": request.name})

        validated_config = ExternalAppConfigValidatorFactory.validate_config(request.config)

        external_app_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            external_app = ExternalApp(
                id=external_app_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                config=validated_config,
                image_url=request.image_url,
                image_file_id=request.image_file_id,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(external_app)

            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="external_app",
                tenant_id=tenant_id,
                resource_id=external_app_id,
                user_id=user_id,
                user=user,
            )

            try:
                session.flush()
            except IntegrityError as e:
                session.rollback()
                if "uq_external_app_tenant_name" in str(e):
                    raise ExternalAppAlreadyExistsError(request.name) from e
                raise

            session.commit()
            session.refresh(external_app)

            logger.info("External app created", extra={"external_app_id": external_app_id})

            self._cache.invalidate_list(tenant_id)

            return self._model_to_response(external_app)

    def update_external_app(
        self, tenant_id: str, external_app_id: str, request: UpdateExternalAppRequest, user_id: str
    ) -> ExternalAppResponse:
        """Update an existing external app.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            request: External app update data
            user_id: The ID of the user updating the app

        Returns:
            Updated external app response

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info("Updating external app", extra={"tenant_id": tenant_id, "external_app_id": external_app_id})

        with self.db_client.get_session() as session:
            query = (
                select(ExternalApp)
                .options(selectinload(ExternalApp.tags).selectinload(ExternalAppTag.tag))
                .where(ExternalApp.id == external_app_id, ExternalApp.tenant_id == tenant_id)
            )
            external_app = session.execute(query).scalar_one_or_none()

            if not external_app:
                raise ExternalAppNotFoundError(external_app_id)

            if request.name is not None:
                external_app.name = request.name
            if request.description is not None:
                external_app.description = request.description
            if request.config is not None:
                external_app.config = ExternalAppConfigValidatorFactory.validate_config(request.config)
            if request.image_url is not None:
                external_app.image_url = request.image_url
            if request.image_file_id is not None:
                external_app.image_file_id = request.image_file_id

            external_app.updated_by = user_id

            try:
                session.flush()
            except IntegrityError as e:
                session.rollback()
                if "uq_external_app_tenant_name" in str(e):
                    raise ExternalAppAlreadyExistsError(request.name or external_app.name) from e
                raise

            session.commit()

            query = (
                select(ExternalApp)
                .options(selectinload(ExternalApp.tags).selectinload(ExternalAppTag.tag))
                .where(ExternalApp.id == external_app_id, ExternalApp.tenant_id == tenant_id)
            )
            external_app = session.execute(query).scalar_one_or_none()
            assert external_app is not None

            logger.info("External app updated", extra={"external_app_id": external_app_id})

            self._cache.invalidate_list(tenant_id)
            self._cache.invalidate_detail(tenant_id, external_app_id)

            return self._model_to_response(external_app)

    def delete_external_app(self, tenant_id: str, external_app_id: str) -> None:
        """Delete an external app.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info("Deleting external app", extra={"tenant_id": tenant_id, "external_app_id": external_app_id})

        with self.db_client.get_session() as session:
            query = select(ExternalApp).where(ExternalApp.id == external_app_id, ExternalApp.tenant_id == tenant_id)
            external_app = session.execute(query).scalar_one_or_none()

            if not external_app:
                raise ExternalAppNotFoundError(external_app_id)

            session.delete(external_app)

            # Clean up recent visits for this resource
            session.execute(
                delete(RecentVisit).where(
                    RecentVisit.tenant_id == tenant_id,
                    RecentVisit.resource_type == "external_app",
                    RecentVisit.resource_id == external_app_id,
                )
            )

            session.commit()

            logger.info("External app deleted", extra={"external_app_id": external_app_id})

            self._cache.invalidate_list(tenant_id)
            self._cache.invalidate_detail(tenant_id, external_app_id)
            self._cache.invalidate_permissions(tenant_id, external_app_id)

    # ========== Permission Management Methods ==========

    def list_external_app_permissions(
        self,
        tenant_id: str,
        external_app_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> ResourcePrincipalsResponse:
        """List all permissions for an external app, grouped by principal.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            skip: Number of principals to skip
            limit: Maximum number of principals to return
            search: Search term for display_name, principal_name, or mail
            roles: Filter by roles (OR logic)
            is_active: Filter by is_active status
            order_by: Column to order by
            order_direction: Sort direction
            use_cache: Whether to use caching

        Returns:
            Grouped principals with their permissions

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info(
            "Listing external app permissions",
            extra={"tenant_id": tenant_id, "external_app_id": external_app_id},
        )

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="external_app",
                tenant_id=tenant_id,
                resource_id=external_app_id,
                skip=skip,
                limit=limit,
                search=search,
                roles=roles,
                is_active=is_active,
                order_by=order_by,
                order_direction=order_direction,
                use_cache=use_cache,
            )
        except ValueError as e:
            raise ExternalAppNotFoundError(external_app_id) from e

        principals = [
            PrincipalWithRolesResponse(
                principal_id=p["principal_id"],
                principal_type=p["principal_type"],
                roles=p["roles"],
                mail=p.get("mail"),
                display_name=p.get("display_name"),
                principal_name=p.get("principal_name"),
                description=p.get("description"),
                is_active=p.get("is_active", True),
            )
            for p in result["principals"]
        ]

        return ResourcePrincipalsResponse(
            resource_id=external_app_id, resource_type="external_app", tenant_id=tenant_id, principals=principals
        )

    def get_external_app_permission(
        self, tenant_id: str, external_app_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """Get all permissions for a specific principal on an external app.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            principal_id: The ID of the principal

        Returns:
            Principal with all their permissions

        Raises:
            ExternalAppNotFoundError: If external app or permission not found
        """
        logger.info(
            "Getting external app permission",
            extra={"tenant_id": tenant_id, "external_app_id": external_app_id, "principal_id": principal_id},
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="external_app",
                tenant_id=tenant_id,
                resource_id=external_app_id,
                principal_id=principal_id,
            )
        except ValueError as e:
            raise ExternalAppNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_external_app_permission(
        self,
        tenant_id: str,
        external_app_id: str,
        request: SetResourcePermissionRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """Set or update a permission for a principal on an external app.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            request: Permission data
            user_id: The ID of the user setting the permission
            user: The authenticated user context

        Returns:
            Created or updated permission

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info(
            "Setting external app permission",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "principal_id": request.principal_id,
            },
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="external_app",
                tenant_id=tenant_id,
                resource_id=external_app_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )
        except ValueError as e:
            raise ExternalAppNotFoundError(str(e)) from e

        return self.get_external_app_permission(
            tenant_id=tenant_id, external_app_id=external_app_id, principal_id=request.principal_id
        )

    def delete_external_app_permission(
        self, tenant_id: str, external_app_id: str, principal_id: str, principal_type: str, permission: str
    ) -> None:
        """Delete a specific permission for a principal on an external app.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to delete

        Raises:
            ExternalAppNotFoundError: If external app or permission not found
        """
        logger.info(
            "Deleting external app permission",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "principal_id": principal_id,
                "permission": permission,
            },
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="external_app",
                tenant_id=tenant_id,
                resource_id=external_app_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission,
            )
        except ValueError as e:
            raise ExternalAppNotFoundError(str(e)) from e

    def _resolve_user_permission(
        self, session: Session, tenant_id: str, external_app_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific external app.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            external_app_id: External app ID
            user: The authenticated user context

        Returns:
            Permission action string or None
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(user, tenant_id, [TenantRolesEnum.TENANT_GLOBAL_ADMIN, TenantRolesEnum.EXTERNAL_APPS_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(
            session, ExternalAppMember, "external_app_id", tenant_id, external_app_id, principal_ids
        )

    @staticmethod
    def _model_to_response(external_app: ExternalApp) -> ExternalAppResponse:
        """Convert ExternalApp model to ExternalAppResponse."""
        tags = []
        if hasattr(external_app, "tags") and external_app.tags:
            for ea_tag in external_app.tags:
                if ea_tag.tag:
                    tags.append(TagSummary(id=ea_tag.tag.id, name=ea_tag.tag.name))

        return ExternalAppResponse(
            id=external_app.id,
            tenant_id=external_app.tenant_id,
            name=external_app.name,
            description=external_app.description,
            config=dict(external_app.config) if external_app.config else {},
            image_url=external_app.image_url,
            image_file_id=external_app.image_file_id,
            tags=tags,
            created_at=external_app.created_at,
            updated_at=external_app.updated_at,
            created_by=external_app.created_by,
            updated_by=external_app.updated_by,
        )
