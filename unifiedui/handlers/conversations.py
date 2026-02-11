"""Business logic handlers for conversation operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List, Union

from sqlalchemy import select

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import Conversation, ConversationMember, Application
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, ApplicationTypeEnum
from unifiedui.caching.client import CacheClient
from unifiedui.services.agent_service_client import AgentServiceClient
from unifiedui.handlers.permission_resolver import resolve_my_permissions_bulk, resolve_my_permission, get_principal_ids, check_is_admin

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler

from unifiedui.schema.requests.conversations import CreateConversationRequest, UpdateConversationRequest
from unifiedui.schema.requests.conversation_permissions import SetConversationPermissionRequest
from unifiedui.schema.responses.conversations import ConversationResponse, ConversationQuickListItemResponse
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import (
    PrincipalWithRolesResponse,
    ResourcePrincipalsResponse
)
from unifiedui.exc.conversations import ConversationNotFoundError, FoundryConversationCreationError
from unifiedui.libs.foundry.client import MicrosoftFoundryClient, MicrosoftFoundryError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class ConversationHandler:
    """Handler class for conversation business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None,
        permissions_handler: Optional[ResourcePermissionsHandler] = None,
        agent_service_client: Optional[AgentServiceClient] = None
    ):
        """
        Initialize the conversation handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
            permissions_handler: Optional central permissions handler
            agent_service_client: Optional agent service client for cascade delete
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self._permissions_handler = permissions_handler
        self._agent_service_client = agent_service_client

    @property
    def permissions_handler(self) -> ResourcePermissionsHandler:
        """Get the permissions handler, creating one if needed."""
        if self._permissions_handler is None:
            from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
            self._permissions_handler = ResourcePermissionsHandler(self.db_client, self.cache_client)
        return self._permissions_handler

    def list_conversations(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None,
        is_active: Optional[int] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        view: Optional[str] = None,
        use_cache: bool = True
    ) -> Union[List[ConversationResponse], List[QuickListItemResponse]]:
        """
        Get a list of conversations for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by conversation name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            view: Optional view type ('full' or 'quick-list')
            use_cache: Whether to use caching
            
        Returns:
            List of conversation responses or quick-list items
        """
        from unifiedui.core.database.enums import TenantRolesEnum
        
        logger.info("Listing conversations", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        # Check if user is admin (has GLOBAL_ADMIN or CONVERSATIONS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next(
            (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
            None
        )
        
        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            is_admin = any(
                p in user_roles 
                for p in [TenantRolesEnum.GLOBAL_ADMIN.value, TenantRolesEnum.CONVERSATIONS_ADMIN.value]
            )
        
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
        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"conversations:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"
        
        # Check if any filters are applied
        has_filters = name_filter is not None
        
        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached conversation list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [ConversationResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached conversation list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(Conversation.tenant_id == tenant_id)
            
            # Filter by permissions if not admin
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)
                
                # Subquery for conversations where user is a member
                member_subquery = (
                    select(ConversationMember.conversation_id)
                    .where(
                        ConversationMember.tenant_id == tenant_id,
                        ConversationMember.principal_id.in_(principal_ids)
                    )
                    .distinct()
                )
                
                query = query.where(Conversation.id.in_(member_subquery))
            
            if name_filter:
                query = query.where(Conversation.name.ilike(f"%{name_filter}%"))
            
            # Filter by is_active status
            if is_active is not None:
                query = query.where(Conversation.is_active == bool(is_active))
            
            # Apply ordering if specified
            if order_by and hasattr(Conversation, order_by):
                column = getattr(Conversation, order_by)
                if order_direction == "desc":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            
            query = query.offset(skip).limit(limit)
            conversations = session.execute(query).scalars().all()
            
            logger.info("Retrieved conversations", extra={"count": len(conversations)})
            
            # Return quick-list format if requested
            if view == "quick-list":
                quick_result = [ConversationQuickListItemResponse(id=conv.id, name=conv.name, application_id=conv.application_id) for conv in conversations]
                if use_cache and self.cache_client and not has_filters:
                    try:
                        data = [r.model_dump() for r in quick_result]
                        self.cache_client.client.set(cache_key, data, ttl=300)
                    except Exception as e:
                        logger.warning(f"Failed to cache conversation list: {e}")
                return quick_result
            
            result = [self._model_to_response(conv) for conv in conversations]

            if is_admin:
                for r in result:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in result]
                if resource_ids:
                    permissions = resolve_my_permissions_bulk(
                        session, ConversationMember, "conversation_id",
                        tenant_id, resource_ids, principal_ids
                    )
                    for r in result:
                        r.my_permission = permissions.get(r.id)

            # Cache the result (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug(f"Cached conversation list")
                except Exception as e:
                    logger.warning(f"Failed to cache conversation list: {e}")
            
            return result

    def get_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
        user: Optional[ContextIdentityUser] = None,
        use_cache: bool = True
    ) -> ConversationResponse:
        """
        Get a specific conversation by ID.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            user: Optional user context for permission resolution
            use_cache: Whether to use caching
            
        Returns:
            Conversation response
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Fetching conversation", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        # Build cache key
        cache_key = f"conversations:detail:tenant:{tenant_id}:conv:{conversation_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached conversation")
                    result = ConversationResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(
                                session, tenant_id, conversation_id, user
                            )
                    return result
            except Exception as e:
                logger.warning(f"Failed to get cached conversation: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            result = self._model_to_response(conversation)
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug(f"Cached conversation detail")
                except Exception as e:
                    logger.warning(f"Failed to cache conversation: {e}")

            if user:
                result.my_permission = self._resolve_user_permission(
                    session, tenant_id, conversation_id, user
                )
            
            return result

    def create_conversation(
        self,
        tenant_id: str,
        request: CreateConversationRequest,
        user_id: str,
        user: ContextIdentityUser,
        foundry_api_key: Optional[str] = None
    ) -> ConversationResponse:
        """
        Create a new conversation.
        
        For MICROSOFT_FOUNDRY applications, this will also create a conversation
        in the Foundry service and store the external conversation ID.
        
        Args:
            tenant_id: The ID of the tenant
            request: Conversation creation data
            user_id: The ID of the user creating the conversation
            user: The authenticated user context (for IDP access)
            foundry_api_key: Optional API key for Microsoft Foundry (required for MICROSOFT_FOUNDRY apps)
            
        Returns:
            Created conversation response
            
        Raises:
            FoundryConversationCreationError: If Foundry conversation creation fails
        """
        logger.info("Creating conversation", extra={"tenant_id": tenant_id, "conversation_name": request.name})
        
        conversation_id = str(uuid.uuid4())
        ext_conversation_id = None
        
        with self.db_client.get_session() as session:
            # First, check the application type
            app_query = select(Application).where(
                Application.id == request.application_id,
                Application.tenant_id == tenant_id
            )
            application = session.execute(app_query).scalar_one_or_none()
            
            if not application:
                raise ValueError(f"Application with ID '{request.application_id}' not found")
            
            # If application type is MICROSOFT_FOUNDRY, create external conversation
            if application.type == ApplicationTypeEnum.MICROSOFT_FOUNDRY.value:
                if not foundry_api_key:
                    raise FoundryConversationCreationError(
                        message="X-Microsoft-Foundry-API-Key header is required for MICROSOFT_FOUNDRY applications"
                    )
                
                # Extract Foundry settings from application config
                app_config = application.config or {}
                project_endpoint = app_config.get("project_endpoint")
                api_version = app_config.get("api_version", "2025-11-15-preview")
                
                if not project_endpoint:
                    raise FoundryConversationCreationError(
                        message="Application config missing 'project_endpoint' for MICROSOFT_FOUNDRY"
                    )
                
                try:
                    foundry_client = MicrosoftFoundryClient(
                        project_endpoint=project_endpoint,
                        api_token=foundry_api_key,
                        api_version=api_version
                    )
                    ext_conversation_id = foundry_client.get_conversation_id()
                    logger.info(
                        "Created Foundry external conversation",
                        extra={"ext_conversation_id": ext_conversation_id}
                    )
                except MicrosoftFoundryError as e:
                    logger.error(f"Failed to create Foundry conversation: {e}")
                    raise FoundryConversationCreationError(
                        message=f"Failed to create Foundry conversation: {e.message}",
                        status_code=e.status_code
                    ) from e
            
            # Create conversation
            conversation = Conversation(
                id=conversation_id,
                tenant_id=tenant_id,
                application_id=request.application_id,
                ext_conversation_id=ext_conversation_id,
                name=request.name,
                description=request.description,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(conversation)
            
            # Add creator as admin member using central handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="conversation",
                tenant_id=tenant_id,
                resource_id=conversation_id,
                user_id=user_id,
                user=user
            )
            
            session.commit()
            session.refresh(conversation)
            
            logger.info("Conversation created", extra={"conversation_id": conversation_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            
            return self._model_to_response(conversation)

    def update_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
        request: UpdateConversationRequest,
        user_id: str
    ) -> ConversationResponse:
        """
        Update an existing conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            request: Conversation update data
            user_id: The ID of the user updating the conversation
            
        Returns:
            Updated conversation response
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Updating conversation", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            # Update fields if provided
            if request.name is not None:
                conversation.name = request.name
            if request.description is not None:
                conversation.description = request.description
            if request.is_active is not None:
                conversation.is_active = request.is_active
            
            conversation.updated_by = user_id
            
            session.commit()
            session.refresh(conversation)
            
            logger.info("Conversation updated", extra={"conversation_id": conversation_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, conversation_id)
            
            return self._model_to_response(conversation)

    def delete_conversation(
        self,
        tenant_id: str,
        conversation_id: str
    ) -> None:
        """
        Delete a conversation and cascade delete associated data in agent service.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Deleting conversation", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            if self._agent_service_client:
                self._agent_service_client.delete_conversation_data(tenant_id, conversation_id)
            
            session.delete(conversation)
            session.commit()
            
            logger.info("Conversation deleted", extra={"conversation_id": conversation_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, conversation_id)
            self._invalidate_permissions_cache(tenant_id, conversation_id)

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        if self.cache_client:
            self.cache_client.client.delete_pattern(f"conversations:list:tenant:{tenant_id}:*")

    def _invalidate_detail_cache(self, tenant_id: str, conversation_id: str) -> None:
        """Invalidate detail cache for a conversation."""
        if self.cache_client:
            cache_key = f"conversations:detail:tenant:{tenant_id}:conv:{conversation_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, conversation_id: str) -> None:
        """Invalidate permissions cache for a conversation."""
        if self.cache_client:
            self.cache_client.client.delete_pattern(f"conversations:permissions:tenant:{tenant_id}:conv:{conversation_id}:*")

    # ========== Permission Management Methods ==========

    def list_conversation_permissions(
        self,
        tenant_id: str,
        conversation_id: str,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        roles: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        use_cache: bool = True
    ) -> ConversationPrincipalsResponse:
        """
        List all permissions for a conversation, grouped by principal.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
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
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Listing conversation permissions", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        try:
            result = self.permissions_handler.list_permissions(
                resource_type="conversation",
                tenant_id=tenant_id,
                resource_id=conversation_id,
                skip=skip,
                limit=limit,
                search=search,
                roles=roles,
                is_active=is_active,
                order_by=order_by,
                order_direction=order_direction,
                use_cache=use_cache
            )
        except ValueError as e:
            raise ConversationNotFoundError(conversation_id) from e
        
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
                is_active=p.get("is_active", True)
            )
            for p in result["principals"]
        ]
        
        return ResourcePrincipalsResponse(
            resource_id=conversation_id,
            resource_type="conversation",
            tenant_id=tenant_id,
            principals=principals
        )

    def get_conversation_permission(
        self,
        tenant_id: str,
        conversation_id: str,
        principal_id: str
    ) -> PrincipalWithRolesResponse:
        """
        Get all permissions for a specific principal on a conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            principal_id: The ID of the principal
            
        Returns:
            Principal with all their permissions
            
        Raises:
            ConversationNotFoundError: If conversation or permission not found
        """
        logger.info(
            "Getting conversation permission",
            extra={"tenant_id": tenant_id, "conversation_id": conversation_id, "principal_id": principal_id}
        )
        
        try:
            result = self.permissions_handler.get_permission(
                resource_type="conversation",
                tenant_id=tenant_id,
                resource_id=conversation_id,
                principal_id=principal_id
            )
        except ValueError as e:
            raise ConversationNotFoundError(str(e)) from e
        
        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description")
        )

    def set_conversation_permission(
        self,
        tenant_id: str,
        conversation_id: str,
        request: SetConversationPermissionRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> PrincipalWithRolesResponse:
        """
        Set or update a permission for a principal on a conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            request: Permission data
            user_id: The ID of the user setting the permission
            
        Returns:
            Created or updated permission
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info(
            "Setting conversation permission",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "principal_id": request.principal_id
            }
        )
        
        try:
            self.permissions_handler.set_permission(
                resource_type="conversation",
                tenant_id=tenant_id,
                resource_id=conversation_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user
            )
        except ValueError as e:
            raise ConversationNotFoundError(str(e)) from e
        
        # Fetch and return the enriched principal data
        return self.get_conversation_permission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            principal_id=request.principal_id
        )

    def delete_conversation_permission(
        self,
        tenant_id: str,
        conversation_id: str,
        principal_id: str,
        principal_type: str,
        role: str
    ) -> None:
        """
        Delete the permission for a principal on a conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            principal_id: The ID of the principal
            principal_type: The type of principal
            role: The role to delete (must match)
            
        Raises:
            ConversationNotFoundError: If conversation or permission not found
        """
        logger.info(
            "Deleting conversation permission",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "principal_id": principal_id,
                "role": role
            }
        )
        
        try:
            self.permissions_handler.delete_permission(
                resource_type="conversation",
                tenant_id=tenant_id,
                resource_id=conversation_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=role
            )
        except ValueError as e:
            raise ConversationNotFoundError(str(e)) from e

    def _resolve_user_permission(
        self,
        session: object,
        tenant_id: str,
        conversation_id: str,
        user: ContextIdentityUser
    ) -> Optional[str]:
        """Resolve the user's permission level on a specific conversation.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            conversation_id: Conversation ID
            user: The authenticated user context

        Returns:
            Permission action string or None
        """
        from unifiedui.core.database.enums import TenantRolesEnum
        if check_is_admin(user, tenant_id, [TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.CONVERSATIONS_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(
            session, ConversationMember, "conversation_id",
            tenant_id, conversation_id, principal_ids
        )

    @staticmethod
    def _model_to_response(conversation: Conversation) -> ConversationResponse:
        """Convert Conversation model to ConversationResponse."""
        return ConversationResponse(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            application_id=conversation.application_id,
            ext_conversation_id=conversation.ext_conversation_id,
            name=conversation.name,
            description=conversation.description,
            is_active=conversation.is_active,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            created_by=conversation.created_by,
            updated_by=conversation.updated_by
        )
