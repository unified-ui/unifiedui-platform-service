"""Business logic handlers for chat agent operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import ChatAgentTypeEnum, PermissionActionEnum
from unifiedui.core.database.models import (
    ChatAgent,
    ChatAgentMember,
    ChatAgentTag,
    ReActAgentVersion,
    RecentVisit,
    TenantAIModel,
)
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
    from unifiedui.core.vault.client import BaseVaultClient
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler
    from unifiedui.schema.requests.chat_agents import (
        CreateChatAgentRequest,
        UpdateChatAgentRequest,
        UpdateReActAgentVersionRequest,
    )
    from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
    from unifiedui.schema.responses.chat_agents import (
        LLMConfigSettingsResponse,
        MicrosoftFoundryConfigSettingsResponse,
        N8NConfigSettingsResponse,
        RestApiConfigSettingsResponse,
    )
    from unifiedui.schema.responses.re_act_agents import ReActAgentConfigSettingsResponse

from unifiedui.exc.chat_agent_config import (
    InvalidAIModelReferenceError,
    InvalidCredentialError,
)
from unifiedui.exc.chat_agents import ChatAgentNotFoundError
from unifiedui.exc.re_act_agents import ReActAgentVersionNotFoundError
from unifiedui.handlers.validators.chat_agent_config import ChatAgentConfigValidatorFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.chat_agents import ChatAgentConfigResponse, ChatAgentResponse
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.re_act_agents import ReActAgentVersionResponse
from unifiedui.schema.responses.tags import TagSummary

logger = get_logger(__name__)


class ChatAgentHandler:
    """Handler class for chat agent business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        vault_client: BaseVaultClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
    ):
        """
        Initialize the chat agent handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
            vault_client: Optional vault client for secret management
            permissions_handler: Optional central permissions handler
            tags_handler: Optional central tags handler
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self.vault_client = vault_client
        self._permissions_handler = permissions_handler
        self._tags_handler = tags_handler
        self._cache = ResourceCacheInvalidator(cache_client, "chat_agents", "chat_agent")

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

    def list_chat_agents(
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
        type_filter: str | None = None,
        use_cache: bool = True,
        id_list: list[str] | None = None,
    ) -> list[ChatAgentResponse] | list[QuickListItemResponse]:
        """
        Get a list of chat agents for a tenant (filtered by permissions).

        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by chat agent name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (chat agents must have AT LEAST ONE of the tags - OR logic)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching

        Returns:
            List of chat agent responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing chat agents", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        # Check if user is admin (has TENANT_GLOBAL_ADMIN or CHAT_AGENTS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            admin_permissions = [TenantRolesEnum.TENANT_GLOBAL_ADMIN.value, TenantRolesEnum.CHAT_AGENTS_ADMIN.value]
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
        type_key = type_filter or "all"
        cache_key = f"chat_agents:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}:type:{type_key}"

        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None or type_filter is not None or id_list is not None

        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached chat agent list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [ChatAgentResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached chat agent list: %s", e)

        with self.db_client.get_session() as session:
            query = (
                select(ChatAgent)
                .options(
                    selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag),
                    selectinload(ChatAgent.versions),
                )
                .where(ChatAgent.tenant_id == tenant_id)
            )

            # Filter by permissions if not admin
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)

                # Subquery for chat agents where user is a member
                member_subquery = (
                    select(ChatAgentMember.chat_agent_id)
                    .where(ChatAgentMember.tenant_id == tenant_id, ChatAgentMember.principal_id.in_(principal_ids))
                    .distinct()
                )

                query = query.where(ChatAgent.id.in_(member_subquery))

            if id_list:
                query = query.where(ChatAgent.id.in_(id_list))

            if type_filter:
                query = query.where(ChatAgent.type == type_filter)

            if name_filter:
                query = query.where(ChatAgent.name.ilike(f"%{name_filter}%"))

            # Filter by is_active status
            if is_active is not None:
                query = query.where(ChatAgent.is_active == bool(is_active))

            # Filter by tags (chat agents must have AT LEAST ONE of the specified tags - OR logic)
            if tag_ids:
                tag_subquery = (
                    select(ChatAgentTag.chat_agent_id)
                    .where(ChatAgentTag.tenant_id == tenant_id, ChatAgentTag.tag_id.in_(tag_ids))
                    .distinct()
                )
                query = query.where(ChatAgent.id.in_(tag_subquery))

            # Apply ordering if specified
            if order_by and hasattr(ChatAgent, order_by):
                column = getattr(ChatAgent, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())
            else:
                # MSSQL requires ORDER BY when using OFFSET/LIMIT
                query = query.order_by(ChatAgent.created_at.desc())

            query = query.offset(skip).limit(limit)
            chat_agents = session.execute(query).scalars().all()

            logger.info("Retrieved chat agents", extra={"count": len(chat_agents)})

            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=app.id, name=app.name) for app in chat_agents]

            result = [self._model_to_response(app) for app in chat_agents]

            if is_admin:
                for r in result:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in result]
                if resource_ids:
                    permissions = resolve_my_permissions_bulk(
                        session, ChatAgentMember, "chat_agent_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in result:
                        r.my_permission = permissions.get(r.id)

            # Cache the result (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached chat agent list")
                except Exception as e:
                    logger.warning("Failed to cache chat agent list: %s", e)

            return result

    def get_chat_agent(
        self, tenant_id: str, chat_agent_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> ChatAgentResponse:
        """
        Get a specific chat agent by ID.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent
            user: Optional user context for permission resolution
            use_cache: Whether to use caching

        Returns:
            Chat agent response

        Raises:
            ChatAgentNotFoundError: If chat agent not found
        """
        logger.info("Fetching chat agent", extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id})

        cache_key = f"chat_agents:detail:tenant:{tenant_id}:chat_agent:{chat_agent_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached chat agent")
                    result = ChatAgentResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(
                                session, tenant_id, chat_agent_id, user
                            )
                    return result
            except Exception as e:
                logger.warning("Failed to get cached chat agent: %s", e)

        with self.db_client.get_session() as session:
            query = (
                select(ChatAgent)
                .options(
                    selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag),
                    selectinload(ChatAgent.versions),
                )
                .where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            )
            chat_agent = session.execute(query).scalar_one_or_none()

            if not chat_agent:
                raise ChatAgentNotFoundError(chat_agent_id)

            result = self._model_to_response(chat_agent)

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached chat agent detail")
                except Exception as e:
                    logger.warning("Failed to cache chat agent: %s", e)

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, chat_agent_id, user)

            return result

    def create_chat_agent(
        self, tenant_id: str, request: CreateChatAgentRequest, user_id: str, user: ContextIdentityUser
    ) -> ChatAgentResponse:
        """
        Create a new chat agent.

        Args:
            tenant_id: The ID of the tenant
            request: Chat agent creation data
            user_id: The ID of the user creating the chat agent
            user: The authenticated user context (for IDP access)

        Returns:
            Created chat agent response

        Raises:
            ChatAgentConfigValidationError: If config validation fails
            UnsupportedChatAgentTypeError: If chat agent type is not supported for validation
        """
        logger.info("Creating chat agent", extra={"tenant_id": tenant_id, "app_name": request.name})

        is_react_agent = request.type == ChatAgentTypeEnum.REACT_AGENT

        validated_config: dict = {}
        if not is_react_agent and request.config:
            validated_config = ChatAgentConfigValidatorFactory.validate_config(
                chat_agent_type=request.type, config=request.config
            )

        chat_agent_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            if request.type == ChatAgentTypeEnum.LLM and validated_config.get("ai_model_id"):
                self._validate_ai_model_reference(session, tenant_id, validated_config["ai_model_id"])

            chat_agent = ChatAgent(
                id=chat_agent_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value,
                config=validated_config,
                is_active=request.is_active,
                embed_allowed_origins=request.embed_allowed_origins,
                greeting_messages=request.greeting_messages or [],
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(chat_agent)

            if is_react_agent:
                version = ReActAgentVersion(
                    id=str(uuid.uuid4()),
                    chat_agent_id=chat_agent_id,
                    version=1,
                    ai_model_ids=request.ai_model_ids,
                    system_prompt=request.system_prompt,
                    tool_ids=request.tool_ids,
                    security_prompt=request.security_prompt,
                    tool_use_prompt=request.tool_use_prompt,
                    response_prompt=request.response_prompt,
                    greeting_messages=request.greeting_messages,
                    config={},
                    created_by=user_id,
                    updated_by=user_id,
                )
                session.add(version)

            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="chat_agent",
                tenant_id=tenant_id,
                resource_id=chat_agent_id,
                user_id=user_id,
                user=user,
            )

            session.commit()

            query = (
                select(ChatAgent)
                .options(
                    selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag),
                    selectinload(ChatAgent.versions),
                )
                .where(ChatAgent.id == chat_agent_id)
            )
            chat_agent = session.execute(query).scalar_one()

            logger.info("Chat agent created", extra={"chat_agent_id": chat_agent_id})

            self._invalidate_list_cache(tenant_id)

            return self._model_to_response(chat_agent)

    def update_chat_agent(
        self, tenant_id: str, chat_agent_id: str, request: UpdateChatAgentRequest, user_id: str
    ) -> ChatAgentResponse:
        """
        Update an existing chat agent.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent
            request: Chat agent update data
            user_id: The ID of the user updating the chat agent

        Returns:
            Updated chat agent response

        Raises:
            ChatAgentNotFoundError: If chat agent not found
            ChatAgentConfigValidationError: If config validation fails
            UnsupportedChatAgentTypeError: If chat agent type is not supported for validation
        """
        logger.info("Updating chat agent", extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id})

        with self.db_client.get_session() as session:
            query = (
                select(ChatAgent)
                .options(selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag))
                .where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            )
            chat_agent = session.execute(query).scalar_one_or_none()

            if not chat_agent:
                raise ChatAgentNotFoundError(chat_agent_id)

            app_type = request.type if request.type is not None else ChatAgentTypeEnum(chat_agent.type)
            is_react_agent = app_type == ChatAgentTypeEnum.REACT_AGENT

            if request.name is not None:
                chat_agent.name = request.name
            if request.description is not None:
                chat_agent.description = request.description
            if request.type is not None:
                chat_agent.type = request.type.value
            if not is_react_agent and request.config is not None:
                validated_config = ChatAgentConfigValidatorFactory.validate_config(
                    chat_agent_type=app_type, config=request.config
                )
                if app_type == ChatAgentTypeEnum.LLM and validated_config.get("ai_model_id"):
                    self._validate_ai_model_reference(session, tenant_id, validated_config["ai_model_id"])
                chat_agent.config = validated_config
            if request.is_active is not None:
                chat_agent.is_active = request.is_active
            if request.embed_allowed_origins is not None:
                chat_agent.embed_allowed_origins = request.embed_allowed_origins
            if request.greeting_messages is not None:
                chat_agent.greeting_messages = request.greeting_messages

            chat_agent.updated_by = user_id

            session.commit()

            query = (
                select(ChatAgent)
                .options(
                    selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag),
                    selectinload(ChatAgent.versions),
                )
                .where(ChatAgent.id == chat_agent_id)
            )
            chat_agent = session.execute(query).scalar_one()

            logger.info("Chat agent updated", extra={"chat_agent_id": chat_agent_id})

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_agent_id)

            return self._model_to_response(chat_agent)

    def delete_chat_agent(self, tenant_id: str, chat_agent_id: str) -> None:
        """
        Delete a chat agent.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent

        Raises:
            ChatAgentNotFoundError: If chat agent not found
        """
        logger.info("Deleting chat agent", extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id})

        with self.db_client.get_session() as session:
            query = select(ChatAgent).where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            chat_agent = session.execute(query).scalar_one_or_none()

            if not chat_agent:
                raise ChatAgentNotFoundError(chat_agent_id)

            session.delete(chat_agent)

            # Clean up recent visits for this resource
            session.execute(
                delete(RecentVisit).where(
                    RecentVisit.tenant_id == tenant_id,
                    RecentVisit.resource_type == "chat_agent",
                    RecentVisit.resource_id == chat_agent_id,
                )
            )

            session.commit()

            logger.info("Chat agent deleted", extra={"chat_agent_id": chat_agent_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_agent_id)
            self._invalidate_permissions_cache(tenant_id, chat_agent_id)

    def duplicate_chat_agent(
        self, tenant_id: str, chat_agent_id: str, user_id: str, user: ContextIdentityUser
    ) -> ChatAgentResponse:
        """
        Duplicate an existing chat agent.

        Creates an exact copy of the chat agent with name + " Copy" (or " Copy(n)" if exists).
        Tags and ReACT agent versions are NOT copied.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent to duplicate
            user_id: The ID of the user performing the duplication
            user: The authenticated user context

        Returns:
            The newly created chat agent response

        Raises:
            ChatAgentNotFoundError: If the source chat agent is not found
        """
        logger.info("Duplicating chat agent", extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id})

        with self.db_client.get_session() as session:
            query = (
                select(ChatAgent)
                .options(selectinload(ChatAgent.versions))
                .where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            )
            source_agent = session.execute(query).scalar_one_or_none()
            if not source_agent:
                raise ChatAgentNotFoundError(chat_agent_id)

            new_name = self._generate_copy_name(session, tenant_id, source_agent.name)
            new_agent_id = str(uuid.uuid4())
            new_agent = ChatAgent(
                id=new_agent_id,
                tenant_id=tenant_id,
                name=new_name,
                description=source_agent.description,
                type=source_agent.type,
                config=source_agent.config.copy() if source_agent.config else {},
                is_active=source_agent.is_active,
                embed_allowed_origins=source_agent.embed_allowed_origins,
                greeting_messages=source_agent.greeting_messages.copy() if source_agent.greeting_messages else [],
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(new_agent)

            if source_agent.type == ChatAgentTypeEnum.REACT_AGENT.value and source_agent.versions:
                latest_version = max(source_agent.versions, key=lambda v: v.version)
                new_version = ReActAgentVersion(
                    id=str(uuid.uuid4()),
                    chat_agent_id=new_agent_id,
                    version=1,
                    ai_model_ids=latest_version.ai_model_ids.copy() if latest_version.ai_model_ids else [],
                    system_prompt=latest_version.system_prompt,
                    tool_ids=latest_version.tool_ids.copy() if latest_version.tool_ids else [],
                    security_prompt=latest_version.security_prompt,
                    tool_use_prompt=latest_version.tool_use_prompt,
                    response_prompt=latest_version.response_prompt,
                    greeting_messages=latest_version.greeting_messages.copy()
                    if latest_version.greeting_messages
                    else [],
                    config=latest_version.config.copy() if latest_version.config else {},
                    created_by=user_id,
                    updated_by=user_id,
                )
                session.add(new_version)

            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="chat_agent",
                tenant_id=tenant_id,
                resource_id=new_agent_id,
                user_id=user_id,
                user=user,
            )

            session.commit()

            query = (
                select(ChatAgent)
                .options(
                    selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag),
                    selectinload(ChatAgent.versions),
                )
                .where(ChatAgent.id == new_agent_id)
            )
            new_agent = session.execute(query).scalar_one()

            logger.info(
                "Chat agent duplicated",
                extra={"source_id": chat_agent_id, "new_id": new_agent_id, "new_name": new_name},
            )
            self._invalidate_list_cache(tenant_id)
            return self._model_to_response(new_agent)

    def _generate_copy_name(self, session: Session, tenant_id: str, original_name: str) -> str:
        """
        Generate a unique copy name for duplicated resources.

        Args:
            session: SQLAlchemy session
            tenant_id: The tenant ID
            original_name: The original resource name

        Returns:
            A unique name like "Original Copy" or "Original Copy(2)"
        """
        base_name = f"{original_name} Copy"
        query = (
            select(func.count())
            .select_from(ChatAgent)
            .where(ChatAgent.tenant_id == tenant_id, ChatAgent.name.like(f"{original_name} Copy%"))
        )
        count = session.execute(query).scalar() or 0

        if count == 0:
            return base_name
        return f"{base_name}({count + 1})"

    def get_chat_agent_config(
        self, tenant_id: str, chat_agent_id: str, user: ContextIdentityUser, credential_handler
    ) -> ChatAgentConfigResponse:
        """
        Get the full chat agent configuration including credential secrets and user data.
        This endpoint is for the agent-service to fetch complete configuration.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent
            user: The authenticated user context
            credential_handler: Credential handler for fetching secrets

        Returns:
            ChatAgentConfigResponse with full config including secrets

        Raises:
            ChatAgentNotFoundError: If chat agent not found
            InvalidCredentialError: If a credential cannot be fetched
        """
        import json

        logger.info("Fetching chat agent config", extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id})

        with self.db_client.get_session() as session:
            query = select(ChatAgent).where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            chat_agent = session.execute(query).scalar_one_or_none()

            if not chat_agent:
                raise ChatAgentNotFoundError(chat_agent_id)

            app_type = ChatAgentTypeEnum(chat_agent.type)
            config = chat_agent.config or {}

            # Build user info
            from unifiedui.schema.responses.chat_agents import (
                CredentialSecretResponse,
                N8NConfigSettingsResponse,
                UserInfoResponse,
            )

            user_info = UserInfoResponse(
                id=user.identity.get_id(),
                display_name=user.identity.get_display_name(),
                principal_name=user.identity.get_principal_name(),
                mail=user.identity.get_mail(),
            )

            # Build settings based on chat agent type
            if app_type == ChatAgentTypeEnum.N8N:
                # Fetch API credential
                api_credential_id = config.get("api_api_key_credential_id")
                chat_credential_id = config.get("chat_auth_credential_id")

                if not api_credential_id:
                    raise InvalidCredentialError(
                        credential_id="unknown",
                        message="Chat agent config is missing required API credential ID",
                    )

                # Fetch API credentials with secrets
                try:
                    api_credential = credential_handler.get_credential(tenant_id, api_credential_id)
                    api_secret = credential_handler.get_credential_secret(tenant_id, api_credential_id)
                except Exception as e:
                    logger.error("Failed to fetch API credential: %s", e)
                    raise InvalidCredentialError(
                        credential_id=api_credential_id,
                        message=f"Invalid or inaccessible API credential with ID '{api_credential_id}'",
                    )

                api_secret_value = api_secret

                api_credentials = CredentialSecretResponse(
                    id=api_credential.id,
                    credentials_uri=api_credential.credential_uri,
                    name=api_credential.name,
                    description=api_credential.description,
                    type=api_credential.type,
                    is_active=api_credential.is_active,
                    secret=api_secret_value,
                )

                # Fetch optional chat auth credentials
                chat_credentials: CredentialSecretResponse | None = None
                if chat_credential_id:
                    try:
                        chat_credential = credential_handler.get_credential(tenant_id, chat_credential_id)
                        chat_secret = credential_handler.get_credential_secret(tenant_id, chat_credential_id)
                    except Exception as e:
                        logger.error("Failed to fetch chat credential: %s", e)
                        raise InvalidCredentialError(
                            credential_id=chat_credential_id,
                            message=f"Invalid or inaccessible chat credential with ID '{chat_credential_id}'",
                        )

                    chat_secret_value = chat_secret
                    if chat_credential.type == "BASIC_AUTH":
                        try:
                            chat_secret_value = json.loads(chat_secret)
                        except json.JSONDecodeError:
                            chat_secret_value = chat_secret

                    chat_credentials = CredentialSecretResponse(
                        id=chat_credential.id,
                        credentials_uri=chat_credential.credential_uri,
                        name=chat_credential.name,
                        description=chat_credential.description,
                        type=chat_credential.type,
                        is_active=chat_credential.is_active,
                        secret=chat_secret_value,
                    )

                settings: (
                    N8NConfigSettingsResponse
                    | MicrosoftFoundryConfigSettingsResponse
                    | RestApiConfigSettingsResponse
                    | LLMConfigSettingsResponse
                    | ReActAgentConfigSettingsResponse
                    | dict[Any, Any]
                ) = N8NConfigSettingsResponse(
                    api_version=config.get("api_version", "v1"),
                    workflow_type=config.get("workflow_type", "N8N_CHAT_AGENT_WORKFLOW"),
                    use_unified_chat_history=config.get("use_unified_chat_history", True),
                    chat_history_count=config.get("chat_history_count", 30),
                    chat_url=config.get("chat_url", ""),
                    workflow_id=self._extract_workflow_id(config.get("workflow_endpoint", "")),
                    n8n_host=self._extract_n8n_host(config.get("workflow_endpoint", "")),
                    api_credentials=api_credentials,
                    chat_credentials=chat_credentials,
                )
            elif app_type == ChatAgentTypeEnum.MICROSOFT_FOUNDRY:
                # For Microsoft Foundry, return the config settings
                from unifiedui.schema.responses.chat_agents import MicrosoftFoundryConfigSettingsResponse

                settings = MicrosoftFoundryConfigSettingsResponse(
                    api_version=config.get("api_version", "2025-11-15-preview"),
                    agent_type=config.get("agent_type", "AGENT"),
                    project_endpoint=config.get("project_endpoint", ""),
                    agent_name=config.get("agent_name", ""),
                )
            elif app_type == ChatAgentTypeEnum.REST_API:
                from unifiedui.schema.responses.chat_agents import RestApiConfigSettingsResponse

                credential_response = None
                access_token = None
                credential_id = config.get("credential_id")
                auth_type = config.get("auth_type", "ANONYMOUS")

                if credential_id and auth_type not in ("ANONYMOUS", "ENTRA_ID_USER_TOKEN"):
                    try:
                        credential = credential_handler.get_credential(tenant_id, credential_id)
                        secret = credential_handler.get_credential_secret(tenant_id, credential_id)

                        secret_value: str | dict = secret
                        if credential.type in ("BASIC_AUTH", "ENTRA_ID_APP_REGISTRATION"):
                            try:
                                secret_value = json.loads(secret) if isinstance(secret, str) else secret
                            except json.JSONDecodeError:
                                secret_value = secret

                        credential_response = CredentialSecretResponse(
                            id=credential.id,
                            credentials_uri=credential.credential_uri,
                            name=credential.name,
                            description=credential.description,
                            type=credential.type,
                            is_active=credential.is_active,
                            secret=secret_value,
                        )

                        if auth_type == "ENTRA_ID_APP_REGISTRATION" and isinstance(secret_value, dict):
                            from unifiedui.core.identity.client_credentials import ClientCredentialsTokenClient

                            cc_client = ClientCredentialsTokenClient(
                                tenant_id=secret_value["tenant_id"],
                                client_id=secret_value["client_id"],
                                client_secret=secret_value["client_secret"],
                            )
                            try:
                                access_token = cc_client.acquire_token()
                            except ValueError as e:
                                logger.error("Failed to acquire client credentials token: %s", e)

                    except Exception as e:
                        logger.error("Failed to fetch REST API credential: %s", e)
                        raise InvalidCredentialError(
                            credential_id=credential_id,
                            message=f"Invalid or inaccessible credential with ID '{credential_id}'",
                        )

                settings = RestApiConfigSettingsResponse(
                    auth_type=auth_type,
                    invoke_endpoint=config.get("invoke_endpoint", ""),
                    credential=credential_response,
                    api_key_header_name=config.get("api_key_header_name", "X-API-Key"),
                    access_token=access_token,
                    use_unified_chat_history=config.get("use_unified_chat_history", True),
                    chat_history_count=config.get("chat_history_count", 30),
                    create_conversation_endpoint=config.get("create_conversation_endpoint"),
                )
            elif app_type == ChatAgentTypeEnum.REACT_AGENT:
                from unifiedui.core.database.models import ReActAgentVersion, Tool
                from unifiedui.schema.responses.re_act_agents import (
                    ReActAgentAIModelResponse,
                    ReActAgentConfigSettingsResponse,
                )

                latest_version = session.execute(
                    select(ReActAgentVersion)
                    .where(ReActAgentVersion.chat_agent_id == chat_agent_id)
                    .order_by(ReActAgentVersion.version.desc())
                    .limit(1)
                ).scalar_one_or_none()

                if not latest_version:
                    raise ChatAgentNotFoundError(chat_agent_id)

                resolved_tools: list[dict] = []
                if latest_version.tool_ids:
                    tools = (
                        session.execute(
                            select(Tool).where(
                                Tool.id.in_(latest_version.tool_ids),
                                Tool.tenant_id == tenant_id,
                            )
                        )
                        .scalars()
                        .all()
                    )

                    for tool in tools:
                        tool_data: dict = {
                            "id": tool.id,
                            "name": tool.name,
                            "type": tool.type,
                            "config": tool.config or {},
                        }
                        if tool.credential_id:
                            try:
                                cred = credential_handler.get_credential(tenant_id, tool.credential_id)
                                secret = credential_handler.get_credential_secret(tenant_id, tool.credential_id)
                                tool_data["credential"] = {
                                    "id": cred.id,
                                    "type": cred.type,
                                    "secret": secret,
                                }
                            except Exception as e:
                                logger.warning("Failed to resolve credential for tool %s: %s", tool.id, e)
                        resolved_tools.append(tool_data)

                resolved_ai_models: list[ReActAgentAIModelResponse] = []
                if latest_version.ai_model_ids:
                    ai_models = (
                        session.execute(
                            select(TenantAIModel).where(
                                TenantAIModel.id.in_(latest_version.ai_model_ids),
                                TenantAIModel.tenant_id == tenant_id,
                            )
                        )
                        .scalars()
                        .all()
                    )

                    for ai_model in ai_models:
                        credential_secret = None
                        if ai_model.credential_id:
                            try:
                                secret = credential_handler.get_credential_secret(tenant_id, ai_model.credential_id)
                                credential_secret = secret if isinstance(secret, dict) else {"api_key": secret}
                            except Exception as e:
                                logger.warning("Failed to resolve credential for AI model %s: %s", ai_model.id, e)
                        resolved_ai_models.append(
                            ReActAgentAIModelResponse(
                                id=ai_model.id,
                                provider=ai_model.provider,
                                config=ai_model.config or {},
                                credential_secret=credential_secret,
                                priority=ai_model.priority,
                            )
                        )

                settings = ReActAgentConfigSettingsResponse(
                    chat_agent_id=chat_agent_id,
                    version=latest_version.version,
                    ai_model_ids=latest_version.ai_model_ids or [],
                    ai_models=resolved_ai_models,
                    system_prompt=latest_version.system_prompt,
                    tool_ids=latest_version.tool_ids or [],
                    tools=resolved_tools,
                    security_prompt=latest_version.security_prompt,
                    tool_use_prompt=latest_version.tool_use_prompt,
                    response_prompt=latest_version.response_prompt,
                    greeting_messages=latest_version.greeting_messages or [],
                    config=latest_version.config or {},
                )
            elif app_type == ChatAgentTypeEnum.LLM:
                from unifiedui.schema.responses.chat_agents import (
                    LLMConfigSettingsResponse,
                    LLMResolvedAIModelResponse,
                )

                llm_ai_model_id = config.get("ai_model_id", "")
                llm_model = session.execute(
                    select(TenantAIModel).where(
                        TenantAIModel.id == llm_ai_model_id,
                        TenantAIModel.tenant_id == tenant_id,
                    )
                ).scalar_one_or_none()

                if not llm_model:
                    raise ChatAgentNotFoundError(chat_agent_id)

                llm_credential_secret = None
                if llm_model.credential_id:
                    try:
                        secret = credential_handler.get_credential_secret(tenant_id, llm_model.credential_id)
                        llm_credential_secret = secret if isinstance(secret, dict) else {"api_key": secret}
                    except Exception as e:
                        logger.warning("Failed to resolve credential for AI model %s: %s", llm_model.id, e)

                resolved_model = LLMResolvedAIModelResponse(
                    id=llm_model.id,
                    provider=llm_model.provider,
                    config=llm_model.config or {},
                    credential_secret=llm_credential_secret,
                )

                settings = LLMConfigSettingsResponse(
                    ai_model_id=llm_ai_model_id,
                    ai_model=resolved_model,
                    system_prompt=config.get("system_prompt"),
                    use_unified_chat_history=True,
                    chat_history_count=30,
                )
            else:
                # For unsupported types, return raw config
                settings = config

            return ChatAgentConfigResponse(
                docversion="v1",
                type=app_type,
                tenant_id=tenant_id,
                chat_agent_id=chat_agent_id,
                settings=settings,
                user=user_info,
            )

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        self._cache.invalidate_list(tenant_id)

    def _invalidate_detail_cache(self, tenant_id: str, chat_agent_id: str) -> None:
        """Invalidate detail cache for a chat agent."""
        self._cache.invalidate_detail(tenant_id, chat_agent_id)

    def _invalidate_permissions_cache(self, tenant_id: str, chat_agent_id: str) -> None:
        """Invalidate permissions cache for a chat agent."""
        self._cache.invalidate_permissions(tenant_id, chat_agent_id)

    # ========== Version Management Methods (REACT_AGENT) ==========

    def update_chat_agent_version(
        self, tenant_id: str, chat_agent_id: str, request: UpdateReActAgentVersionRequest, user_id: str
    ) -> ChatAgentResponse:
        """Create a new version of the chat agent config (REACT_AGENT only).

        Takes the latest version, applies the partial update, and saves as a new version.

        Args:
            tenant_id: Tenant ID for scoping
            chat_agent_id: Chat agent ID
            request: Version config update data
            user_id: ID of the updating user

        Returns:
            Updated chat agent response with new latest version

        Raises:
            ChatAgentNotFoundError: If chat agent not found
        """
        logger.info(
            "Creating new chat agent version",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id},
        )

        with self.db_client.get_session() as session:
            chat_agent = session.execute(
                select(ChatAgent).where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            ).scalar_one_or_none()

            if not chat_agent:
                raise ChatAgentNotFoundError(chat_agent_id)

            latest_version = session.execute(
                select(ReActAgentVersion)
                .where(ReActAgentVersion.chat_agent_id == chat_agent_id)
                .order_by(ReActAgentVersion.version.desc())
                .limit(1)
            ).scalar_one_or_none()

            next_version_num = (latest_version.version + 1) if latest_version else 1

            new_version = ReActAgentVersion(
                id=str(uuid.uuid4()),
                chat_agent_id=chat_agent_id,
                version=next_version_num,
                ai_model_ids=(
                    request.ai_model_ids
                    if request.ai_model_ids is not None
                    else (latest_version.ai_model_ids if latest_version else [])
                ),
                system_prompt=(
                    request.system_prompt
                    if request.system_prompt is not None
                    else (latest_version.system_prompt if latest_version else None)
                ),
                tool_ids=(
                    request.tool_ids
                    if request.tool_ids is not None
                    else (latest_version.tool_ids if latest_version else [])
                ),
                security_prompt=(
                    request.security_prompt
                    if request.security_prompt is not None
                    else (latest_version.security_prompt if latest_version else None)
                ),
                tool_use_prompt=(
                    request.tool_use_prompt
                    if request.tool_use_prompt is not None
                    else (latest_version.tool_use_prompt if latest_version else None)
                ),
                response_prompt=(
                    request.response_prompt
                    if request.response_prompt is not None
                    else (latest_version.response_prompt if latest_version else None)
                ),
                greeting_messages=(
                    request.greeting_messages
                    if request.greeting_messages is not None
                    else (latest_version.greeting_messages if latest_version else [])
                ),
                config=(
                    request.config if request.config is not None else (latest_version.config if latest_version else {})
                ),
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(new_version)

            chat_agent.updated_by = user_id
            session.commit()

            query = (
                select(ChatAgent)
                .options(
                    selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag),
                    selectinload(ChatAgent.versions),
                )
                .where(ChatAgent.id == chat_agent_id)
            )
            chat_agent = session.execute(query).scalar_one()

            logger.info(
                "Chat agent version created",
                extra={"chat_agent_id": chat_agent_id, "version": next_version_num},
            )

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_agent_id)

            return self._model_to_response(chat_agent)

    def list_chat_agent_versions(
        self,
        tenant_id: str,
        chat_agent_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ReActAgentVersionResponse]:
        """List all versions of a chat agent (REACT_AGENT only).

        Args:
            tenant_id: Tenant ID for scoping
            chat_agent_id: Chat agent ID
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of version responses ordered by version descending

        Raises:
            ChatAgentNotFoundError: If chat agent not found
        """
        logger.info(
            "Listing chat agent versions",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id},
        )

        with self.db_client.get_session() as session:
            agent_exists = session.execute(
                select(func.count())
                .select_from(ChatAgent)
                .where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            ).scalar_one()

            if not agent_exists:
                raise ChatAgentNotFoundError(chat_agent_id)

            versions = (
                session.execute(
                    select(ReActAgentVersion)
                    .where(ReActAgentVersion.chat_agent_id == chat_agent_id)
                    .order_by(ReActAgentVersion.version.desc())
                    .offset(skip)
                    .limit(limit)
                )
                .scalars()
                .all()
            )

            return [self._version_to_response(v) for v in versions]

    def get_chat_agent_version(
        self,
        tenant_id: str,
        chat_agent_id: str,
        version: int,
    ) -> ReActAgentVersionResponse:
        """Get a specific version of a chat agent (REACT_AGENT only).

        Args:
            tenant_id: Tenant ID for scoping
            chat_agent_id: Chat agent ID
            version: Version number

        Returns:
            Version response

        Raises:
            ChatAgentNotFoundError: If chat agent not found
            ReActAgentVersionNotFoundError: If version not found
        """
        logger.info(
            "Fetching chat agent version",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "version": version},
        )

        with self.db_client.get_session() as session:
            agent_exists = session.execute(
                select(func.count())
                .select_from(ChatAgent)
                .where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            ).scalar_one()

            if not agent_exists:
                raise ChatAgentNotFoundError(chat_agent_id)

            version_record = session.execute(
                select(ReActAgentVersion).where(
                    ReActAgentVersion.chat_agent_id == chat_agent_id,
                    ReActAgentVersion.version == version,
                )
            ).scalar_one_or_none()

            if not version_record:
                raise ReActAgentVersionNotFoundError(chat_agent_id, version)

            return self._version_to_response(version_record)

    def restore_chat_agent_version(
        self,
        tenant_id: str,
        chat_agent_id: str,
        version: int,
        user_id: str,
    ) -> ChatAgentResponse:
        """Restore a previous version by creating a new version with the same config.

        Args:
            tenant_id: Tenant ID for scoping
            chat_agent_id: Chat agent ID
            version: Version number to restore
            user_id: ID of the restoring user

        Returns:
            Updated chat agent response with the restored version as latest

        Raises:
            ChatAgentNotFoundError: If chat agent not found
            ReActAgentVersionNotFoundError: If version not found
        """
        logger.info(
            "Restoring chat agent version",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "version": version},
        )

        with self.db_client.get_session() as session:
            chat_agent = session.execute(
                select(ChatAgent).where(ChatAgent.id == chat_agent_id, ChatAgent.tenant_id == tenant_id)
            ).scalar_one_or_none()

            if not chat_agent:
                raise ChatAgentNotFoundError(chat_agent_id)

            source_version = session.execute(
                select(ReActAgentVersion).where(
                    ReActAgentVersion.chat_agent_id == chat_agent_id,
                    ReActAgentVersion.version == version,
                )
            ).scalar_one_or_none()

            if not source_version:
                raise ReActAgentVersionNotFoundError(chat_agent_id, version)

            latest_version_num = (
                session.execute(
                    select(func.max(ReActAgentVersion.version)).where(ReActAgentVersion.chat_agent_id == chat_agent_id)
                ).scalar_one()
                or 0
            )

            new_version = ReActAgentVersion(
                id=str(uuid.uuid4()),
                chat_agent_id=chat_agent_id,
                version=latest_version_num + 1,
                ai_model_ids=source_version.ai_model_ids,
                system_prompt=source_version.system_prompt,
                tool_ids=source_version.tool_ids,
                security_prompt=source_version.security_prompt,
                tool_use_prompt=source_version.tool_use_prompt,
                response_prompt=source_version.response_prompt,
                greeting_messages=source_version.greeting_messages,
                config=source_version.config,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(new_version)

            chat_agent.updated_by = user_id
            session.commit()

            query = (
                select(ChatAgent)
                .options(
                    selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag),
                    selectinload(ChatAgent.versions),
                )
                .where(ChatAgent.id == chat_agent_id)
            )
            chat_agent = session.execute(query).scalar_one()

            logger.info(
                "Chat agent version restored",
                extra={
                    "chat_agent_id": chat_agent_id,
                    "source_version": version,
                    "new_version": latest_version_num + 1,
                },
            )

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_agent_id)

            return self._model_to_response(chat_agent)

    # ========== Permission Management Methods ==========

    def list_chat_agent_permissions(
        self,
        tenant_id: str,
        chat_agent_id: str,
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
        List all permissions for a chat agent, grouped by principal.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent
            skip: Number of principals to skip
            limit: Maximum number of principals to return
            search: Search term for display_name, principal_name, or mail
            roles: Filter by roles (OR logic)
            is_active: Filter by is_active status
            order_by: Column to order by
            order_direction: Sort direction
            use_cache: Whether to use caching

        Returns:
            Unified ResourcePrincipalsResponse with enriched principal data

        Raises:
            ChatAgentNotFoundError: If chat agent not found
        """
        logger.info("Listing chat agent permissions", extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id})

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="chat_agent",
                tenant_id=tenant_id,
                resource_id=chat_agent_id,
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
            raise ChatAgentNotFoundError(chat_agent_id) from e

        # Convert to unified response schema
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
            resource_id=chat_agent_id, resource_type="chat_agent", tenant_id=tenant_id, principals=principals
        )

    def get_chat_agent_permission(
        self, tenant_id: str, chat_agent_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """
        Get all permissions for a specific principal on a chat agent.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent
            principal_id: The ID of the principal

        Returns:
            Unified PrincipalWithRolesResponse with enriched principal data

        Raises:
            ChatAgentNotFoundError: If chat agent or permission not found
        """
        logger.info(
            "Getting chat agent permission",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "principal_id": principal_id},
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="chat_agent", tenant_id=tenant_id, resource_id=chat_agent_id, principal_id=principal_id
            )
        except ValueError as e:
            raise ChatAgentNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_chat_agent_permission(
        self,
        tenant_id: str,
        chat_agent_id: str,
        request: SetResourcePermissionRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """
        Set or update a permission for a principal on a chat agent.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent
            request: Permission data
            user_id: The ID of the user setting the permission

        Returns:
            Updated principal with their roles

        Raises:
            ChatAgentNotFoundError: If chat agent not found
        """
        logger.info(
            "Setting chat agent permission",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "principal_id": request.principal_id},
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="chat_agent",
                tenant_id=tenant_id,
                resource_id=chat_agent_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )

            # Fetch and return the updated permission with all enriched data
            result = self.permissions_handler.get_permission(
                resource_type="chat_agent",
                tenant_id=tenant_id,
                resource_id=chat_agent_id,
                principal_id=request.principal_id,
            )
        except ValueError as e:
            raise ChatAgentNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def delete_chat_agent_permission(
        self, tenant_id: str, chat_agent_id: str, principal_id: str, principal_type: str, permission: str
    ) -> None:
        """
        Delete a specific permission for a principal on a chat agent.

        Args:
            tenant_id: The ID of the tenant
            chat_agent_id: The ID of the chat agent
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to delete

        Raises:
            ChatAgentNotFoundError: If chat agent or permission not found
        """
        logger.info(
            "Deleting chat agent permission",
            extra={
                "tenant_id": tenant_id,
                "chat_agent_id": chat_agent_id,
                "principal_id": principal_id,
                "permission": permission,
            },
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="chat_agent",
                tenant_id=tenant_id,
                resource_id=chat_agent_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission,
            )
        except ValueError as e:
            raise ChatAgentNotFoundError(str(e)) from e

    @staticmethod
    def _extract_workflow_id(workflow_endpoint: str) -> str:
        """
        Extract the workflow ID from a workflow endpoint URL.

        Example: https://n8n.example.com/workflow/abc123 -> abc123

        Args:
            workflow_endpoint: The full workflow endpoint URL

        Returns:
            The workflow ID extracted from the URL
        """
        if not workflow_endpoint:
            return ""
        # Split by '/workflow/' and get the part after it
        parts = workflow_endpoint.split("/workflow/")
        if len(parts) < 2:
            return ""
        # Return the workflow ID (everything after /workflow/, strip any trailing slashes or paths)
        workflow_part = parts[1]
        # Remove any trailing path components or query strings
        workflow_id = workflow_part.split("/")[0].split("?")[0]
        return workflow_id

    @staticmethod
    def _extract_n8n_host(workflow_endpoint: str) -> str:
        """
        Extract the N8N host URL from a workflow endpoint URL.

        Example: https://n8n.example.com/workflow/abc123 -> https://n8n.example.com

        Args:
            workflow_endpoint: The full workflow endpoint URL

        Returns:
            The N8N host URL (scheme + host)
        """
        if not workflow_endpoint:
            return ""
        from urllib.parse import urlparse

        parsed = urlparse(workflow_endpoint)
        if not parsed.scheme or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _validate_ai_model_reference(session: Session, tenant_id: str, ai_model_id: str) -> None:
        """Validate that the referenced AI model exists and is active for the tenant.

        Args:
            session: Active database session
            tenant_id: The tenant ID to scope the query
            ai_model_id: The AI model ID to validate

        Raises:
            InvalidAIModelReferenceError: If AI model not found or inactive
        """
        ai_model = session.execute(
            select(TenantAIModel).where(
                TenantAIModel.id == ai_model_id,
                TenantAIModel.tenant_id == tenant_id,
                TenantAIModel.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if not ai_model:
            raise InvalidAIModelReferenceError(ai_model_id)

    @staticmethod
    def _model_to_response(chat_agent: ChatAgent) -> ChatAgentResponse:
        """Convert ChatAgent model to ChatAgentResponse."""
        tags = []
        if hasattr(chat_agent, "tags") and chat_agent.tags:
            for app_tag in chat_agent.tags:
                if app_tag.tag:
                    tags.append(TagSummary(id=app_tag.tag.id, name=app_tag.tag.name))

        version_fields: dict = {}
        if (
            ChatAgentTypeEnum(chat_agent.type) == ChatAgentTypeEnum.REACT_AGENT
            and hasattr(chat_agent, "versions")
            and chat_agent.versions
        ):
            latest = chat_agent.versions[0]
            version_fields = {
                "current_version": latest.version,
                "ai_model_ids": latest.ai_model_ids or [],
                "system_prompt": latest.system_prompt,
                "tool_ids": latest.tool_ids or [],
                "security_prompt": latest.security_prompt,
                "tool_use_prompt": latest.tool_use_prompt,
                "response_prompt": latest.response_prompt,
                "greeting_messages": latest.greeting_messages or [],
            }

        greeting_messages = version_fields.pop("greeting_messages", None) or (chat_agent.greeting_messages or [])

        return ChatAgentResponse(
            id=chat_agent.id,
            tenant_id=chat_agent.tenant_id,
            name=chat_agent.name,
            description=chat_agent.description,
            type=chat_agent.type,
            is_active=chat_agent.is_active,
            embed_allowed_origins=chat_agent.embed_allowed_origins,
            config=chat_agent.config,
            tags=tags,
            created_at=chat_agent.created_at,
            updated_at=chat_agent.updated_at,
            created_by=chat_agent.created_by,
            updated_by=chat_agent.updated_by,
            greeting_messages=greeting_messages,
            **version_fields,
        )

    @staticmethod
    def _version_to_response(version: ReActAgentVersion) -> ReActAgentVersionResponse:
        """Convert a ReACT agent version model to a response.

        Args:
            version: ReACT agent version model instance

        Returns:
            ReACT agent version response
        """
        return ReActAgentVersionResponse(
            id=version.id,
            chat_agent_id=version.chat_agent_id,
            version=version.version,
            ai_model_ids=version.ai_model_ids or [],
            system_prompt=version.system_prompt,
            tool_ids=version.tool_ids or [],
            security_prompt=version.security_prompt,
            tool_use_prompt=version.tool_use_prompt,
            response_prompt=version.response_prompt,
            greeting_messages=version.greeting_messages or [],
            config=version.config or {},
            created_at=version.created_at,
            updated_at=version.updated_at,
            created_by=version.created_by,
            updated_by=version.updated_by,
        )

    def _resolve_user_permission(
        self, session: Session, tenant_id: str, chat_agent_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific chat agent.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            chat_agent_id: Chat agent ID
            user: The authenticated user context

        Returns:
            Permission action string or None
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(user, tenant_id, [TenantRolesEnum.TENANT_GLOBAL_ADMIN, TenantRolesEnum.CHAT_AGENTS_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(session, ChatAgentMember, "chat_agent_id", tenant_id, chat_agent_id, principal_ids)
