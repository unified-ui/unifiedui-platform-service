"""Business logic handlers for tool operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import PermissionActionEnum, ToolTypeEnum
from unifiedui.core.database.models import Credential, Tool, ToolMember, ToolTag
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
    from unifiedui.schema.requests.tool_permissions import SetToolPermissionRequest
    from unifiedui.schema.requests.tools import CreateToolRequest, UpdateToolRequest

from unifiedui.exc.tools import InvalidToolCredentialError, ToolNotFoundError
from unifiedui.handlers.validators.tool_validator import ToolConfigValidatorFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.tools import ToolResponse

logger = get_logger(__name__)


class ToolHandler:
    """Handler class for tool business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
    ):
        """
        Initialize the tool handler.

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

    def list_tools(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        type_filter: list[str] | None = None,
        is_active: int | None = None,
        tag_ids: list[int] | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        view: str | None = None,
        use_cache: bool = True,
    ) -> list[ToolResponse] | list[QuickListItemResponse]:
        """
        Get a list of tools for a tenant (filtered by permissions).

        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by tool name
            type_filter: Optional list of tool types to filter by (e.g., ['MCP_SERVER', 'OPENAPI_DEFINITION'])
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            view: Optional view type ('full' or 'quick-list')
            use_cache: Whether to use caching

        Returns:
            List of tool responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing tools", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        # Check if user is admin (has GLOBAL_ADMIN or REACT_AGENT_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            admin_permissions = [TenantRolesEnum.GLOBAL_ADMIN.value, TenantRolesEnum.REACT_AGENT_ADMIN.value]
            is_admin = any(perm in user_roles for perm in admin_permissions)

        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]

        # Build cache key
        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"tools:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"

        # Check if any filters are applied
        has_filters = name_filter is not None or type_filter is not None or tag_ids is not None

        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached tool list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [ToolResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached tool list: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(Tool)
                .options(selectinload(Tool.tags).selectinload(ToolTag.tag))
                .where(Tool.tenant_id == tenant_id)
            )

            # Filter by permissions if not admin
            if not is_admin:
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)

                member_subquery = (
                    select(ToolMember.tool_id)
                    .where(ToolMember.tenant_id == tenant_id, ToolMember.principal_id.in_(principal_ids))
                    .distinct()
                )

                query = query.where(Tool.id.in_(member_subquery))

            if name_filter:
                query = query.where(Tool.name.ilike(f"%{name_filter}%"))

            # Filter by tool type
            if type_filter:
                query = query.where(Tool.type.in_(type_filter))

            # Filter by is_active status
            if is_active is not None:
                query = query.where(Tool.is_active == bool(is_active))

            # Filter by tags
            if tag_ids:
                tag_subquery = (
                    select(ToolTag.tool_id)
                    .where(ToolTag.tenant_id == tenant_id, ToolTag.tag_id.in_(tag_ids))
                    .distinct()
                )
                query = query.where(Tool.id.in_(tag_subquery))

            # Apply ordering
            if order_by and hasattr(Tool, order_by):
                column = getattr(Tool, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            tools = session.execute(query).scalars().all()

            logger.info("Retrieved tools", extra={"count": len(tools)})

            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=tool.id, name=tool.name) for tool in tools]

            result = [self._model_to_response(tool) for tool in tools]

            if is_admin:
                for r in result:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in result]
                if resource_ids:
                    permissions = resolve_my_permissions_bulk(
                        session, ToolMember, "tool_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in result:
                        r.my_permission = permissions.get(r.id)

            # Cache the result
            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached tool list")
                except Exception as e:
                    logger.warning(f"Failed to cache tool list: {e}")

            return result

    def get_tool(
        self, tenant_id: str, tool_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> ToolResponse:
        """
        Get a specific tool by ID.

        Args:
            tenant_id: The ID of the tenant
            tool_id: The ID of the tool
            user: Optional user context for permission resolution
            use_cache: Whether to use caching

        Returns:
            Tool response

        Raises:
            ToolNotFoundError: If tool not found
        """
        logger.info("Fetching tool", extra={"tenant_id": tenant_id, "tool_id": tool_id})

        cache_key = f"tools:detail:tenant:{tenant_id}:tool:{tool_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached tool")
                    result = ToolResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(session, tenant_id, tool_id, user)
                    return result
            except Exception as e:
                logger.warning(f"Failed to get cached tool: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(Tool)
                .options(selectinload(Tool.tags).selectinload(ToolTag.tag))
                .where(Tool.id == tool_id, Tool.tenant_id == tenant_id)
            )
            tool = session.execute(query).scalar_one_or_none()

            if not tool:
                raise ToolNotFoundError(tool_id)

            result = self._model_to_response(tool)

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached tool detail")
                except Exception as e:
                    logger.warning(f"Failed to cache tool: {e}")

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, tool_id, user)

            return result

    def create_tool(
        self, tenant_id: str, request: CreateToolRequest, user_id: str, user: ContextIdentityUser
    ) -> ToolResponse:
        """
        Create a new tool.

        Args:
            tenant_id: The ID of the tenant
            request: Tool creation data
            user_id: The ID of the user creating the tool
            user: The authenticated user context

        Returns:
            Created tool response
        """
        logger.info("Creating tool", extra={"tenant_id": tenant_id, "tool_name": request.name})

        # Validate config based on tool type
        validated_config = {}
        if request.config:
            validated_config = ToolConfigValidatorFactory.validate_config(
                tool_type=request.type.value, config=request.config
            )

        tool_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            # Validate credential_id if provided
            if request.credential_id:
                credential = session.execute(
                    select(Credential).where(Credential.id == request.credential_id, Credential.tenant_id == tenant_id)
                ).scalar_one_or_none()
                if not credential:
                    raise InvalidToolCredentialError(request.credential_id, "not found")

            # Create tool
            tool = Tool(
                id=tool_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value,
                config=validated_config,
                credential_id=request.credential_id,
                is_active=request.is_active,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(tool)

            # Add creator as admin member using central handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="tool",
                tenant_id=tenant_id,
                resource_id=tool_id,
                user_id=user_id,
                user=user,
            )

            session.commit()
            session.refresh(tool)

            logger.info("Tool created", extra={"tool_id": tool_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)

            return self._model_to_response(tool)

    def update_tool(self, tenant_id: str, tool_id: str, request: UpdateToolRequest, user_id: str) -> ToolResponse:
        """
        Update an existing tool.

        Args:
            tenant_id: The ID of the tenant
            tool_id: The ID of the tool
            request: Tool update data
            user_id: The ID of the user updating the tool

        Returns:
            Updated tool response

        Raises:
            ToolNotFoundError: If tool not found
        """
        logger.info("Updating tool", extra={"tenant_id": tenant_id, "tool_id": tool_id})

        with self.db_client.get_session() as session:
            query = (
                select(Tool)
                .options(selectinload(Tool.tags).selectinload(ToolTag.tag))
                .where(Tool.id == tool_id, Tool.tenant_id == tenant_id)
            )
            tool = session.execute(query).scalar_one_or_none()

            if not tool:
                raise ToolNotFoundError(tool_id)

            # Determine the tool type for config validation
            tool_type = request.type if request.type is not None else ToolTypeEnum(tool.type)

            # Update fields if provided
            if request.name is not None:
                tool.name = request.name
            if request.description is not None:
                tool.description = request.description
            if request.type is not None:
                tool.type = request.type.value
            if request.config is not None:
                validated_config = ToolConfigValidatorFactory.validate_config(
                    tool_type=tool_type.value, config=request.config
                )
                tool.config = validated_config
            if request.credential_id is not None:
                # Validate credential if provided (empty string = remove credential)
                if request.credential_id:
                    credential = session.execute(
                        select(Credential).where(
                            Credential.id == request.credential_id, Credential.tenant_id == tenant_id
                        )
                    ).scalar_one_or_none()
                    if not credential:
                        raise InvalidToolCredentialError(request.credential_id, "not found")
                    tool.credential_id = request.credential_id
                else:
                    tool.credential_id = None
            if request.is_active is not None:
                tool.is_active = request.is_active

            tool.updated_by = user_id

            session.commit()
            session.refresh(tool)

            # Re-fetch with tags for response
            query = select(Tool).options(selectinload(Tool.tags).selectinload(ToolTag.tag)).where(Tool.id == tool_id)
            tool = session.execute(query).scalar_one()

            logger.info("Tool updated", extra={"tool_id": tool_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, tool_id)

            return self._model_to_response(tool)

    def delete_tool(self, tenant_id: str, tool_id: str) -> None:
        """
        Delete a tool.

        Args:
            tenant_id: The ID of the tenant
            tool_id: The ID of the tool

        Raises:
            ToolNotFoundError: If tool not found
        """
        logger.info("Deleting tool", extra={"tenant_id": tenant_id, "tool_id": tool_id})

        with self.db_client.get_session() as session:
            query = select(Tool).where(Tool.id == tool_id, Tool.tenant_id == tenant_id)
            tool = session.execute(query).scalar_one_or_none()

            if not tool:
                raise ToolNotFoundError(tool_id)

            session.delete(tool)
            session.commit()

            logger.info("Tool deleted", extra={"tool_id": tool_id})

            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, tool_id)
            self._invalidate_permissions_cache(tenant_id, tool_id)

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        if self.cache_client:
            pattern = f"tools:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, tool_id: str) -> None:
        """Invalidate detail cache for a tool."""
        if self.cache_client:
            cache_key = f"tools:detail:tenant:{tenant_id}:tool:{tool_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, tool_id: str) -> None:
        """Invalidate permissions cache for a tool."""
        if self.cache_client:
            pattern = f"tools:permissions:tenant:{tenant_id}:tool:{tool_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    # ========== Permission Management Methods ==========

    def list_tool_permissions(
        self,
        tenant_id: str,
        tool_id: str,
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
        List all permissions for a tool, grouped by principal.

        Args:
            tenant_id: The ID of the tenant
            tool_id: The ID of the tool
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
        """
        logger.info("Listing tool permissions", extra={"tenant_id": tenant_id, "tool_id": tool_id})

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="tool",
                tenant_id=tenant_id,
                resource_id=tool_id,
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
            raise ToolNotFoundError(tool_id) from e

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
            resource_id=tool_id, resource_type="tool", tenant_id=tenant_id, principals=principals
        )

    def get_tool_permission(self, tenant_id: str, tool_id: str, principal_id: str) -> PrincipalWithRolesResponse:
        """
        Get all permissions for a specific principal on a tool.
        """
        logger.info(
            "Getting tool permission", extra={"tenant_id": tenant_id, "tool_id": tool_id, "principal_id": principal_id}
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="tool", tenant_id=tenant_id, resource_id=tool_id, principal_id=principal_id
            )
        except ValueError as e:
            raise ToolNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_tool_permission(
        self, tenant_id: str, tool_id: str, request: SetToolPermissionRequest, user_id: str, user: ContextIdentityUser
    ) -> PrincipalWithRolesResponse:
        """
        Set or update a permission for a principal on a tool.
        """
        logger.info(
            "Setting tool permission",
            extra={"tenant_id": tenant_id, "tool_id": tool_id, "principal_id": request.principal_id},
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="tool",
                tenant_id=tenant_id,
                resource_id=tool_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )

            result = self.permissions_handler.get_permission(
                resource_type="tool", tenant_id=tenant_id, resource_id=tool_id, principal_id=request.principal_id
            )
        except ValueError as e:
            raise ToolNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def delete_tool_permission(
        self, tenant_id: str, tool_id: str, principal_id: str, principal_type: str, permission: str
    ) -> None:
        """
        Delete a specific permission for a principal on a tool.
        """
        logger.info(
            "Deleting tool permission",
            extra={"tenant_id": tenant_id, "tool_id": tool_id, "principal_id": principal_id, "permission": permission},
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="tool",
                tenant_id=tenant_id,
                resource_id=tool_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission,
            )
        except ValueError as e:
            raise ToolNotFoundError(str(e)) from e

    def _resolve_user_permission(
        self, session: object, tenant_id: str, tool_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific tool.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            tool_id: Tool ID
            user: The authenticated user context

        Returns:
            Permission action string or None
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(user, tenant_id, [TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.REACT_AGENT_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(session, ToolMember, "tool_id", tenant_id, tool_id, principal_ids)

    @staticmethod
    def _model_to_response(tool: Tool) -> ToolResponse:
        """Convert Tool model to ToolResponse."""
        tags = []
        if hasattr(tool, "tags") and tool.tags:
            for tool_tag in tool.tags:
                if tool_tag.tag:
                    tags.append(TagSummary(id=tool_tag.tag.id, name=tool_tag.tag.name))

        return ToolResponse(
            id=tool.id,
            tenant_id=tool.tenant_id,
            name=tool.name,
            description=tool.description,
            type=tool.type,
            is_active=tool.is_active,
            config=tool.config,
            credential_id=tool.credential_id,
            tags=tags,
            created_at=tool.created_at,
            updated_at=tool.updated_at,
            created_by=tool.created_by,
            updated_by=tool.updated_by,
        )
