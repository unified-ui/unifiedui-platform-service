"""Business logic handlers for chat widget operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import ChatWidget, ChatWidgetMember, ChatWidgetTag
from unifiedui.handlers.permission_resolver import (
    check_is_admin,
    get_principal_ids,
    resolve_my_permission,
    resolve_my_permissions_bulk,
)

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler
    from unifiedui.schema.requests.chat_widget_permissions import SetChatWidgetPermissionRequest
    from unifiedui.schema.requests.chat_widgets import CreateChatWidgetRequest, UpdateChatWidgetRequest

from unifiedui.exc.chat_widgets import ChatWidgetNotFoundError
from unifiedui.logger import get_logger
from unifiedui.schema.responses.chat_widgets import ChatWidgetResponse
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.tags import TagSummary

logger = get_logger(__name__)


class ChatWidgetHandler:
    """Handler class for chat widget business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
    ):
        """
        Initialize the chat widget handler.

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

    def list_chat_widgets(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        is_active: int | None = None,
        tag_ids: list[int] | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        view: str | None = None,
        use_cache: bool = True,
    ) -> list[ChatWidgetResponse] | list[QuickListItemResponse]:
        """
        Get a list of chat widgets for a tenant (filtered by permissions).

        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by chat widget name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (chat widgets must have AT LEAST ONE of the tags - OR logic)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching

        Returns:
            List of chat widget responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing chat widgets", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        # Check if user is admin (has GLOBAL_ADMIN or CHAT_WIDGETS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            admin_permissions = [TenantRolesEnum.GLOBAL_ADMIN.value, TenantRolesEnum.CHAT_WIDGETS_ADMIN.value]
            is_admin = any(perm in user_roles for perm in admin_permissions)

        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            # groups now contains both IDENTITY_GROUP and CUSTOM_GROUP with principal_type attribute
            identity_group_ids = [
                g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
            ]
            custom_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]

        # Build cache key with order and is_active parameters
        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"chat_widgets:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"

        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None

        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached chat widget list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [ChatWidgetResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached chat widget list: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(ChatWidget)
                .options(selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag))
                .where(ChatWidget.tenant_id == tenant_id)
            )

            # Filter by permissions if not admin
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)

                # Subquery for chat widgets where user is a member
                member_subquery = (
                    select(ChatWidgetMember.chat_widget_id)
                    .where(ChatWidgetMember.tenant_id == tenant_id, ChatWidgetMember.principal_id.in_(principal_ids))
                    .distinct()
                )

                query = query.where(ChatWidget.id.in_(member_subquery))

            if name_filter:
                query = query.where(ChatWidget.name.ilike(f"%{name_filter}%"))

            if is_active is not None:
                query = query.where(ChatWidget.is_active == bool(is_active))

            # Filter by tags (chat widgets must have AT LEAST ONE of the specified tags - OR logic)
            if tag_ids:
                tag_subquery = (
                    select(ChatWidgetTag.chat_widget_id)
                    .where(ChatWidgetTag.tenant_id == tenant_id, ChatWidgetTag.tag_id.in_(tag_ids))
                    .distinct()
                )
                query = query.where(ChatWidget.id.in_(tag_subquery))

            # Apply ordering if specified
            if order_by and hasattr(ChatWidget, order_by):
                column = getattr(ChatWidget, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            chat_widgets = session.execute(query).scalars().all()

            logger.info("Retrieved chat widgets", extra={"count": len(chat_widgets)})

            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=cw.id, name=cw.name) for cw in chat_widgets]

            result = [self._model_to_response(cw) for cw in chat_widgets]

            if is_admin:
                for r in result:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in result]
                if resource_ids:
                    permissions = resolve_my_permissions_bulk(
                        session, ChatWidgetMember, "chat_widget_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in result:
                        r.my_permission = permissions.get(r.id)

            # Cache the result (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached chat widget list")
                except Exception as e:
                    logger.warning(f"Failed to cache chat widget list: {e}")

            return result

    def get_chat_widget(
        self, tenant_id: str, chat_widget_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> ChatWidgetResponse:
        """
        Get a specific chat widget by ID.

        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
            user: Optional user context for permission resolution
            use_cache: Whether to use caching

        Returns:
            Chat widget response

        Raises:
            ChatWidgetNotFoundError: If chat widget not found
        """
        logger.info("Fetching chat widget", extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id})

        # Build cache key
        cache_key = f"chat_widgets:detail:tenant:{tenant_id}:cw:{chat_widget_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached chat widget")
                    result = ChatWidgetResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(
                                session, tenant_id, chat_widget_id, user
                            )
                    return result
            except Exception as e:
                logger.warning(f"Failed to get cached chat widget: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(ChatWidget)
                .options(selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag))
                .where(ChatWidget.id == chat_widget_id, ChatWidget.tenant_id == tenant_id)
            )
            chat_widget = session.execute(query).scalar_one_or_none()

            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)

            result = self._model_to_response(chat_widget)

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached chat widget detail")
                except Exception as e:
                    logger.warning(f"Failed to cache chat widget: {e}")

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, chat_widget_id, user)

            return result

    def create_chat_widget(
        self, tenant_id: str, request: CreateChatWidgetRequest, user_id: str, user: ContextIdentityUser
    ) -> ChatWidgetResponse:
        """
        Create a new chat widget.

        Args:
            tenant_id: The ID of the tenant
            request: Chat widget creation data
            user_id: The ID of the user creating the chat widget
            user: The authenticated user context (for IDP access)

        Returns:
            Created chat widget response
        """
        logger.info("Creating chat widget", extra={"tenant_id": tenant_id, "cw_name": request.name})

        chat_widget_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            # Create chat widget
            chat_widget = ChatWidget(
                id=chat_widget_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value if request.type else None,
                config=request.config,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(chat_widget)

            # Add creator as admin member using central handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="chat_widget",
                tenant_id=tenant_id,
                resource_id=chat_widget_id,
                user_id=user_id,
                user=user,
            )

            session.commit()
            session.refresh(chat_widget)

            logger.info("Chat widget created", extra={"chat_widget_id": chat_widget_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)

            return self._model_to_response(chat_widget)

    def update_chat_widget(
        self, tenant_id: str, chat_widget_id: str, request: UpdateChatWidgetRequest, user_id: str
    ) -> ChatWidgetResponse:
        """
        Update an existing chat widget.

        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
            request: Chat widget update data
            user_id: The ID of the user updating the chat widget

        Returns:
            Updated chat widget response

        Raises:
            ChatWidgetNotFoundError: If chat widget not found
        """
        logger.info("Updating chat widget", extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id})

        with self.db_client.get_session() as session:
            query = (
                select(ChatWidget)
                .options(selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag))
                .where(ChatWidget.id == chat_widget_id, ChatWidget.tenant_id == tenant_id)
            )
            chat_widget = session.execute(query).scalar_one_or_none()

            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)

            # Update fields if provided
            if request.name is not None:
                chat_widget.name = request.name
            if request.description is not None:
                chat_widget.description = request.description
            if request.type is not None:
                chat_widget.type = request.type.value
            if request.config is not None:
                chat_widget.config = request.config
            if request.is_active is not None:
                chat_widget.is_active = request.is_active

            chat_widget.updated_by = user_id

            session.commit()

            # Re-fetch with tags to ensure they are loaded
            query = (
                select(ChatWidget)
                .options(selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag))
                .where(ChatWidget.id == chat_widget_id, ChatWidget.tenant_id == tenant_id)
            )
            chat_widget = session.execute(query).scalar_one_or_none()

            logger.info("Chat widget updated", extra={"chat_widget_id": chat_widget_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_widget_id)

            return self._model_to_response(chat_widget)

    def delete_chat_widget(self, tenant_id: str, chat_widget_id: str) -> None:
        """
        Delete a chat widget.

        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget

        Raises:
            ChatWidgetNotFoundError: If chat widget not found
        """
        logger.info("Deleting chat widget", extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id})

        with self.db_client.get_session() as session:
            query = select(ChatWidget).where(ChatWidget.id == chat_widget_id, ChatWidget.tenant_id == tenant_id)
            chat_widget = session.execute(query).scalar_one_or_none()

            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)

            session.delete(chat_widget)
            session.commit()

            logger.info("Chat widget deleted", extra={"chat_widget_id": chat_widget_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_widget_id)
            self._invalidate_permissions_cache(tenant_id, chat_widget_id)

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        if self.cache_client:
            pattern = f"chat_widgets:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, chat_widget_id: str) -> None:
        """Invalidate detail cache for a chat widget."""
        if self.cache_client:
            cache_key = f"chat_widgets:detail:tenant:{tenant_id}:cw:{chat_widget_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, chat_widget_id: str) -> None:
        """Invalidate permissions cache for a chat widget."""
        if self.cache_client:
            pattern = f"chat_widgets:permissions:tenant:{tenant_id}:cw:{chat_widget_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    # ========== Permission Management Methods ==========

    def list_chat_widget_permissions(
        self,
        tenant_id: str,
        chat_widget_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> ResourcePrincipalsResponse:
        """
        List all permissions for a chat widget, grouped by principal.

        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
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
            ChatWidgetNotFoundError: If chat widget not found
        """
        logger.info("Listing chat widget permissions", extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id})

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="chat_widget",
                tenant_id=tenant_id,
                resource_id=chat_widget_id,
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
            raise ChatWidgetNotFoundError(chat_widget_id) from e

        # Convert to response schema
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
            resource_id=chat_widget_id, resource_type="chat_widget", tenant_id=tenant_id, principals=principals
        )

    def get_chat_widget_permission(
        self, tenant_id: str, chat_widget_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """
        Get all permissions for a specific principal on a chat widget.

        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
            principal_id: The ID of the principal

        Returns:
            Principal with all their permissions

        Raises:
            ChatWidgetNotFoundError: If chat widget or permission not found
        """
        logger.info(
            "Getting chat widget permission",
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "principal_id": principal_id},
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="chat_widget", tenant_id=tenant_id, resource_id=chat_widget_id, principal_id=principal_id
            )
        except ValueError as e:
            raise ChatWidgetNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_chat_widget_permission(
        self,
        tenant_id: str,
        chat_widget_id: str,
        request: SetChatWidgetPermissionRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """
        Set or update a permission for a principal on a chat widget.

        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
            request: Permission data
            user_id: The ID of the user setting the permission

        Returns:
            Created or updated permission

        Raises:
            ChatWidgetNotFoundError: If chat widget not found
        """
        logger.info(
            "Setting chat widget permission",
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "principal_id": request.principal_id},
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="chat_widget",
                tenant_id=tenant_id,
                resource_id=chat_widget_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )
        except ValueError as e:
            raise ChatWidgetNotFoundError(str(e)) from e

        # Fetch and return the enriched principal data
        return self.get_chat_widget_permission(
            tenant_id=tenant_id, chat_widget_id=chat_widget_id, principal_id=request.principal_id
        )

    def delete_chat_widget_permission(
        self, tenant_id: str, chat_widget_id: str, principal_id: str, principal_type: str, permission: str
    ) -> None:
        """
        Delete a specific permission for a principal on a chat widget.

        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to delete

        Raises:
            ChatWidgetNotFoundError: If chat widget or permission not found
        """
        logger.info(
            "Deleting chat widget permission",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "principal_id": principal_id,
                "permission": permission,
            },
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="chat_widget",
                tenant_id=tenant_id,
                resource_id=chat_widget_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission,
            )
        except ValueError as e:
            raise ChatWidgetNotFoundError(str(e)) from e

    def _resolve_user_permission(
        self, session: object, tenant_id: str, chat_widget_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific chat widget.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            chat_widget_id: Chat widget ID
            user: The authenticated user context

        Returns:
            Permission action string or None
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(user, tenant_id, [TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.CHAT_WIDGETS_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(
            session, ChatWidgetMember, "chat_widget_id", tenant_id, chat_widget_id, principal_ids
        )

    @staticmethod
    def _model_to_response(chat_widget: ChatWidget) -> ChatWidgetResponse:
        """Convert ChatWidget model to ChatWidgetResponse."""
        # Extract tags from the chat widget's tags relationship
        tags = []
        if hasattr(chat_widget, "tags") and chat_widget.tags:
            for cw_tag in chat_widget.tags:
                if cw_tag.tag:
                    tags.append(TagSummary(id=cw_tag.tag.id, name=cw_tag.tag.name))

        return ChatWidgetResponse(
            id=chat_widget.id,
            tenant_id=chat_widget.tenant_id,
            name=chat_widget.name,
            description=chat_widget.description,
            is_active=chat_widget.is_active,
            type=chat_widget.type,
            config=chat_widget.config,
            tags=tags,
            created_at=chat_widget.created_at,
            updated_at=chat_widget.updated_at,
            created_by=chat_widget.created_by,
            updated_by=chat_widget.updated_by,
        )
