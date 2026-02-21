"""API routes for tag management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import PermissionActionEnum, TenantRolesEnum, UserPermissionEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.tags import TagNotFoundError
from unifiedui.handlers.dependencies import get_tag_handler
from unifiedui.handlers.tags import TagHandler
from unifiedui.logger import get_logger
from unifiedui.schema.requests.tags import CreateTagRequest, SetResourceTagsRequest
from unifiedui.schema.responses.tags import TagResponse, TagSummary

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/tags")


# ========== Tenant Tag Endpoints ==========


@router.get(
    "", response_model=list[TagSummary], summary="List tags", description="Get a list of tags for the current tenant"
)
@authenticate()
async def list_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """
    List tags for a tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        name: Optional filter by tag name (disables caching when used)
        skip: Number of tags to skip for pagination
        limit: Maximum number of tags to return
        handler: Tag handler dependency

    Returns:
        List of tags
    """
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name,
                "skip": skip,
                "limit": limit,
            },
        )

        return handler.list_tags(tenant_id=tenant_id, name_filter=name, skip=skip, limit=limit, use_cache=use_cache)
    except Exception as e:
        logger.error(f"Failed to list tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list tags")


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create a new tag. Any authenticated tenant member can create tags.",
)
@authenticate()
async def create_tag(
    request: Request, tenant_id: str, create_request: CreateTagRequest, handler: TagHandler = Depends(get_tag_handler)
) -> TagResponse:
    """
    Create a new tag.

    Any authenticated tenant member can create tags.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Tag creation data
        handler: Tag handler dependency

    Returns:
        Created tag
    """
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Create tag",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "tag_name": create_request.name},
        )

        return handler.create_tag(tenant_id=tenant_id, name=create_request.name, user=user)
    except Exception as e:
        logger.error(f"Failed to create tag: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create tag")


# ========== Resource Type Tags Routers ==========
# These routers expose tags per resource type at /{resource_type}/tags

# Chat Agents Tags Router
chat_agents_tags_list_router = APIRouter(prefix="/chat-agents/tags")


@chat_agents_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for chat agents",
    description="Get all tags that are applied to chat agents",
)
@authenticate()
async def list_chat_agent_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to chat agents."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for chat agents",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name,
                "skip": skip,
                "limit": limit,
            },
        )

        return handler.list_tags_for_resource(
            tenant_id=tenant_id,
            resource_type="chat_agent",
            name_filter=name,
            skip=skip,
            limit=limit,
            use_cache=use_cache,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list chat agent tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat agent tags")


# Autonomous Agents Tags Router
autonomous_agents_tags_list_router = APIRouter(prefix="/autonomous-agents/tags")


@autonomous_agents_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for autonomous agents",
    description="Get all tags that are applied to autonomous agents",
)
@authenticate()
async def list_autonomous_agent_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to autonomous agents."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for autonomous agents",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name,
                "skip": skip,
                "limit": limit,
            },
        )

        return handler.list_tags_for_resource(
            tenant_id=tenant_id,
            resource_type="autonomous_agent",
            name_filter=name,
            skip=skip,
            limit=limit,
            use_cache=use_cache,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list autonomous agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list autonomous agent tags"
        )


# Chat Widgets Tags Router
chat_widgets_tags_list_router = APIRouter(prefix="/chat-widgets/tags")


@chat_widgets_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for chat widgets",
    description="Get all tags that are applied to chat widgets",
)
@authenticate()
async def list_chat_widget_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to chat widgets."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for chat widgets",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name,
                "skip": skip,
                "limit": limit,
            },
        )

        return handler.list_tags_for_resource(
            tenant_id=tenant_id,
            resource_type="chat_widget",
            name_filter=name,
            skip=skip,
            limit=limit,
            use_cache=use_cache,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list chat widget tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat widget tags")


# Credentials Tags Router
credentials_tags_list_router = APIRouter(prefix="/credentials/tags")


@credentials_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for credentials",
    description="Get all tags that are applied to credentials",
)
@authenticate()
async def list_credential_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to credentials."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for credentials",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name,
                "skip": skip,
                "limit": limit,
            },
        )

        return handler.list_tags_for_resource(
            tenant_id=tenant_id,
            resource_type="credential",
            name_filter=name,
            skip=skip,
            limit=limit,
            use_cache=use_cache,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list credential tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list credential tags")


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag. Only GLOBAL_ADMIN or the tag creator can delete.",
)
@authenticate()
@check_permissions(entity="tag", required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, UserPermissionEnum.IS_CREATOR])
async def delete_tag(
    request: Request, tenant_id: str, tag_id: int, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """
    Delete a tag.

    Only GLOBAL_ADMIN or the tag creator can delete a tag.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        tag_id: Tag ID from path
        handler: Tag handler dependency

    Returns:
        No content (204)
    """
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete tag", extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "tag_id": tag_id}
        )

        handler.delete_tag(tenant_id=tenant_id, tag_id=tag_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except TagNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete tag: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tag")


# ========== Chat Agent Tag Endpoints ==========

chat_agent_tags_router = APIRouter(prefix="/chat-agents/{chat_agent_id}/tags")


@chat_agent_tags_router.get(
    "", response_model=list[TagResponse], summary="Get chat agent tags", description="Get tags for a chat agent"
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_chat_agent_tags(
    request: Request, tenant_id: str, chat_agent_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for a chat agent."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get chat agent tags",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id, resource_type="chat_agent", resource_id=chat_agent_id, use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get chat agent tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat agent tags")


@chat_agent_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set chat agent tags",
    description="Set tags for a chat agent (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_chat_agent_tags(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for a chat agent."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set chat agent tags",
            extra={
                "tenant_id": tenant_id,
                "chat_agent_id": chat_agent_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags,
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="chat_agent",
            resource_id=chat_agent_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error(f"Failed to set chat agent tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set chat agent tags")


@chat_agent_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat agent tags",
    description="Remove all tags from a chat agent",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_chat_agent_tags(
    request: Request, tenant_id: str, chat_agent_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a chat agent."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete chat agent tags",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
        )

        handler.delete_resource_tags(tenant_id=tenant_id, resource_type="chat_agent", resource_id=chat_agent_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete chat agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat agent tags"
        )


# ========== Autonomous Agent Tag Endpoints ==========

autonomous_agent_tags_router = APIRouter(prefix="/autonomous-agents/{autonomous_agent_id}/tags")


@autonomous_agent_tags_router.get(
    "",
    response_model=list[TagResponse],
    summary="Get autonomous agent tags",
    description="Get tags for an autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_autonomous_agent_tags(
    request: Request, tenant_id: str, autonomous_agent_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for an autonomous agent."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get autonomous agent tags",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "user_id": user.identity.get_id(),
            },
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id, resource_type="autonomous_agent", resource_id=autonomous_agent_id, use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get autonomous agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get autonomous agent tags"
        )


@autonomous_agent_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set autonomous agent tags",
    description="Set tags for an autonomous agent (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_autonomous_agent_tags(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for an autonomous agent."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set autonomous agent tags",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags,
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="autonomous_agent",
            resource_id=autonomous_agent_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error(f"Failed to set autonomous agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set autonomous agent tags"
        )


@autonomous_agent_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete autonomous agent tags",
    description="Remove all tags from an autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_autonomous_agent_tags(
    request: Request, tenant_id: str, autonomous_agent_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from an autonomous agent."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete autonomous agent tags",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "user_id": user.identity.get_id(),
            },
        )

        handler.delete_resource_tags(
            tenant_id=tenant_id, resource_type="autonomous_agent", resource_id=autonomous_agent_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete autonomous agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete autonomous agent tags"
        )


# ========== Chat Widget Tag Endpoints ==========

chat_widget_tags_router = APIRouter(prefix="/chat-widgets/{chat_widget_id}/tags")


@chat_widget_tags_router.get(
    "", response_model=list[TagResponse], summary="Get chat widget tags", description="Get tags for a chat widget"
)
@authenticate()
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_chat_widget_tags(
    request: Request, tenant_id: str, chat_widget_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for a chat widget."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get chat widget tags",
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "user_id": user.identity.get_id()},
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id, resource_type="chat_widget", resource_id=chat_widget_id, use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get chat widget tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat widget tags")


@chat_widget_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set chat widget tags",
    description="Set tags for a chat widget (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_chat_widget_tags(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for a chat widget."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set chat widget tags",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags,
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="chat_widget",
            resource_id=chat_widget_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error(f"Failed to set chat widget tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set chat widget tags")


@chat_widget_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat widget tags",
    description="Remove all tags from a chat widget",
)
@authenticate()
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_chat_widget_tags(
    request: Request, tenant_id: str, chat_widget_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a chat widget."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete chat widget tags",
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "user_id": user.identity.get_id()},
        )

        handler.delete_resource_tags(tenant_id=tenant_id, resource_type="chat_widget", resource_id=chat_widget_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete chat widget tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat widget tags"
        )


# ========== Credential Tag Endpoints ==========

credential_tags_router = APIRouter(prefix="/credentials/{credential_id}/tags")


@credential_tags_router.get(
    "", response_model=list[TagResponse], summary="Get credential tags", description="Get tags for a credential"
)
@authenticate()
@check_permissions(
    entity="credential",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_credential_tags(
    request: Request, tenant_id: str, credential_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for a credential."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get credential tags",
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "user_id": user.identity.get_id()},
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id, resource_type="credential", resource_id=credential_id, use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get credential tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get credential tags")


@credential_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set credential tags",
    description="Set tags for a credential (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="credential",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_credential_tags(
    request: Request,
    tenant_id: str,
    credential_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for a credential."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set credential tags",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags,
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="credential",
            resource_id=credential_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error(f"Failed to set credential tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set credential tags")


@credential_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credential tags",
    description="Remove all tags from a credential",
)
@authenticate()
@check_permissions(
    entity="credential",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_credential_tags(
    request: Request, tenant_id: str, credential_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a credential."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete credential tags",
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "user_id": user.identity.get_id()},
        )

        handler.delete_resource_tags(tenant_id=tenant_id, resource_type="credential", resource_id=credential_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete credential tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete credential tags"
        )


# ========== Tools Tags List Router ==========

tools_tags_list_router = APIRouter(prefix="/tools/tags")


@tools_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for tools",
    description="Get all tags that are applied to tools",
)
@authenticate()
async def list_tool_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to tools."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for tools",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name,
                "skip": skip,
                "limit": limit,
            },
        )

        return handler.list_tags_for_resource(
            tenant_id=tenant_id, resource_type="tool", name_filter=name, skip=skip, limit=limit, use_cache=use_cache
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list tool tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list tool tags")


# ========== Tool Tag Endpoints ==========

tool_tags_router = APIRouter(prefix="/tools/{tool_id}/tags")


@tool_tags_router.get("", response_model=list[TagResponse], summary="Get tool tags", description="Get tags for a tool")
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_tool_tags(
    request: Request, tenant_id: str, tool_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for a tool."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get tool tags", extra={"tenant_id": tenant_id, "tool_id": tool_id, "user_id": user.identity.get_id()}
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id, resource_type="tool", resource_id=tool_id, user=user, use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get tool tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get tool tags")


@tool_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set tool tags",
    description="Set tags for a tool (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_tool_tags(
    request: Request,
    tenant_id: str,
    tool_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for a tool (replaces existing tags)."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set tool tags",
            extra={
                "tenant_id": tenant_id,
                "tool_id": tool_id,
                "tags": tags_request.tags,
                "user_id": user.identity.get_id(),
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id, resource_type="tool", resource_id=tool_id, tag_names=tags_request.tags, user=user
        )
    except Exception as e:
        logger.error(f"Failed to set tool tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set tool tags")


@tool_tags_router.delete(
    "", status_code=status.HTTP_204_NO_CONTENT, summary="Delete tool tags", description="Remove all tags from a tool"
)
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_tool_tags(
    request: Request, tenant_id: str, tool_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a tool."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete tool tags",
            extra={"tenant_id": tenant_id, "tool_id": tool_id, "user_id": user.identity.get_id()},
        )

        handler.delete_resource_tags(tenant_id=tenant_id, resource_type="tool", resource_id=tool_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete tool tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tool tags")


# ========== ReACT Agent Tags List Router ==========

re_act_agents_tags_list_router = APIRouter(prefix="/re-act-agents/tags")


@re_act_agents_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for ReACT agents",
    description="Get all tags that are applied to ReACT agents",
)
@authenticate()
async def list_re_act_agent_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to ReACT agents."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for ReACT agents",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name,
                "skip": skip,
                "limit": limit,
            },
        )

        return handler.list_tags_for_resource(
            tenant_id=tenant_id,
            resource_type="re_act_agent",
            name_filter=name,
            skip=skip,
            limit=limit,
            use_cache=use_cache,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list ReACT agent tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list ReACT agent tags")


# ========== ReACT Agent Tag Endpoints ==========

re_act_agent_tags_router = APIRouter(prefix="/re-act-agents/{re_act_agent_id}/tags")


@re_act_agent_tags_router.get(
    "", response_model=list[TagResponse], summary="Get ReACT agent tags", description="Get tags for a ReACT agent"
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_re_act_agent_tags(
    request: Request, tenant_id: str, re_act_agent_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for a ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get ReACT agent tags",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "user_id": user.identity.get_id()},
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id,
            resource_type="re_act_agent",
            resource_id=re_act_agent_id,
            user=user,
            use_cache=use_cache,
        )
    except Exception as e:
        logger.error(f"Failed to get ReACT agent tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get ReACT agent tags")


@re_act_agent_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set ReACT agent tags",
    description="Set tags for a ReACT agent (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_re_act_agent_tags(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for a ReACT agent (replaces existing tags)."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set ReACT agent tags",
            extra={
                "tenant_id": tenant_id,
                "re_act_agent_id": re_act_agent_id,
                "tags": tags_request.tags,
                "user_id": user.identity.get_id(),
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="re_act_agent",
            resource_id=re_act_agent_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error(f"Failed to set ReACT agent tags: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set ReACT agent tags")


@re_act_agent_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete ReACT agent tags",
    description="Remove all tags from a ReACT agent",
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_re_act_agent_tags(
    request: Request, tenant_id: str, re_act_agent_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete ReACT agent tags",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "user_id": user.identity.get_id()},
        )

        handler.delete_resource_tags(tenant_id=tenant_id, resource_type="re_act_agent", resource_id=re_act_agent_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete ReACT agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete ReACT agent tags"
        )
