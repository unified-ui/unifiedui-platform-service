"""Business logic handlers for autonomous agent operations."""

from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import AutonomousAgentTypeEnum, PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import AutonomousAgent, AutonomousAgentMember, AutonomousAgentTag
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
    from unifiedui.schema.requests.autonomous_agents import CreateAutonomousAgentRequest, UpdateAutonomousAgentRequest
    from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
    from unifiedui.services.agent_service_client import AgentServiceClient

from datetime import UTC

from unifiedui.exc.autonomous_agents import (
    AutonomousAgentApiKeysNotAllowedError,
    AutonomousAgentConfigValidationError,
    AutonomousAgentKeyNotFoundError,
    AutonomousAgentNotFoundError,
    AutonomousAgentPermissionNotFoundError,
)
from unifiedui.handlers.validators.autonomous_agent_config import AutonomousAgentConfigValidatorFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.autonomous_agents import (
    AutonomousAgentKeyResponse,
    AutonomousAgentResponse,
    WorkflowRunDetailResponse,
    WorkflowRunRetryResponse,
    WorkflowRunsListResponse,
)
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.tags import TagSummary

logger = get_logger(__name__)


class AutonomousAgentHandler:
    """Handler class for autonomous agent business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        vault_client: BaseVaultClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
        agent_service_client: AgentServiceClient | None = None,
    ):
        """
        Initialize the autonomous agent handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
            vault_client: Optional vault client for secret management
            permissions_handler: Optional central permissions handler
            tags_handler: Optional central tags handler
            agent_service_client: Optional agent service client for cascade delete
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self.vault_client = vault_client
        self._permissions_handler = permissions_handler
        self._tags_handler = tags_handler
        self._agent_service_client = agent_service_client
        self._cache = ResourceCacheInvalidator(cache_client, "autonomous_agents", "agent")

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

    def list_autonomous_agents(
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
    ) -> list[AutonomousAgentResponse] | list[QuickListItemResponse]:
        """
        Get a list of autonomous agents for a tenant (filtered by permissions).

        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by autonomous agent name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (agents must have AT LEAST ONE of the tags - OR logic)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching

        Returns:
            List of autonomous agent responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing autonomous agents", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        # Check if user is admin (has TENANT_GLOBAL_ADMIN or AUTONOMOUS_AGENTS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            is_admin = any(
                p in user_roles
                for p in [TenantRolesEnum.TENANT_GLOBAL_ADMIN.value, TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN.value]
            )

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
        cache_key = f"autonomous_agents:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"

        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None

        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached autonomous agents for tenant %s, user %s", tenant_id, user_id)
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [AutonomousAgentResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached autonomous agents: %s", e)

        with self.db_client.get_session() as session:
            # If user is admin, return all autonomous agents
            if is_admin:
                query = (
                    select(AutonomousAgent)
                    .options(selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag))
                    .where(AutonomousAgent.tenant_id == tenant_id)
                )
                if name_filter:
                    query = query.where(AutonomousAgent.name.ilike(f"%{name_filter}%"))
                # Filter by is_active status
                if is_active is not None:
                    query = query.where(AutonomousAgent.is_active == bool(is_active))
                # Filter by tags (agents must have ALL specified tags)
                if tag_ids:
                    for tag_id in tag_ids:
                        tag_subquery = select(AutonomousAgentTag.autonomous_agent_id).where(
                            AutonomousAgentTag.tenant_id == tenant_id, AutonomousAgentTag.tag_id == tag_id
                        )
                        query = query.where(AutonomousAgent.id.in_(tag_subquery))
                # Apply ordering if specified
                if order_by and hasattr(AutonomousAgent, order_by):
                    column = getattr(AutonomousAgent, order_by)
                    query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())
                query = query.offset(skip).limit(limit)
                autonomous_agents = session.execute(query).scalars().all()
            else:
                # Filter by permissions: user must have at least READ permission
                query = (
                    select(AutonomousAgent)
                    .options(selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag))
                    .join(AutonomousAgentMember, AutonomousAgent.id == AutonomousAgentMember.autonomous_agent_id)
                    .where(AutonomousAgent.tenant_id == tenant_id)
                )

                # Add permission filters
                permission_filters = []

                # User permission
                permission_filters.append(AutonomousAgentMember.principal_id == user_id)

                # Identity group permissions
                if identity_group_ids:
                    permission_filters.append(AutonomousAgentMember.principal_id.in_(identity_group_ids))

                # Custom group permissions
                if custom_group_ids:
                    permission_filters.append(AutonomousAgentMember.principal_id.in_(custom_group_ids))

                query = query.where(or_(*permission_filters))

                if name_filter:
                    query = query.where(AutonomousAgent.name.ilike(f"%{name_filter}%"))

                # Filter by is_active status
                if is_active is not None:
                    query = query.where(AutonomousAgent.is_active == bool(is_active))

                # Filter by tags (agents must have AT LEAST ONE of the specified tags - OR logic)
                if tag_ids:
                    tag_subquery = (
                        select(AutonomousAgentTag.autonomous_agent_id)
                        .where(AutonomousAgentTag.tenant_id == tenant_id, AutonomousAgentTag.tag_id.in_(tag_ids))
                        .distinct()
                    )
                    query = query.where(AutonomousAgent.id.in_(tag_subquery))

                # Apply ordering if specified
                if order_by and hasattr(AutonomousAgent, order_by):
                    column = getattr(AutonomousAgent, order_by)
                    query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

                query = query.distinct().offset(skip).limit(limit)
                autonomous_agents = session.execute(query).scalars().all()

            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=agent.id, name=agent.name) for agent in autonomous_agents]

            # Convert to response models
            responses = [self._model_to_response(agent) for agent in autonomous_agents]

            if is_admin:
                for r in responses:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in responses]
                if resource_ids:
                    principal_ids = [user_id]
                    if identity_group_ids:
                        principal_ids.extend(identity_group_ids)
                    if custom_group_ids:
                        principal_ids.extend(custom_group_ids)
                    permissions = resolve_my_permissions_bulk(
                        session, AutonomousAgentMember, "autonomous_agent_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in responses:
                        r.my_permission = permissions.get(r.id)

            # Cache the results (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    cache_data = [r.model_dump() for r in responses]
                    self.cache_client.client.set(cache_key, cache_data, ttl=300)
                    logger.debug("Cached autonomous agents list for tenant %s, user %s", tenant_id, user_id)
                except Exception as e:
                    logger.warning("Failed to cache autonomous agents: %s", e)

            return responses

    def get_autonomous_agent(
        self, tenant_id: str, autonomous_agent_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> AutonomousAgentResponse:
        """
        Get a specific autonomous agent by ID.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            user: Optional user context for permission resolution
            use_cache: Whether to use caching

        Returns:
            Autonomous agent response

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info(
            "Fetching autonomous agent", extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id}
        )

        # Build cache key
        cache_key = f"autonomous_agents:detail:tenant:{tenant_id}:agent:{autonomous_agent_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached autonomous agent %s", autonomous_agent_id)
                    result = AutonomousAgentResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(
                                session, tenant_id, autonomous_agent_id, user
                            )
                    return result
            except Exception as e:
                logger.warning("Failed to get cached autonomous agent: %s", e)

        with self.db_client.get_session() as session:
            query = (
                select(AutonomousAgent)
                .options(selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag))
                .where(AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id)
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()

            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            result = self._model_to_response(autonomous_agent)

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached autonomous agent %s", autonomous_agent_id)
                except Exception as e:
                    logger.warning("Failed to cache autonomous agent: %s", e)

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, autonomous_agent_id, user)

            return result

    def get_autonomous_agent_model(self, tenant_id: str, autonomous_agent_id: str) -> AutonomousAgent:
        """
        Get the raw autonomous agent DB model by ID.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent

        Returns:
            AutonomousAgent SQLAlchemy model (detached from session)

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        with self.db_client.get_session() as session:
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()

            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            session.expunge(autonomous_agent)
            return autonomous_agent

    def create_autonomous_agent(
        self, tenant_id: str, request: CreateAutonomousAgentRequest, user_id: str, user: ContextIdentityUser
    ) -> AutonomousAgentResponse:
        """
        Create a new autonomous agent.

        Args:
            tenant_id: The ID of the tenant
            request: Autonomous agent creation data
            user_id: ID of the user creating the autonomous agent
            user: The authenticated user context (for IDP access)

        Returns:
            Created autonomous agent response

        Raises:
            AutonomousAgentConfigValidationError: If config validation fails
            UnsupportedAutonomousAgentTypeError: If agent type is not supported
        """
        logger.info(
            "Creating autonomous agent",
            extra={
                "tenant_id": tenant_id,
                "agent_name": request.name,
                "agent_type": request.type.value,
                "user_id": user_id,
            },
        )

        # Validate config based on agent type
        validated_config = AutonomousAgentConfigValidatorFactory.validate_config(
            agent_type=request.type, config=request.config
        )

        autonomous_agent_id = str(uuid.uuid4())

        # Generate API keys and store them in vault
        primary_key = self._generate_api_key()
        secondary_key = self._generate_api_key()

        primary_key_vault_uri = None
        secondary_key_vault_uri = None

        if self.vault_client:
            try:
                primary_key_vault_uri = self.vault_client.store_secret(
                    key=f"{tenant_id}/autonomous-agents/{autonomous_agent_id}/primary-key",
                    value=primary_key,
                    metadata={
                        "tenant_id": tenant_id,
                        "autonomous_agent_id": autonomous_agent_id,
                        "key_type": "primary",
                    },
                )
                secondary_key_vault_uri = self.vault_client.store_secret(
                    key=f"{tenant_id}/autonomous-agents/{autonomous_agent_id}/secondary-key",
                    value=secondary_key,
                    metadata={
                        "tenant_id": tenant_id,
                        "autonomous_agent_id": autonomous_agent_id,
                        "key_type": "secondary",
                    },
                )
                logger.info("Stored API keys in vault for autonomous agent %s", autonomous_agent_id)
            except Exception as e:
                logger.error("Failed to store API keys in vault: %s", e)
                raise
        else:
            logger.warning("No vault client configured - API keys will not be stored")

        with self.db_client.get_session() as session:
            # Create autonomous agent
            autonomous_agent = AutonomousAgent(
                id=autonomous_agent_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value,
                config=validated_config,
                is_active=request.is_active,
                allow_api_keys=request.allow_api_keys,
                primary_key_vault_uri=primary_key_vault_uri,
                secondary_key_vault_uri=secondary_key_vault_uri,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(autonomous_agent)

            # Add creator as ADMIN using the central permissions handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="autonomous_agent",
                tenant_id=tenant_id,
                resource_id=autonomous_agent_id,
                user_id=user_id,
                user=user,
            )

            session.commit()
            session.refresh(autonomous_agent)

            response = self._model_to_response(autonomous_agent)

        # Invalidate list cache
        self._invalidate_list_cache(tenant_id)

        logger.info("Created autonomous agent %s", autonomous_agent_id)
        return response

    def update_autonomous_agent(
        self, tenant_id: str, autonomous_agent_id: str, request: UpdateAutonomousAgentRequest, user_id: str
    ) -> AutonomousAgentResponse:
        """
        Update an existing autonomous agent.

        Note: type, primary_key_vault_uri, secondary_key_vault_uri, last_full_import
        are NOT updatable via this method.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            request: Autonomous agent update data
            user_id: ID of the user updating the autonomous agent

        Returns:
            Updated autonomous agent response

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            AutonomousAgentConfigValidationError: If config validation fails
        """
        logger.info(
            "Updating autonomous agent",
            extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id, "user_id": user_id},
        )

        with self.db_client.get_session() as session:
            query = (
                select(AutonomousAgent)
                .options(selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag))
                .where(AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id)
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()

            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            # Update fields if provided
            if request.name is not None:
                autonomous_agent.name = request.name
            if request.description is not None:
                autonomous_agent.description = request.description
            if request.config is not None:
                # Validate config based on the existing agent type
                validated_config = AutonomousAgentConfigValidatorFactory.validate_config(
                    agent_type=AutonomousAgentTypeEnum(autonomous_agent.type), config=request.config
                )
                autonomous_agent.config = validated_config
            if request.is_active is not None:
                autonomous_agent.is_active = request.is_active
            if request.allow_api_keys is not None:
                autonomous_agent.allow_api_keys = request.allow_api_keys

            autonomous_agent.updated_by = user_id

            session.commit()

            # Re-fetch with tags to ensure they are loaded
            query = (
                select(AutonomousAgent)
                .options(selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag))
                .where(AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id)
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            assert autonomous_agent is not None

            response = self._model_to_response(autonomous_agent)

            # Invalidate caches
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, autonomous_agent_id)

            logger.info("Updated autonomous agent %s", autonomous_agent_id)
            return response

    def delete_autonomous_agent(self, tenant_id: str, autonomous_agent_id: str) -> None:
        """
        Delete an autonomous agent and cascade delete associated data.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info(
            "Deleting autonomous agent", extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id}
        )

        with self.db_client.get_session() as session:
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()

            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            self._cascade_delete_agent_data(tenant_id, autonomous_agent_id, autonomous_agent)

            session.delete(autonomous_agent)
            session.commit()

            # Invalidate caches
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, autonomous_agent_id)
            self._invalidate_permissions_cache(tenant_id, autonomous_agent_id)

            logger.info("Deleted autonomous agent %s", autonomous_agent_id)

    def _cascade_delete_agent_data(
        self, tenant_id: str, autonomous_agent_id: str, autonomous_agent: AutonomousAgent
    ) -> None:
        """
        Cascade delete agent service data and vault secrets (best-effort).

        Args:
            tenant_id: Tenant ID
            autonomous_agent_id: Agent ID
            autonomous_agent: Agent model instance
        """
        if self._agent_service_client:
            self._agent_service_client.delete_autonomous_agent_data(tenant_id, autonomous_agent_id)

        if self.vault_client:
            for vault_uri_attr in ("primary_key_vault_uri", "secondary_key_vault_uri"):
                vault_uri = getattr(autonomous_agent, vault_uri_attr, None)
                if vault_uri:
                    try:
                        self.vault_client.delete_secret(vault_uri)
                    except Exception:
                        logger.warning(
                            f"Failed to delete vault secret {vault_uri_attr}",
                            extra={"autonomous_agent_id": autonomous_agent_id},
                        )

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate all list caches for a tenant."""
        self._cache.invalidate_list(tenant_id)

    def _invalidate_detail_cache(self, tenant_id: str, autonomous_agent_id: str) -> None:
        """Invalidate detail cache for a specific autonomous agent."""
        self._cache.invalidate_detail(tenant_id, autonomous_agent_id)

    def _invalidate_permissions_cache(self, tenant_id: str, autonomous_agent_id: str) -> None:
        """Invalidate permissions cache for a specific autonomous agent."""
        self._cache.invalidate_permissions(tenant_id, autonomous_agent_id)

    @staticmethod
    def _generate_api_key() -> str:
        """Generate a secure random API key."""
        return secrets.token_urlsafe(32)

    # ========== Config Endpoint Method ==========

    def get_autonomous_agent_config(
        self, tenant_id: str, autonomous_agent_id: str, autonomous_agent: AutonomousAgent, credential_handler
    ):
        """
        Get the full autonomous agent configuration including credential secrets.
        This endpoint is for external systems (like N8N) to fetch complete configuration.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            autonomous_agent: The autonomous agent model (already fetched by middleware)
            credential_handler: Credential handler for fetching secrets

        Returns:
            AutonomousAgentConfigResponse with full config including secrets

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            InvalidCredentialError: If a credential cannot be fetched
        """
        from unifiedui.exc.chat_agent_config import InvalidCredentialError
        from unifiedui.schema.responses.autonomous_agents import (
            AutonomousAgentConfigResponse,
            CredentialSecretResponse,
            N8NAutonomousAgentConfigSettingsResponse,
        )

        logger.info(
            "Fetching autonomous agent config",
            extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id},
        )

        agent_type = AutonomousAgentTypeEnum(autonomous_agent.type)
        config = autonomous_agent.config or {}

        # Build settings based on agent type
        if agent_type == AutonomousAgentTypeEnum.N8N:
            # Extract config values
            api_version = config.get("api_version", "v1")
            workflow_endpoint = config.get("workflow_endpoint", "")
            api_credential_id = config.get("api_api_key_credential_id")

            if not api_credential_id:
                raise InvalidCredentialError(
                    credential_id="unknown",
                    message="Autonomous agent config is missing required api_api_key_credential_id",
                )

            # Parse workflow URL to extract host and workflow ID
            n8n_host = ""
            workflow_id = ""
            if workflow_endpoint:
                # Parse URL: http://host:port/workflow/workflowId
                from urllib.parse import urlparse

                parsed = urlparse(workflow_endpoint)
                n8n_host = f"{parsed.scheme}://{parsed.netloc}"

                # Extract workflow ID from path
                path_parts = parsed.path.split("/workflow/")
                if len(path_parts) > 1:
                    workflow_id = path_parts[1].strip("/")

            # Fetch API credential with secret
            try:
                api_credential = credential_handler.get_credential(tenant_id, api_credential_id)
                api_secret = credential_handler.get_credential_secret(tenant_id, api_credential_id)
            except Exception as e:
                logger.error("Failed to fetch API credential: %s", e)
                raise InvalidCredentialError(
                    credential_id=api_credential_id,
                    message=f"Invalid or inaccessible API credential with ID '{api_credential_id}'",
                )

            if api_secret is None:
                logger.error(
                    f"Credential secret is None for credential '{api_credential_id}' — vault may be unavailable"
                )
                raise InvalidCredentialError(
                    credential_id=api_credential_id,
                    message=f"Could not retrieve secret for credential '{api_credential_id}'. Ensure the vault is running and the secret exists.",
                )

            api_credentials = CredentialSecretResponse(
                id=api_credential.id,
                credentials_uri=api_credential.credential_uri,
                name=api_credential.name,
                description=api_credential.description,
                type=api_credential.type,
                is_active=api_credential.is_active,
                secret=api_secret,
            )

            settings = N8NAutonomousAgentConfigSettingsResponse(
                api_version=api_version,
                n8n_host=n8n_host,
                n8n_workflow_endpoint=workflow_endpoint,
                workflow_id=workflow_id,
                api_credentials=api_credentials,
            )
        else:
            # For unsupported types, return raw config
            settings = config

        return AutonomousAgentConfigResponse(
            docversion="v1",
            type=agent_type,
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            settings=settings,
        )

    # ========== Workflow Runs Methods ==========

    def _get_n8n_connection_config(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        credential_handler,
    ) -> tuple[str, str, str, str]:
        """Extract n8n connection details from autonomous agent config.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            credential_handler: Credential handler for fetching API key secrets

        Returns:
            Tuple of (n8n_host, workflow_id, api_version, api_secret)

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            UnsupportedAutonomousAgentTypeError: If agent type doesn't support workflow runs
            AutonomousAgentConfigValidationError: If required config is missing
        """
        from urllib.parse import urlparse

        from unifiedui.exc.autonomous_agents import UnsupportedAutonomousAgentTypeError

        with self.db_client.get_session() as session:
            agent = session.execute(
                select(AutonomousAgent).where(
                    AutonomousAgent.id == autonomous_agent_id,
                    AutonomousAgent.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            agent_type = AutonomousAgentTypeEnum(agent.type)
            if agent_type != AutonomousAgentTypeEnum.N8N:
                raise UnsupportedAutonomousAgentTypeError(agent.type)

            config = agent.config or {}
            workflow_endpoint = config.get("workflow_endpoint", "")
            api_version = config.get("api_version", "v1")
            api_credential_id = config.get("api_api_key_credential_id")

            if not workflow_endpoint or not api_credential_id:
                raise AutonomousAgentConfigValidationError(
                    message="Autonomous agent missing required config for workflow runs",
                    errors=["workflow_endpoint and api_api_key_credential_id are required"],
                )

            parsed = urlparse(workflow_endpoint)
            n8n_host = f"{parsed.scheme}://{parsed.netloc}"
            path_parts = parsed.path.split("/workflow/")
            workflow_id = path_parts[1].strip("/") if len(path_parts) > 1 else ""

            if not workflow_id:
                raise AutonomousAgentConfigValidationError(
                    message="Could not extract workflow ID from workflow_endpoint",
                    errors=["workflow_endpoint must contain /workflow/{id}"],
                )

            api_secret = credential_handler.get_credential_secret(tenant_id, api_credential_id)
            if not api_secret:
                raise AutonomousAgentConfigValidationError(
                    message="Failed to retrieve API key for workflow runs",
                    errors=["Ensure the vault is running and the credential secret exists"],
                )

            return n8n_host, workflow_id, api_version, api_secret

    def get_workflow_runs(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        credential_handler,
        limit: int = 20,
        cursor: str | None = None,
        status: str | None = None,
    ) -> WorkflowRunsListResponse:
        """Fetch workflow execution runs from the external workflow platform.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            credential_handler: Credential handler for fetching API key secrets
            limit: Maximum number of runs to return
            cursor: Pagination cursor for next page
            status: Filter by execution status

        Returns:
            WorkflowRunsListResponse with list of workflow runs

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            UnsupportedAutonomousAgentTypeError: If agent type doesn't support workflow runs
            AutonomousAgentConfigValidationError: If config is missing or vault unavailable
        """
        import httpx

        from unifiedui.schema.responses.autonomous_agents import WorkflowRunResponse, WorkflowRunsListResponse

        n8n_host, workflow_id, api_version, api_secret = self._get_n8n_connection_config(
            tenant_id, autonomous_agent_id, credential_handler
        )

        url = f"{n8n_host}/api/{api_version}/executions"
        params: dict[str, str | int] = {
            "workflowId": workflow_id,
            "limit": min(limit, 100),
        }
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status

        headers = {"X-N8N-API-KEY": api_secret}

        try:
            with httpx.Client(timeout=15) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch workflow runs from N8N: %s", e)
            return WorkflowRunsListResponse(runs=[], next_cursor=None)

        raw_runs = data.get("data", [])
        runs = []
        for run in raw_runs:
            runs.append(
                WorkflowRunResponse(
                    id=str(run.get("id", "")),
                    finished=run.get("finished", False),
                    mode=run.get("mode", "unknown"),
                    startedAt=run.get("startedAt"),
                    stoppedAt=run.get("stoppedAt"),
                    status=run.get("status", "unknown"),
                    workflowName=run.get("workflowName"),
                    retryOf=run.get("retryOf"),
                    retrySuccessId=run.get("retrySuccessId"),
                )
            )

        return WorkflowRunsListResponse(
            runs=runs,
            next_cursor=data.get("nextCursor"),
        )

    def get_workflow_run_detail(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        execution_id: str,
        credential_handler,
    ) -> WorkflowRunDetailResponse:
        """Fetch a single workflow execution with full data from the external platform.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            execution_id: The execution ID to fetch
            credential_handler: Credential handler for fetching API key secrets

        Returns:
            WorkflowRunDetailResponse with full execution data

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            UnsupportedAutonomousAgentTypeError: If agent type doesn't support workflow runs
            AutonomousAgentConfigValidationError: If config is missing or execution not found
        """
        import httpx

        from unifiedui.schema.responses.autonomous_agents import WorkflowRunDetailResponse

        n8n_host, _workflow_id, api_version, api_secret = self._get_n8n_connection_config(
            tenant_id, autonomous_agent_id, credential_handler
        )

        url = f"{n8n_host}/api/{api_version}/executions/{execution_id}"
        headers = {"X-N8N-API-KEY": api_secret}

        try:
            with httpx.Client(timeout=15) as client:
                response = client.get(url, params={"includeData": "true"}, headers=headers)
                response.raise_for_status()
                run = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise AutonomousAgentConfigValidationError(
                    message=f"Execution {execution_id} not found",
                    errors=[str(e)],
                )
            raise
        except httpx.HTTPError as e:
            logger.error("Failed to fetch workflow run detail from N8N: %s", e)
            raise AutonomousAgentConfigValidationError(
                message=f"Failed to fetch execution {execution_id}",
                errors=[str(e)],
            )

        return WorkflowRunDetailResponse(
            id=str(run.get("id", "")),
            finished=run.get("finished", False),
            mode=run.get("mode", "unknown"),
            startedAt=run.get("startedAt"),
            stoppedAt=run.get("stoppedAt"),
            status=run.get("status", "unknown"),
            workflowName=run.get("workflowName"),
            retryOf=run.get("retryOf"),
            retrySuccessId=run.get("retrySuccessId"),
            data=run.get("data"),
            workflowData=run.get("workflowData"),
        )

    def retry_workflow_run(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        execution_id: str,
        credential_handler,
    ) -> WorkflowRunRetryResponse:
        """Retry a failed workflow execution.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            execution_id: The execution ID to retry
            credential_handler: Credential handler for fetching API key secrets

        Returns:
            WorkflowRunRetryResponse with retry result

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            UnsupportedAutonomousAgentTypeError: If agent type doesn't support workflow runs
            AutonomousAgentConfigValidationError: If retry fails
        """
        import httpx

        from unifiedui.schema.responses.autonomous_agents import WorkflowRunRetryResponse

        n8n_host, _workflow_id, api_version, api_secret = self._get_n8n_connection_config(
            tenant_id, autonomous_agent_id, credential_handler
        )

        url = f"{n8n_host}/api/{api_version}/executions/{execution_id}/retry"
        headers = {"X-N8N-API-KEY": api_secret}

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to retry workflow execution: %s", e)
            raise AutonomousAgentConfigValidationError(
                message=f"Failed to retry execution {execution_id}",
                errors=[str(e)],
            )

        if "message" in data:
            return WorkflowRunRetryResponse(message=data["message"])

        retry_data = data.get("data", data)
        return WorkflowRunRetryResponse(
            id=str(retry_data.get("id", "")),
            retried=retry_data.get("retried", True),
        )

    def start_workflow(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        body: dict | None = None,
        files: list[dict] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> dict:
        """
        Trigger a workflow via its configured webhook URL.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            body: Optional JSON body to send with the webhook request
            files: Optional list of file dicts with name, mimeType, and base64 data
            query_params: Optional query parameters to append to the webhook URL

        Returns:
            Response from the webhook endpoint

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            UnsupportedAutonomousAgentTypeError: If agent type doesn't support workflows
            AutonomousAgentConfigValidationError: If webhook_url is not configured
        """
        import httpx

        from unifiedui.exc.autonomous_agents import UnsupportedAutonomousAgentTypeError

        with self.db_client.get_session() as session:
            agent = session.execute(
                select(AutonomousAgent).where(
                    AutonomousAgent.id == autonomous_agent_id,
                    AutonomousAgent.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            agent_type = AutonomousAgentTypeEnum(agent.type)
            if agent_type != AutonomousAgentTypeEnum.N8N:
                raise UnsupportedAutonomousAgentTypeError(agent.type)

            config = agent.config or {}
            webhook_url = config.get("webhook_url")

            if not webhook_url:
                from unifiedui.exc.autonomous_agents import AutonomousAgentConfigValidationError

                raise AutonomousAgentConfigValidationError(
                    message="No webhook_url configured for this autonomous agent",
                    errors=["webhook_url is required to start a workflow"],
                )

            payload = body or {}
            if files:
                payload["files"] = files

            target_url = webhook_url
            if query_params:
                from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

                parsed = urlparse(webhook_url)
                existing_params = parse_qs(parsed.query)
                existing_params.update({k: [v] for k, v in query_params.items()})
                new_query = urlencode({k: v[0] for k, v in existing_params.items()})
                target_url = urlunparse(parsed._replace(query=new_query))

            try:
                with httpx.Client(timeout=30) as client:
                    response = client.post(
                        target_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    try:
                        return response.json()
                    except Exception:
                        return {"status": "ok", "statusCode": response.status_code}
            except httpx.HTTPError as e:
                logger.error("Failed to trigger workflow webhook: %s", e)
                from unifiedui.exc.autonomous_agents import AutonomousAgentConfigValidationError

                raise AutonomousAgentConfigValidationError(
                    message=f"Failed to trigger workflow: {e!s}",
                    errors=[str(e)],
                )

    # ========== API Key Management Methods ==========

    def get_api_key(self, tenant_id: str, autonomous_agent_id: str, key_number: int) -> AutonomousAgentKeyResponse:
        """
        Get an API key for an autonomous agent.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            key_number: Key number (1 for primary, 2 for secondary)

        Returns:
            The API key response

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            AutonomousAgentKeyNotFoundError: If key not found or vault not configured
        """
        logger.info(
            "Getting API key",
            extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id, "key_number": key_number},
        )

        if key_number not in [1, 2]:
            raise AutonomousAgentKeyNotFoundError(autonomous_agent_id, key_number)

        if not self.vault_client:
            raise AutonomousAgentKeyNotFoundError(autonomous_agent_id, key_number)

        with self.db_client.get_session() as session:
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()

            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            if not autonomous_agent.allow_api_keys:
                raise AutonomousAgentApiKeysNotAllowedError(autonomous_agent_id)

            vault_uri = (
                autonomous_agent.primary_key_vault_uri if key_number == 1 else autonomous_agent.secondary_key_vault_uri
            )

            if not vault_uri:
                raise AutonomousAgentKeyNotFoundError(autonomous_agent_id, key_number)

            key = self.vault_client.get_secret(vault_uri, use_cache=False)

            if not key:
                raise AutonomousAgentKeyNotFoundError(autonomous_agent_id, key_number)

            return AutonomousAgentKeyResponse(key=key, key_number=key_number)

    def rotate_api_key(
        self, tenant_id: str, autonomous_agent_id: str, key_number: int, user_id: str
    ) -> AutonomousAgentKeyResponse:
        """
        Rotate an API key for an autonomous agent.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            key_number: Key number (1 for primary, 2 for secondary)
            user_id: ID of the user rotating the key

        Returns:
            The new API key response

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
            AutonomousAgentKeyNotFoundError: If vault not configured
        """
        logger.info(
            "Rotating API key",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "key_number": key_number,
                "user_id": user_id,
            },
        )

        if key_number not in [1, 2]:
            raise AutonomousAgentKeyNotFoundError(autonomous_agent_id, key_number)

        if not self.vault_client:
            raise AutonomousAgentKeyNotFoundError(autonomous_agent_id, key_number)

        with self.db_client.get_session() as session:
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()

            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            if not autonomous_agent.allow_api_keys:
                raise AutonomousAgentApiKeysNotAllowedError(autonomous_agent_id)

            # Generate new key
            new_key = self._generate_api_key()

            # Determine which vault URI to use
            vault_uri = (
                autonomous_agent.primary_key_vault_uri if key_number == 1 else autonomous_agent.secondary_key_vault_uri
            )

            if vault_uri:
                # Update existing secret
                success = self.vault_client.update_secret(vault_uri, new_key)
                if not success:
                    logger.error(
                        f"Failed to update key {key_number} in vault for autonomous agent {autonomous_agent_id}"
                    )
                    raise RuntimeError(f"Failed to rotate key {key_number}")
            else:
                # Create new secret (shouldn't happen normally, but handle gracefully)
                key_type = "primary" if key_number == 1 else "secondary"
                vault_uri = self.vault_client.store_secret(
                    key=f"{tenant_id}/autonomous-agents/{autonomous_agent_id}/{key_type}-key",
                    value=new_key,
                    metadata={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id, "key_type": key_type},
                )

                # Update the model with the new vault URI
                if key_number == 1:
                    autonomous_agent.primary_key_vault_uri = vault_uri
                else:
                    autonomous_agent.secondary_key_vault_uri = vault_uri

            autonomous_agent.updated_by = user_id
            session.commit()

            # Invalidate caches
            self._invalidate_detail_cache(tenant_id, autonomous_agent_id)

            logger.info("Rotated key %s for autonomous agent %s", key_number, autonomous_agent_id)
            return AutonomousAgentKeyResponse(key=new_key, key_number=key_number)

    def update_last_full_import(
        self, tenant_id: str, autonomous_agent_id: str, user_id: str
    ) -> AutonomousAgentResponse:
        """
        Update the last_full_import timestamp for an autonomous agent.
        This is a system-only operation.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            user_id: ID of the system user performing the update

        Returns:
            Updated autonomous agent response

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        from datetime import datetime

        logger.info(
            "Updating last_full_import", extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id}
        )

        with self.db_client.get_session() as session:
            query = (
                select(AutonomousAgent)
                .options(selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag))
                .where(AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id)
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()

            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)

            autonomous_agent.last_full_import = datetime.now(UTC)
            autonomous_agent.updated_by = user_id

            session.commit()
            session.refresh(autonomous_agent)

            response = self._model_to_response(autonomous_agent)

            # Invalidate caches
            self._invalidate_detail_cache(tenant_id, autonomous_agent_id)

            return response

    # ========== Permission Management Methods ==========

    def list_autonomous_agent_permissions(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
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
        Get all permissions for an autonomous agent.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            skip: Number of principals to skip
            limit: Maximum number of principals to return
            search: Search term for display_name, principal_name, or mail
            roles: Filter by roles (OR logic)
            is_active: Filter by is_active status
            order_by: Column to order by
            order_direction: Sort direction
            use_cache: Whether to use caching

        Returns:
            List of principals with their permissions

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info(
            "Listing autonomous agent permissions",
            extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id},
        )

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="autonomous_agent",
                tenant_id=tenant_id,
                resource_id=autonomous_agent_id,
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
            raise AutonomousAgentNotFoundError(autonomous_agent_id) from e

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
            resource_id=autonomous_agent_id,
            resource_type="autonomous_agent",
            tenant_id=tenant_id,
            principals=principals,
        )

    def get_autonomous_agent_permission(
        self, tenant_id: str, autonomous_agent_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """
        Get permissions for a specific principal on an autonomous agent.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            principal_id: The ID of the principal

        Returns:
            Principal's permissions

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info(
            "Getting autonomous agent permission for principal",
            extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id, "principal_id": principal_id},
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="autonomous_agent",
                tenant_id=tenant_id,
                resource_id=autonomous_agent_id,
                principal_id=principal_id,
            )
        except ValueError as e:
            # If permission not found, return empty response
            if "No permissions found" in str(e):
                return PrincipalWithRolesResponse(principal_id=principal_id, principal_type="", roles=[])
            raise AutonomousAgentNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_autonomous_agent_permission(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        request: SetResourcePermissionRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """
        Set or update a permission for a principal on an autonomous agent.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            request: Permission setting data
            user_id: ID of the user setting the permission

        Returns:
            Created or updated permission response

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info(
            "Setting autonomous agent permission",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "principal_id": request.principal_id,
                "agent_role": request.role,
                "user_id": user_id,
            },
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="autonomous_agent",
                tenant_id=tenant_id,
                resource_id=autonomous_agent_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )
        except ValueError as e:
            raise AutonomousAgentNotFoundError(str(e)) from e

        # Fetch and return the enriched principal data
        return self.get_autonomous_agent_permission(
            tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id, principal_id=request.principal_id
        )

    def delete_autonomous_agent_permission(
        self, tenant_id: str, autonomous_agent_id: str, principal_id: str, principal_type: str, role: str
    ) -> None:
        """
        Delete a permission for a principal on an autonomous agent.

        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            principal_id: The ID of the principal
            principal_type: The type of principal
            role: The role to delete

        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info(
            "Deleting autonomous agent permission",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "principal_id": principal_id,
                "agent_role": role,
            },
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="autonomous_agent",
                tenant_id=tenant_id,
                resource_id=autonomous_agent_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=role,
            )
        except ValueError as e:
            if "No permissions found" in str(e) or "not found" in str(e).lower():
                raise AutonomousAgentPermissionNotFoundError(principal_id) from e
            raise AutonomousAgentNotFoundError(str(e)) from e

    @staticmethod
    def _group_permissions_by_principal(results) -> list[dict]:
        """Helper to group permissions by principal."""
        principals_dict = {}
        for member, permission in results:
            key = (member.principal_id, member.principal.principal_type)
            if key not in principals_dict:
                principals_dict[key] = {
                    "principal_id": member.principal_id,
                    "principal_type": member.principal.principal_type,
                    "roles": [],
                }
            principals_dict[key]["roles"].append(permission.permission)
        return list(principals_dict.values())

    @staticmethod
    def _model_to_response(agent: AutonomousAgent) -> AutonomousAgentResponse:
        """Convert AutonomousAgent model to AutonomousAgentResponse."""
        # Extract tags from the agent's tags relationship
        tags = []
        if hasattr(agent, "tags") and agent.tags:
            for agent_tag in agent.tags:
                if agent_tag.tag:
                    tags.append(TagSummary(id=agent_tag.tag.id, name=agent_tag.tag.name))

        return AutonomousAgentResponse(
            id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            description=agent.description,
            type=AutonomousAgentTypeEnum(agent.type),
            is_active=agent.is_active,
            allow_api_keys=agent.allow_api_keys,
            config=agent.config,
            last_full_import=agent.last_full_import,
            tags=tags,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            created_by=agent.created_by,
            updated_by=agent.updated_by,
        )

    def _resolve_user_permission(
        self, session: Session, tenant_id: str, autonomous_agent_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific autonomous agent."""
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(
            user, tenant_id, [TenantRolesEnum.TENANT_GLOBAL_ADMIN, TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN]
        ):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(
            session, AutonomousAgentMember, "autonomous_agent_id", tenant_id, autonomous_agent_id, principal_ids
        )

    @staticmethod
    def _validate_principal_type(principal_type: str) -> bool:
        """Validate that principal_type is valid."""
        return principal_type in [
            PrincipalTypeEnum.IDENTITY_USER.value,
            PrincipalTypeEnum.IDENTITY_GROUP.value,
            PrincipalTypeEnum.CUSTOM_GROUP.value,
        ]
