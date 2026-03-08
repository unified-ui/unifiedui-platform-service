"""Business logic handlers for ReACT agent operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import ChatAgentTypeEnum, PermissionActionEnum
from unifiedui.core.database.models import (
    ChatAgent,
    ReActAgent,
    ReActAgentMember,
    ReActAgentTag,
    ReActAgentVersion,
)
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
    from unifiedui.schema.requests.re_act_agent_permissions import SetReActAgentPermissionRequest
    from unifiedui.schema.requests.re_act_agents import (
        CreateReActAgentRequest,
        PublishReActAgentRequest,
        UpdateReActAgentRequest,
        UpdateReActAgentVersionRequest,
    )

from unifiedui.exc.re_act_agents import (
    ReActAgentNotFoundError,
    ReActAgentVersionNotFoundError,
)
from unifiedui.logger import get_logger
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.re_act_agents import (
    PublishReActAgentResponse,
    ReActAgentResponse,
    ReActAgentVersionResponse,
)
from unifiedui.schema.responses.tags import TagSummary

logger = get_logger(__name__)


class ReActAgentHandler:
    """Handler class for ReACT agent business logic with versioned config."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
    ):
        """Initialize ReActAgentHandler.

        Args:
            db_client: SQLAlchemy database client
            cache_client: Optional cache client
            permissions_handler: Optional resource permissions handler
            tags_handler: Optional resource tags handler
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self._permissions_handler = permissions_handler
        self._tags_handler = tags_handler

    @property
    def permissions_handler(self) -> ResourcePermissionsHandler:
        """Lazily initialize permissions handler."""
        if self._permissions_handler is None:
            from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler

            self._permissions_handler = ResourcePermissionsHandler(self.db_client, self.cache_client)
        return self._permissions_handler

    @property
    def tags_handler(self) -> ResourceTagsHandler:
        """Lazily initialize tags handler."""
        if self._tags_handler is None:
            from unifiedui.handlers.resource_tags import ResourceTagsHandler

            self._tags_handler = ResourceTagsHandler(self.db_client, self.cache_client)
        return self._tags_handler

    def list_re_act_agents(
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
    ) -> list[ReActAgentResponse] | list[QuickListItemResponse]:
        """List ReACT agents for a tenant filtered by user permissions.

        Args:
            tenant_id: Tenant ID for scoping
            user: Authenticated user context
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional name filter
            is_active: Optional active status filter
            tag_ids: Optional tag ID filter
            order_by: Column to order by
            order_direction: Sort direction
            view: View type (full or quick-list)
            use_cache: Whether to use cache

        Returns:
            List of ReACT agent responses or quick list items
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing ReACT agents", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            admin_permissions = [TenantRolesEnum.TENANT_GLOBAL_ADMIN.value, TenantRolesEnum.REACT_AGENT_ADMIN.value]
            is_admin = any(perm in user_roles for perm in admin_permissions)

        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]

        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"re_act_agents:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"

        has_filters = name_filter is not None or tag_ids is not None

        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached ReACT agent list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [ReActAgentResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached ReACT agent list: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(ReActAgent)
                .options(
                    selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag),
                    selectinload(ReActAgent.versions),
                )
                .where(ReActAgent.tenant_id == tenant_id)
            )

            if not is_admin:
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)

                member_subquery = (
                    select(ReActAgentMember.re_act_agent_id)
                    .where(ReActAgentMember.tenant_id == tenant_id, ReActAgentMember.principal_id.in_(principal_ids))
                    .distinct()
                )

                query = query.where(ReActAgent.id.in_(member_subquery))

            if name_filter:
                query = query.where(ReActAgent.name.ilike(f"%{name_filter}%"))

            if is_active is not None:
                query = query.where(ReActAgent.is_active == bool(is_active))

            if tag_ids:
                tag_subquery = (
                    select(ReActAgentTag.re_act_agent_id)
                    .where(ReActAgentTag.tenant_id == tenant_id, ReActAgentTag.tag_id.in_(tag_ids))
                    .distinct()
                )
                query = query.where(ReActAgent.id.in_(tag_subquery))

            if order_by and hasattr(ReActAgent, order_by):
                column = getattr(ReActAgent, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            agents = session.execute(query).scalars().all()

            logger.info("Retrieved ReACT agents", extra={"count": len(agents)})

            if view == "quick-list":
                return [QuickListItemResponse(id=agent.id, name=agent.name) for agent in agents]

            result = [self._model_to_response(agent) for agent in agents]

            if is_admin:
                for r in result:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in result]
                if resource_ids:
                    permissions = resolve_my_permissions_bulk(
                        session, ReActAgentMember, "re_act_agent_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in result:
                        r.my_permission = permissions.get(r.id)

            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached ReACT agent list")
                except Exception as e:
                    logger.warning(f"Failed to cache ReACT agent list: {e}")

            return result

    def get_re_act_agent(
        self, tenant_id: str, re_act_agent_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> ReActAgentResponse:
        """Get a specific ReACT agent by ID with its latest version config.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            user: Optional authenticated user context for permission resolution
            use_cache: Whether to use cache

        Returns:
            ReACT agent response
        """
        logger.info("Fetching ReACT agent", extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id})

        cache_key = f"re_act_agents:detail:tenant:{tenant_id}:agent:{re_act_agent_id}"

        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached ReACT agent")
                    result = ReActAgentResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(
                                session, tenant_id, re_act_agent_id, user
                            )
                    return result
            except Exception as e:
                logger.warning(f"Failed to get cached ReACT agent: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(ReActAgent)
                .options(
                    selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag),
                    selectinload(ReActAgent.versions),
                )
                .where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            )
            agent = session.execute(query).scalar_one_or_none()

            if not agent:
                raise ReActAgentNotFoundError(re_act_agent_id)

            result = self._model_to_response(agent)

            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached ReACT agent detail")
                except Exception as e:
                    logger.warning(f"Failed to cache ReACT agent: {e}")

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, re_act_agent_id, user)

            return result

    def create_re_act_agent(
        self, tenant_id: str, request: CreateReActAgentRequest, user_id: str, user: ContextIdentityUser
    ) -> ReActAgentResponse:
        """Create a new ReACT agent with initial version (v1).

        Args:
            tenant_id: Tenant ID for scoping
            request: Creation request data
            user_id: ID of the creating user
            user: Authenticated user context

        Returns:
            Created ReACT agent response
        """
        logger.info("Creating ReACT agent", extra={"tenant_id": tenant_id, "agent_name": request.name})

        agent_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            agent = ReActAgent(
                id=agent_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                is_active=request.is_active,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(agent)

            version = ReActAgentVersion(
                id=version_id,
                re_act_agent_id=agent_id,
                version=1,
                ai_model_ids=request.ai_model_ids,
                system_prompt=request.system_prompt,
                tool_ids=request.tool_ids,
                security_prompt=request.security_prompt,
                tool_use_prompt=request.tool_use_prompt,
                response_prompt=request.response_prompt,
                greeting_messages=request.greeting_messages,
                config=request.config or {},
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(version)

            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=agent_id,
                user_id=user_id,
                user=user,
            )

            session.commit()

            query = (
                select(ReActAgent)
                .options(
                    selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag),
                    selectinload(ReActAgent.versions),
                )
                .where(ReActAgent.id == agent_id)
            )
            agent = session.execute(query).scalar_one()

            logger.info("ReACT agent created", extra={"agent_id": agent_id})

            self._invalidate_list_cache(tenant_id)

            return self._model_to_response(agent)

    def update_re_act_agent(
        self, tenant_id: str, re_act_agent_id: str, request: UpdateReActAgentRequest, user_id: str
    ) -> ReActAgentResponse:
        """Update metadata of an existing ReACT agent (name, description, is_active).

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            request: Update request data (metadata only)
            user_id: ID of the updating user

        Returns:
            Updated ReACT agent response
        """
        logger.info("Updating ReACT agent", extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id})

        with self.db_client.get_session() as session:
            query = (
                select(ReActAgent)
                .options(
                    selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag),
                    selectinload(ReActAgent.versions),
                )
                .where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            )
            agent = session.execute(query).scalar_one_or_none()

            if not agent:
                raise ReActAgentNotFoundError(re_act_agent_id)

            if request.name is not None:
                agent.name = request.name
            if request.description is not None:
                agent.description = request.description
            if request.is_active is not None:
                agent.is_active = request.is_active

            agent.updated_by = user_id

            session.commit()

            query = (
                select(ReActAgent)
                .options(
                    selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag),
                    selectinload(ReActAgent.versions),
                )
                .where(ReActAgent.id == re_act_agent_id)
            )
            agent = session.execute(query).scalar_one()

            logger.info("ReACT agent updated", extra={"re_act_agent_id": re_act_agent_id})

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, re_act_agent_id)

            return self._model_to_response(agent)

    def update_re_act_agent_version(
        self, tenant_id: str, re_act_agent_id: str, request: UpdateReActAgentVersionRequest, user_id: str
    ) -> ReActAgentResponse:
        """Create a new version of the ReACT agent config.

        Takes the latest version, applies the partial update, and saves as a new version.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            request: Version config update data
            user_id: ID of the updating user

        Returns:
            Updated ReACT agent response (with new latest version)
        """
        logger.info(
            "Creating new ReACT agent version",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id},
        )

        with self.db_client.get_session() as session:
            agent = session.execute(
                select(ReActAgent).where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            ).scalar_one_or_none()

            if not agent:
                raise ReActAgentNotFoundError(re_act_agent_id)

            latest_version = session.execute(
                select(ReActAgentVersion)
                .where(ReActAgentVersion.re_act_agent_id == re_act_agent_id)
                .order_by(ReActAgentVersion.version.desc())
                .limit(1)
            ).scalar_one_or_none()

            next_version_num = (latest_version.version + 1) if latest_version else 1

            new_version = ReActAgentVersion(
                id=str(uuid.uuid4()),
                re_act_agent_id=re_act_agent_id,
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

            agent.updated_by = user_id
            session.commit()

            query = (
                select(ReActAgent)
                .options(
                    selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag),
                    selectinload(ReActAgent.versions),
                )
                .where(ReActAgent.id == re_act_agent_id)
            )
            agent = session.execute(query).scalar_one()

            logger.info(
                "ReACT agent version created",
                extra={"re_act_agent_id": re_act_agent_id, "version": next_version_num},
            )

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, re_act_agent_id)

            return self._model_to_response(agent)

    def list_re_act_agent_versions(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ReActAgentVersionResponse]:
        """List all versions of a ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of version responses ordered by version descending
        """
        logger.info(
            "Listing ReACT agent versions",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id},
        )

        with self.db_client.get_session() as session:
            agent_exists = session.execute(
                select(func.count())
                .select_from(ReActAgent)
                .where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            ).scalar_one()

            if not agent_exists:
                raise ReActAgentNotFoundError(re_act_agent_id)

            versions = (
                session.execute(
                    select(ReActAgentVersion)
                    .where(ReActAgentVersion.re_act_agent_id == re_act_agent_id)
                    .order_by(ReActAgentVersion.version.desc())
                    .offset(skip)
                    .limit(limit)
                )
                .scalars()
                .all()
            )

            return [self._version_to_response(v) for v in versions]

    def get_re_act_agent_version(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        version: int,
    ) -> ReActAgentVersionResponse:
        """Get a specific version of a ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            version: Version number

        Returns:
            Version response
        """
        logger.info(
            "Fetching ReACT agent version",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "version": version},
        )

        with self.db_client.get_session() as session:
            agent_exists = session.execute(
                select(func.count())
                .select_from(ReActAgent)
                .where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            ).scalar_one()

            if not agent_exists:
                raise ReActAgentNotFoundError(re_act_agent_id)

            version_record = session.execute(
                select(ReActAgentVersion).where(
                    ReActAgentVersion.re_act_agent_id == re_act_agent_id,
                    ReActAgentVersion.version == version,
                )
            ).scalar_one_or_none()

            if not version_record:
                raise ReActAgentVersionNotFoundError(re_act_agent_id, version)

            return self._version_to_response(version_record)

    def restore_re_act_agent_version(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        version: int,
        user_id: str,
    ) -> ReActAgentResponse:
        """Restore a previous version by creating a new version with the same config.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            version: Version number to restore
            user_id: ID of the restoring user

        Returns:
            Updated ReACT agent response with the restored version as latest
        """
        logger.info(
            "Restoring ReACT agent version",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "version": version},
        )

        with self.db_client.get_session() as session:
            agent = session.execute(
                select(ReActAgent).where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            ).scalar_one_or_none()

            if not agent:
                raise ReActAgentNotFoundError(re_act_agent_id)

            source_version = session.execute(
                select(ReActAgentVersion).where(
                    ReActAgentVersion.re_act_agent_id == re_act_agent_id,
                    ReActAgentVersion.version == version,
                )
            ).scalar_one_or_none()

            if not source_version:
                raise ReActAgentVersionNotFoundError(re_act_agent_id, version)

            latest_version_num = (
                session.execute(
                    select(func.max(ReActAgentVersion.version)).where(
                        ReActAgentVersion.re_act_agent_id == re_act_agent_id
                    )
                ).scalar_one()
                or 0
            )

            new_version = ReActAgentVersion(
                id=str(uuid.uuid4()),
                re_act_agent_id=re_act_agent_id,
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

            agent.updated_by = user_id
            session.commit()

            query = (
                select(ReActAgent)
                .options(
                    selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag),
                    selectinload(ReActAgent.versions),
                )
                .where(ReActAgent.id == re_act_agent_id)
            )
            agent = session.execute(query).scalar_one()

            logger.info(
                "ReACT agent version restored",
                extra={
                    "re_act_agent_id": re_act_agent_id,
                    "source_version": version,
                    "new_version": latest_version_num + 1,
                },
            )

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, re_act_agent_id)

            return self._model_to_response(agent)

    def publish_re_act_agent(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        request: PublishReActAgentRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PublishReActAgentResponse:
        """Publish a ReACT agent as a chat agent.

        Creates or updates a chat_agent entry with type REACT_AGENT. The config
        stores the react_agent_id; the latest version is resolved at query time.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            request: Publish request data
            user_id: ID of the publishing user
            user: Authenticated user context

        Returns:
            Publish response with the chat agent details
        """
        logger.info(
            "Publishing ReACT agent",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id},
        )

        with self.db_client.get_session() as session:
            agent = session.execute(
                select(ReActAgent).where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            ).scalar_one_or_none()

            if not agent:
                raise ReActAgentNotFoundError(re_act_agent_id)

            chat_agent_name = request.name or agent.name
            chat_agent_description = request.description or agent.description
            chat_agent_config = {"react_agent_id": re_act_agent_id}

            if agent.published_chat_agent_id:
                chat_agent = session.execute(
                    select(ChatAgent).where(ChatAgent.id == agent.published_chat_agent_id)
                ).scalar_one_or_none()

                if chat_agent:
                    chat_agent.name = chat_agent_name
                    chat_agent.description = chat_agent_description
                    chat_agent.config = chat_agent_config
                    chat_agent.is_active = request.is_active
                    chat_agent.updated_by = user_id
                else:
                    chat_agent = self._create_chat_agent(
                        session,
                        tenant_id,
                        chat_agent_name,
                        chat_agent_description,
                        chat_agent_config,
                        request.is_active,
                        user_id,
                    )
                    agent.published_chat_agent_id = chat_agent.id
            else:
                chat_agent = self._create_chat_agent(
                    session,
                    tenant_id,
                    chat_agent_name,
                    chat_agent_description,
                    chat_agent_config,
                    request.is_active,
                    user_id,
                )
                agent.published_chat_agent_id = chat_agent.id

            agent.updated_by = user_id
            session.commit()
            session.refresh(chat_agent)

            logger.info(
                "ReACT agent published",
                extra={"re_act_agent_id": re_act_agent_id, "chat_agent_id": chat_agent.id},
            )

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, re_act_agent_id)

            return PublishReActAgentResponse(
                chat_agent_id=chat_agent.id,
                re_act_agent_id=re_act_agent_id,
                chat_agent_name=chat_agent.name,
                chat_agent_type=ChatAgentTypeEnum.REACT_AGENT,
                is_active=chat_agent.is_active,
            )

    @staticmethod
    def _create_chat_agent(
        session: Session,
        tenant_id: str,
        name: str,
        description: str | None,
        config: dict,
        is_active: bool,
        user_id: str,
    ) -> ChatAgent:
        """Create a new ChatAgent entry for a published ReACT agent.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            name: Chat agent name
            description: Chat agent description
            config: Chat agent config dict
            is_active: Active flag
            user_id: Creating user ID

        Returns:
            Created ChatAgent instance
        """
        chat_agent = ChatAgent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            description=description,
            type=ChatAgentTypeEnum.REACT_AGENT.value,
            config=config,
            is_active=is_active,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(chat_agent)
        return chat_agent

    def delete_re_act_agent(self, tenant_id: str, re_act_agent_id: str) -> None:
        """Delete a ReACT agent and all its versions.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
        """
        logger.info("Deleting ReACT agent", extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id})

        with self.db_client.get_session() as session:
            query = select(ReActAgent).where(ReActAgent.id == re_act_agent_id, ReActAgent.tenant_id == tenant_id)
            agent = session.execute(query).scalar_one_or_none()

            if not agent:
                raise ReActAgentNotFoundError(re_act_agent_id)

            session.delete(agent)
            session.commit()

            logger.info("ReACT agent deleted", extra={"re_act_agent_id": re_act_agent_id})

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, re_act_agent_id)
            self._invalidate_permissions_cache(tenant_id, re_act_agent_id)

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        if self.cache_client:
            pattern = f"re_act_agents:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, re_act_agent_id: str) -> None:
        """Invalidate detail cache for a specific agent."""
        if self.cache_client:
            cache_key = f"re_act_agents:detail:tenant:{tenant_id}:agent:{re_act_agent_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, re_act_agent_id: str) -> None:
        """Invalidate permissions cache for a specific agent."""
        if self.cache_client:
            pattern = f"re_act_agents:permissions:tenant:{tenant_id}:agent:{re_act_agent_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def list_re_act_agent_permissions(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> ResourcePrincipalsResponse:
        """List permissions for a ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            skip: Number of items to skip
            limit: Maximum number of items to return
            search: Optional search filter
            roles: Optional role filter
            is_active: Optional active status filter
            order_by: Column to order by
            order_direction: Sort direction
            use_cache: Whether to use cache

        Returns:
            Resource principals response
        """
        logger.info(
            "Listing ReACT agent permissions", extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id}
        )

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
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
            raise ReActAgentNotFoundError(re_act_agent_id) from e

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
            resource_id=re_act_agent_id, resource_type="re_act_agent", tenant_id=tenant_id, principals=principals
        )

    def get_re_act_agent_permission(
        self, tenant_id: str, re_act_agent_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """Get permission for a specific principal on a ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            principal_id: Principal ID

        Returns:
            Principal with roles response
        """
        logger.info(
            "Getting ReACT agent permission",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "principal_id": principal_id},
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
                principal_id=principal_id,
            )
        except ValueError as e:
            raise ReActAgentNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_re_act_agent_permission(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        request: SetReActAgentPermissionRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """Set or update a permission for a principal on a ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            request: Permission request data
            user_id: ID of the user setting the permission
            user: Authenticated user context

        Returns:
            Principal with roles response
        """
        logger.info(
            "Setting ReACT agent permission",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "principal_id": request.principal_id},
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )

            result = self.permissions_handler.get_permission(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
                principal_id=request.principal_id,
            )
        except ValueError as e:
            raise ReActAgentNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def delete_re_act_agent_permission(
        self, tenant_id: str, re_act_agent_id: str, principal_id: str, principal_type: str, permission: str
    ) -> None:
        """Delete a permission for a principal on a ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            principal_id: Principal ID
            principal_type: Type of principal
            permission: Permission to delete
        """
        logger.info(
            "Deleting ReACT agent permission",
            extra={
                "tenant_id": tenant_id,
                "re_act_agent_id": re_act_agent_id,
                "principal_id": principal_id,
                "permission": permission,
            },
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission,
            )
        except ValueError as e:
            raise ReActAgentNotFoundError(str(e)) from e

    def _resolve_user_permission(
        self, session: Session, tenant_id: str, re_act_agent_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific ReACT agent.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            re_act_agent_id: ReACT agent ID
            user: The authenticated user context

        Returns:
            Permission action string or None
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(user, tenant_id, [TenantRolesEnum.TENANT_GLOBAL_ADMIN, TenantRolesEnum.REACT_AGENT_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(
            session, ReActAgentMember, "re_act_agent_id", tenant_id, re_act_agent_id, principal_ids
        )

    @staticmethod
    def _model_to_response(agent: ReActAgent) -> ReActAgentResponse:
        """Convert a ReACT agent model (with loaded versions) to a response.

        The latest version's config fields are flattened into the response.

        Args:
            agent: ReACT agent model instance with versions loaded

        Returns:
            ReACT agent response
        """
        tags = []
        if hasattr(agent, "tags") and agent.tags:
            for agent_tag in agent.tags:
                if agent_tag.tag:
                    tags.append(TagSummary(id=agent_tag.tag.id, name=agent_tag.tag.name))

        latest = agent.versions[0] if agent.versions else None

        return ReActAgentResponse(
            id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            description=agent.description,
            is_active=agent.is_active,
            published_chat_agent_id=agent.published_chat_agent_id,
            current_version=latest.version if latest else None,
            ai_model_ids=latest.ai_model_ids if latest else [],
            system_prompt=latest.system_prompt if latest else None,
            tool_ids=latest.tool_ids if latest else [],
            security_prompt=latest.security_prompt if latest else None,
            tool_use_prompt=latest.tool_use_prompt if latest else None,
            response_prompt=latest.response_prompt if latest else None,
            greeting_messages=latest.greeting_messages if latest else [],
            config=latest.config if latest else {},
            tags=tags,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            created_by=agent.created_by,
            updated_by=agent.updated_by,
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
            re_act_agent_id=version.re_act_agent_id,
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
