"""Business logic handlers for ReACT agent operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List, Union

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import ReActAgent, ReActAgentMember, ReActAgentTag
from unifiedui.caching.client import CacheClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler

from unifiedui.schema.requests.re_act_agents import CreateReActAgentRequest, UpdateReActAgentRequest
from unifiedui.schema.requests.re_act_agent_permissions import SetReActAgentPermissionRequest
from unifiedui.schema.responses.re_act_agents import ReActAgentResponse
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.principals import (
    PrincipalWithRolesResponse,
    ResourcePrincipalsResponse
)
from unifiedui.exc.re_act_agents import ReActAgentNotFoundError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class ReActAgentHandler:
    """Handler class for ReACT agent business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None,
        permissions_handler: Optional[ResourcePermissionsHandler] = None,
        tags_handler: Optional[ResourceTagsHandler] = None
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
        name_filter: Optional[str] = None,
        is_active: Optional[int] = None,
        tag_ids: Optional[List[int]] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        view: Optional[str] = None,
        use_cache: bool = True
    ) -> Union[List[ReActAgentResponse], List[QuickListItemResponse]]:
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
        matching_tenant = next(
            (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
            None
        )

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            admin_permissions = [
                TenantRolesEnum.GLOBAL_ADMIN.value,
                TenantRolesEnum.REACT_AGENT_ADMIN.value
            ]
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
            query = select(ReActAgent).options(
                selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag)
            ).where(ReActAgent.tenant_id == tenant_id)

            if not is_admin:
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)

                member_subquery = (
                    select(ReActAgentMember.re_act_agent_id)
                    .where(
                        ReActAgentMember.tenant_id == tenant_id,
                        ReActAgentMember.principal_id.in_(principal_ids)
                    )
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
                    .where(
                        ReActAgentTag.tenant_id == tenant_id,
                        ReActAgentTag.tag_id.in_(tag_ids)
                    )
                    .distinct()
                )
                query = query.where(ReActAgent.id.in_(tag_subquery))

            if order_by and hasattr(ReActAgent, order_by):
                column = getattr(ReActAgent, order_by)
                if order_direction == "desc":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            agents = session.execute(query).scalars().all()

            logger.info("Retrieved ReACT agents", extra={"count": len(agents)})

            if view == "quick-list":
                return [QuickListItemResponse(id=agent.id, name=agent.name) for agent in agents]

            result = [self._model_to_response(agent) for agent in agents]

            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached ReACT agent list")
                except Exception as e:
                    logger.warning(f"Failed to cache ReACT agent list: {e}")

            return result

    def get_re_act_agent(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        use_cache: bool = True
    ) -> ReActAgentResponse:
        """Get a specific ReACT agent by ID.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
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
                    return ReActAgentResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached ReACT agent: {e}")

        with self.db_client.get_session() as session:
            query = select(ReActAgent).options(
                selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag)
            ).where(
                ReActAgent.id == re_act_agent_id,
                ReActAgent.tenant_id == tenant_id
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

            return result

    def create_re_act_agent(
        self,
        tenant_id: str,
        request: CreateReActAgentRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> ReActAgentResponse:
        """Create a new ReACT agent.

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

        with self.db_client.get_session() as session:
            agent = ReActAgent(
                id=agent_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                ai_model_ids=request.ai_model_ids,
                system_prompt=request.system_prompt,
                tool_ids=request.tool_ids,
                security_prompt=request.security_prompt,
                tool_use_prompt=request.tool_use_prompt,
                response_prompt=request.response_prompt,
                greeting_messages=request.greeting_messages,
                config=request.config or {},
                is_active=request.is_active,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(agent)

            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=agent_id,
                user_id=user_id,
                user=user
            )

            session.commit()
            session.refresh(agent)

            logger.info("ReACT agent created", extra={"agent_id": agent_id})

            self._invalidate_list_cache(tenant_id)

            return self._model_to_response(agent)

    def update_re_act_agent(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        request: UpdateReActAgentRequest,
        user_id: str
    ) -> ReActAgentResponse:
        """Update an existing ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
            request: Update request data
            user_id: ID of the updating user

        Returns:
            Updated ReACT agent response
        """
        logger.info("Updating ReACT agent", extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id})

        with self.db_client.get_session() as session:
            query = select(ReActAgent).options(
                selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag)
            ).where(
                ReActAgent.id == re_act_agent_id,
                ReActAgent.tenant_id == tenant_id
            )
            agent = session.execute(query).scalar_one_or_none()

            if not agent:
                raise ReActAgentNotFoundError(re_act_agent_id)

            if request.name is not None:
                agent.name = request.name
            if request.description is not None:
                agent.description = request.description
            if request.ai_model_ids is not None:
                agent.ai_model_ids = request.ai_model_ids
            if request.system_prompt is not None:
                agent.system_prompt = request.system_prompt
            if request.tool_ids is not None:
                agent.tool_ids = request.tool_ids
            if request.security_prompt is not None:
                agent.security_prompt = request.security_prompt
            if request.tool_use_prompt is not None:
                agent.tool_use_prompt = request.tool_use_prompt
            if request.response_prompt is not None:
                agent.response_prompt = request.response_prompt
            if request.greeting_messages is not None:
                agent.greeting_messages = request.greeting_messages
            if request.config is not None:
                agent.config = request.config
            if request.is_active is not None:
                agent.is_active = request.is_active

            agent.updated_by = user_id

            session.commit()
            session.refresh(agent)

            query = select(ReActAgent).options(
                selectinload(ReActAgent.tags).selectinload(ReActAgentTag.tag)
            ).where(ReActAgent.id == re_act_agent_id)
            agent = session.execute(query).scalar_one()

            logger.info("ReACT agent updated", extra={"re_act_agent_id": re_act_agent_id})

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, re_act_agent_id)

            return self._model_to_response(agent)

    def delete_re_act_agent(
        self,
        tenant_id: str,
        re_act_agent_id: str
    ) -> None:
        """Delete a ReACT agent.

        Args:
            tenant_id: Tenant ID for scoping
            re_act_agent_id: ReACT agent ID
        """
        logger.info("Deleting ReACT agent", extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id})

        with self.db_client.get_session() as session:
            query = select(ReActAgent).where(
                ReActAgent.id == re_act_agent_id,
                ReActAgent.tenant_id == tenant_id
            )
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
        search: Optional[str] = None,
        roles: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        use_cache: bool = True
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
        logger.info("Listing ReACT agent permissions", extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id})

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
                use_cache=use_cache
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
                is_active=p.get("is_active", True)
            )
            for p in result["principals"]
        ]

        return ResourcePrincipalsResponse(
            resource_id=re_act_agent_id,
            resource_type="re_act_agent",
            tenant_id=tenant_id,
            principals=principals
        )

    def get_re_act_agent_permission(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        principal_id: str
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
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "principal_id": principal_id}
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
                principal_id=principal_id
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
            description=result.get("description")
        )

    def set_re_act_agent_permission(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        request: SetReActAgentPermissionRequest,
        user_id: str,
        user: ContextIdentityUser
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
            extra={
                "tenant_id": tenant_id,
                "re_act_agent_id": re_act_agent_id,
                "principal_id": request.principal_id
            }
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
                user=user
            )

            result = self.permissions_handler.get_permission(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
                principal_id=request.principal_id
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
            description=result.get("description")
        )

    def delete_re_act_agent_permission(
        self,
        tenant_id: str,
        re_act_agent_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
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
                "permission": permission
            }
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="re_act_agent",
                tenant_id=tenant_id,
                resource_id=re_act_agent_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission
            )
        except ValueError as e:
            raise ReActAgentNotFoundError(str(e)) from e

    @staticmethod
    def _model_to_response(agent: ReActAgent) -> ReActAgentResponse:
        """Convert a ReACT agent model to a response.

        Args:
            agent: ReACT agent model instance

        Returns:
            ReACT agent response
        """
        tags = []
        if hasattr(agent, 'tags') and agent.tags:
            for agent_tag in agent.tags:
                if agent_tag.tag:
                    tags.append(TagSummary(
                        id=agent_tag.tag.id,
                        name=agent_tag.tag.name
                    ))

        return ReActAgentResponse(
            id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            description=agent.description,
            ai_model_ids=agent.ai_model_ids or [],
            system_prompt=agent.system_prompt,
            tool_ids=agent.tool_ids or [],
            security_prompt=agent.security_prompt,
            tool_use_prompt=agent.tool_use_prompt,
            response_prompt=agent.response_prompt,
            greeting_messages=agent.greeting_messages or [],
            config=agent.config or {},
            is_active=agent.is_active,
            tags=tags,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            created_by=agent.created_by,
            updated_by=agent.updated_by
        )
