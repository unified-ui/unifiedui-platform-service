"""Business logic handlers for chat widget operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import ChatWidget, ChatWidgetMember, ChatWidgetTag, Tag
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.caching.client import CacheClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

from unifiedui.schema.requests.chat_widgets import CreateChatWidgetRequest, UpdateChatWidgetRequest
from unifiedui.schema.requests.chat_widget_permissions import SetChatWidgetPermissionRequest
from unifiedui.schema.responses.chat_widgets import ChatWidgetResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.chat_widget_permissions import (
    ChatWidgetPermissionResponse,
    ChatWidgetPrincipalsResponse,
    PrincipalPermissionsResponse
)
from unifiedui.exc.chat_widgets import ChatWidgetNotFoundError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class ChatWidgetHandler:
    """Handler class for chat widget business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None
    ):
        """
        Initialize the chat widget handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_chat_widgets(
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
    ) -> List[ChatWidgetResponse]:
        """
        Get a list of chat widgets for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by chat widget name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (chat widgets must have ALL specified tags)
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
        matching_tenant = next(
            (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
            None
        )
        
        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            admin_permissions = [
                TenantRolesEnum.GLOBAL_ADMIN.value,
                TenantRolesEnum.CHAT_WIDGETS_ADMIN.value
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
        cache_key = f"chat_widgets:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}"
        
        # Check if any filters are applied
        has_filters = name_filter is not None or is_active is not None or tag_ids is not None or order_by is not None
        
        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached chat widget list")
                    return [ChatWidgetResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached chat widget list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(ChatWidget).options(
                selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag)
            ).where(ChatWidget.tenant_id == tenant_id)
            
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
                    .where(
                        ChatWidgetMember.tenant_id == tenant_id,
                        ChatWidgetMember.principal_id.in_(principal_ids)
                    )
                    .distinct()
                )
                
                query = query.where(ChatWidget.id.in_(member_subquery))
            
            if name_filter:
                query = query.where(ChatWidget.name.ilike(f"%{name_filter}%"))
            
            if is_active is not None:
                query = query.where(ChatWidget.is_active == bool(is_active))
            
            # Filter by tags (chat widgets must have ALL specified tags)
            if tag_ids:
                for tag_id in tag_ids:
                    tag_subquery = (
                        select(ChatWidgetTag.chat_widget_id)
                        .where(
                            ChatWidgetTag.tenant_id == tenant_id,
                            ChatWidgetTag.tag_id == tag_id
                        )
                    )
                    query = query.where(ChatWidget.id.in_(tag_subquery))
            
            # Apply ordering if specified
            if order_by and hasattr(ChatWidget, order_by):
                column = getattr(ChatWidget, order_by)
                if order_direction == "desc":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            
            query = query.offset(skip).limit(limit)
            chat_widgets = session.execute(query).scalars().all()
            
            logger.info("Retrieved chat widgets", extra={"count": len(chat_widgets)})
            result = [self._model_to_response(cw) for cw in chat_widgets]
            
            # Cache the result (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug(f"Cached chat widget list")
                except Exception as e:
                    logger.warning(f"Failed to cache chat widget list: {e}")
            
            return result

    def get_chat_widget(
        self,
        tenant_id: str,
        chat_widget_id: str,
        use_cache: bool = True
    ) -> ChatWidgetResponse:
        """
        Get a specific chat widget by ID.
        
        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
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
                    logger.debug(f"Returning cached chat widget")
                    return ChatWidgetResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached chat widget: {e}")
        
        with self.db_client.get_session() as session:
            query = select(ChatWidget).options(
                selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag)
            ).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
            )
            chat_widget = session.execute(query).scalar_one_or_none()
            
            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)
            
            result = self._model_to_response(chat_widget)
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug(f"Cached chat widget detail")
                except Exception as e:
                    logger.warning(f"Failed to cache chat widget: {e}")
            
            return result

    def create_chat_widget(
        self,
        tenant_id: str,
        request: CreateChatWidgetRequest,
        user_id: str
    ) -> ChatWidgetResponse:
        """
        Create a new chat widget.
        
        Args:
            tenant_id: The ID of the tenant
            request: Chat widget creation data
            user_id: The ID of the user creating the chat widget
            
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
                updated_by=user_id
            )
            session.add(chat_widget)
            
            # Add creator as admin member
            member_id = str(uuid.uuid4())
            member = ChatWidgetMember(
                id=member_id,
                tenant_id=tenant_id,
                chat_widget_id=chat_widget_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER,
                role=PermissionActionEnum.ADMIN,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(member)
            
            session.commit()
            session.refresh(chat_widget)
            
            logger.info("Chat widget created", extra={"chat_widget_id": chat_widget_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            
            return self._model_to_response(chat_widget)

    def update_chat_widget(
        self,
        tenant_id: str,
        chat_widget_id: str,
        request: UpdateChatWidgetRequest,
        user_id: str
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
            query = select(ChatWidget).options(
                selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag)
            ).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
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
            
            chat_widget.updated_by = user_id
            
            session.commit()
            
            # Re-fetch with tags to ensure they are loaded
            query = select(ChatWidget).options(
                selectinload(ChatWidget.tags).selectinload(ChatWidgetTag.tag)
            ).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
            )
            chat_widget = session.execute(query).scalar_one_or_none()
            
            logger.info("Chat widget updated", extra={"chat_widget_id": chat_widget_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_widget_id)
            
            return self._model_to_response(chat_widget)

    def delete_chat_widget(
        self,
        tenant_id: str,
        chat_widget_id: str
    ) -> None:
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
            query = select(ChatWidget).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
            )
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
        use_cache: bool = True
    ) -> ChatWidgetPrincipalsResponse:
        """
        List all permissions for a chat widget, grouped by principal.
        
        Args:
            tenant_id: The ID of the tenant
            chat_widget_id: The ID of the chat widget
            use_cache: Whether to use caching
            
        Returns:
            Grouped principals with their permissions
            
        Raises:
            ChatWidgetNotFoundError: If chat widget not found
        """
        logger.info("Listing chat widget permissions", extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id})
        
        # Build cache key
        cache_key = f"chat_widgets:permissions:tenant:{tenant_id}:cw:{chat_widget_id}:list"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached permissions list")
                    return ChatWidgetPrincipalsResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached permissions: {e}")
        
        with self.db_client.get_session() as session:
            # Verify chat widget exists
            cw_query = select(ChatWidget).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
            )
            chat_widget = session.execute(cw_query).scalar_one_or_none()
            
            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)
            
            # Get all members and their roles
            members_query = (
                select(ChatWidgetMember)
                .where(ChatWidgetMember.chat_widget_id == chat_widget_id)
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
                    chat_widget_id=chat_widget_id,
                    tenant_id=tenant_id,
                    **data
                )
                for data in principals_dict.values()
            ]
            
            result = ChatWidgetPrincipalsResponse(
                chat_widget_id=chat_widget_id,
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

    def get_chat_widget_permission(
        self,
        tenant_id: str,
        chat_widget_id: str,
        principal_id: str
    ) -> PrincipalPermissionsResponse:
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
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "principal_id": principal_id}
        )
        
        with self.db_client.get_session() as session:
            # Verify chat widget exists
            cw_query = select(ChatWidget).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
            )
            chat_widget = session.execute(cw_query).scalar_one_or_none()
            
            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)
            
            # Get member for this principal
            member_query = (
                select(ChatWidgetMember)
                .where(
                    ChatWidgetMember.chat_widget_id == chat_widget_id,
                    ChatWidgetMember.principal_id == principal_id
                )
            )
            members = session.execute(member_query).scalars().all()
            
            if not members:
                raise ChatWidgetNotFoundError(f"No permissions found for principal {principal_id}")
            
            # Collect all roles and get principal_type from first member
            permissions = []
            principal_type = members[0].principal_type
            for member in members:
                if member.role not in permissions:
                    permissions.append(member.role)
            
            return PrincipalPermissionsResponse(
                chat_widget_id=chat_widget_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                roles=permissions
            )

    def set_chat_widget_permission(
        self,
        tenant_id: str,
        chat_widget_id: str,
        request: SetChatWidgetPermissionRequest,
        user_id: str
    ) -> ChatWidgetPermissionResponse:
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
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "principal_id": request.principal_id
            }
        )
        
        with self.db_client.get_session() as session:
            # Verify chat widget exists
            cw_query = select(ChatWidget).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
            )
            chat_widget = session.execute(cw_query).scalar_one_or_none()
            
            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)
            
            # Find or create member with this role
            # Note: A principal can only have ONE role per chat widget (enforced by unique constraint)
            # So we need to update or insert
            member_query = (
                select(ChatWidgetMember)
                .where(
                    ChatWidgetMember.chat_widget_id == chat_widget_id,
                    ChatWidgetMember.principal_id == request.principal_id,
                    ChatWidgetMember.principal_type == request.principal_type.value
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                # Create new member with role
                member_id = str(uuid.uuid4())
                member = ChatWidgetMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    chat_widget_id=chat_widget_id,
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
            
            result = ChatWidgetPermissionResponse(
                id=member.id,
                chat_widget_id=chat_widget_id,
                tenant_id=tenant_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type,
                role=request.role,
                created_at=member.created_at,
                updated_at=member.updated_at
            )
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, chat_widget_id)
            
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

    def delete_chat_widget_permission(
        self,
        tenant_id: str,
        chat_widget_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
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
                "permission": permission
            }
        )
        
        with self.db_client.get_session() as session:
            # Verify chat widget exists
            cw_query = select(ChatWidget).where(
                ChatWidget.id == chat_widget_id,
                ChatWidget.tenant_id == tenant_id
            )
            chat_widget = session.execute(cw_query).scalar_one_or_none()
            
            if not chat_widget:
                raise ChatWidgetNotFoundError(chat_widget_id)
            
            # Find member with this role
            member_query = (
                select(ChatWidgetMember)
                .where(
                    ChatWidgetMember.chat_widget_id == chat_widget_id,
                    ChatWidgetMember.principal_id == principal_id,
                    ChatWidgetMember.principal_type == principal_type,
                    ChatWidgetMember.role == permission
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                raise ChatWidgetNotFoundError(f"Member with role {permission} not found for principal {principal_id}")
            
            session.delete(member)
            session.commit()
            
            logger.info("Member with role deleted")
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, chat_widget_id)
            
            # Invalidate user cache so list operations reflect removed permissions
            if self.cache_client:
                try:
                    if principal_type == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(principal_id)
                        logger.debug(f"Cleared cache for user {principal_id} after permission removal")
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")

    @staticmethod
    def _model_to_response(chat_widget: ChatWidget) -> ChatWidgetResponse:
        """Convert ChatWidget model to ChatWidgetResponse."""
        # Extract tags from the chat widget's tags relationship
        tags = []
        if hasattr(chat_widget, 'tags') and chat_widget.tags:
            for cw_tag in chat_widget.tags:
                if cw_tag.tag:
                    tags.append(TagSummary(
                        id=cw_tag.tag.id,
                        name=cw_tag.tag.name
                    ))
        
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
            updated_by=chat_widget.updated_by
        )
