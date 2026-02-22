"""Business logic handlers for chat agent operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import ChatAgentTypeEnum, PermissionActionEnum
from unifiedui.core.database.models import ChatAgent, ChatAgentMember, ChatAgentTag
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
    from unifiedui.core.vault.client import BaseVaultClient
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler
    from unifiedui.schema.requests.chat_agent_permissions import SetChatAgentPermissionRequest
    from unifiedui.schema.requests.chat_agents import CreateChatAgentRequest, UpdateChatAgentRequest

from unifiedui.exc.chat_agent_config import (
    InvalidCredentialError,
)
from unifiedui.exc.chat_agents import ChatAgentNotFoundError
from unifiedui.handlers.validators.chat_agent_config import ChatAgentConfigValidatorFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.chat_agents import ChatAgentConfigResponse, ChatAgentResponse
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
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
        use_cache: bool = True,
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
        cache_key = f"chat_agents:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"

        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None

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
                logger.warning(f"Failed to get cached chat agent list: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(ChatAgent)
                .options(selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag))
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
                    logger.warning(f"Failed to cache chat agent list: {e}")

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
                logger.warning(f"Failed to get cached chat agent: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(ChatAgent)
                .options(selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag))
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
                    logger.warning(f"Failed to cache chat agent: {e}")

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

        # Validate config based on chat agent type
        validated_config = {}
        if request.config:
            validated_config = ChatAgentConfigValidatorFactory.validate_config(
                chat_agent_type=request.type, config=request.config
            )

        chat_agent_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            # Create chat agent
            chat_agent = ChatAgent(
                id=chat_agent_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value,
                config=validated_config,
                is_active=request.is_active,
                embed_allowed_origins=request.embed_allowed_origins,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(chat_agent)

            # Add creator as admin member using central handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="chat_agent",
                tenant_id=tenant_id,
                resource_id=chat_agent_id,
                user_id=user_id,
                user=user,
            )

            session.commit()
            session.refresh(chat_agent)

            logger.info("Chat agent created", extra={"chat_agent_id": chat_agent_id})

            # Invalidate cache
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

            # Determine the chat agent type for config validation
            app_type = request.type if request.type is not None else ChatAgentTypeEnum(chat_agent.type)

            # Update fields if provided
            if request.name is not None:
                chat_agent.name = request.name
            if request.description is not None:
                chat_agent.description = request.description
            if request.type is not None:
                chat_agent.type = request.type.value
            if request.config is not None:
                # Validate config based on chat agent type
                validated_config = ChatAgentConfigValidatorFactory.validate_config(
                    chat_agent_type=app_type, config=request.config
                )
                chat_agent.config = validated_config
            if request.is_active is not None:
                chat_agent.is_active = request.is_active
            if request.embed_allowed_origins is not None:
                chat_agent.embed_allowed_origins = request.embed_allowed_origins

            chat_agent.updated_by = user_id

            session.commit()
            session.refresh(chat_agent)

            # Re-fetch with tags for response
            query = (
                select(ChatAgent)
                .options(selectinload(ChatAgent.tags).selectinload(ChatAgentTag.tag))
                .where(ChatAgent.id == chat_agent_id)
            )
            chat_agent = session.execute(query).scalar_one()

            logger.info("Chat agent updated", extra={"chat_agent_id": chat_agent_id})

            # Invalidate cache
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
            session.commit()

            logger.info("Chat agent deleted", extra={"chat_agent_id": chat_agent_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, chat_agent_id)
            self._invalidate_permissions_cache(tenant_id, chat_agent_id)

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

                if not api_credential_id or not chat_credential_id:
                    raise InvalidCredentialError(
                        credential_id=api_credential_id or chat_credential_id or "unknown",
                        message="Chat agent config is missing required credential IDs",
                    )

                # Fetch credentials with secrets
                try:
                    api_credential = credential_handler.get_credential(tenant_id, api_credential_id)
                    api_secret = credential_handler.get_credential_secret(tenant_id, api_credential_id)
                except Exception as e:
                    logger.error(f"Failed to fetch API credential: {e}")
                    raise InvalidCredentialError(
                        credential_id=api_credential_id,
                        message=f"Invalid or inaccessible API credential with ID '{api_credential_id}'",
                    )

                try:
                    chat_credential = credential_handler.get_credential(tenant_id, chat_credential_id)
                    chat_secret = credential_handler.get_credential_secret(tenant_id, chat_credential_id)
                except Exception as e:
                    logger.error(f"Failed to fetch chat credential: {e}")
                    raise InvalidCredentialError(
                        credential_id=chat_credential_id,
                        message=f"Invalid or inaccessible chat credential with ID '{chat_credential_id}'",
                    )

                # Parse secrets based on credential type
                api_secret_value = api_secret
                chat_secret_value = chat_secret

                # For BASIC_AUTH, parse as JSON dict
                if chat_credential.type == "BASIC_AUTH":
                    try:
                        chat_secret_value = json.loads(chat_secret)
                    except json.JSONDecodeError:
                        chat_secret_value = chat_secret

                api_credentials = CredentialSecretResponse(
                    id=api_credential.id,
                    credentials_uri=api_credential.credential_uri,
                    name=api_credential.name,
                    description=api_credential.description,
                    type=api_credential.type,
                    is_active=api_credential.is_active,
                    secret=api_secret_value,
                )

                chat_credentials = CredentialSecretResponse(
                    id=chat_credential.id,
                    credentials_uri=chat_credential.credential_uri,
                    name=chat_credential.name,
                    description=chat_credential.description,
                    type=chat_credential.type,
                    is_active=chat_credential.is_active,
                    secret=chat_secret_value,
                )

                settings = N8NConfigSettingsResponse(
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
        if self.cache_client:
            pattern = f"chat_agents:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, chat_agent_id: str) -> None:
        """Invalidate detail cache for a chat agent."""
        if self.cache_client:
            cache_key = f"chat_agents:detail:tenant:{tenant_id}:chat_agent:{chat_agent_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, chat_agent_id: str) -> None:
        """Invalidate permissions cache for a chat agent."""
        if self.cache_client:
            pattern = f"chat_agents:permissions:tenant:{tenant_id}:chat_agent:{chat_agent_id}:*"
            self.cache_client.client.delete_pattern(pattern)

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
        request: SetChatAgentPermissionRequest,
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
    def _model_to_response(chat_agent: ChatAgent) -> ChatAgentResponse:
        """Convert ChatAgent model to ChatAgentResponse."""
        # Extract tags from the chat agent's tags relationship
        tags = []
        if hasattr(chat_agent, "tags") and chat_agent.tags:
            for app_tag in chat_agent.tags:
                if app_tag.tag:
                    tags.append(TagSummary(id=app_tag.tag.id, name=app_tag.tag.name))

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
        )

    def _resolve_user_permission(
        self, session: object, tenant_id: str, chat_agent_id: str, user: ContextIdentityUser
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
