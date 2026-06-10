"""API routes for tag management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import PermissionActionEnum, TenantRolesEnum, UserPermissionEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.tags import TagNotFoundError
from unifiedui.handlers.dependencies import get_tag_handler
from unifiedui.handlers.field_filter import filtered_response
from unifiedui.handlers.tags import TagHandler
from unifiedui.logger import get_logger
from unifiedui.schema.requests.tags import CreateTagRequest, SetResourceTagsRequest
from unifiedui.schema.responses.tags import TagResponse, TagSummary

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/tags")


# ========== Tenant Tag Endpoints ==========


@router.get("", summary="List tags", description="Get a list of tags for the current tenant")
@authenticate()
async def list_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: TagHandler = Depends(get_tag_handler),
):
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

        return filtered_response(
            handler.list_tags(tenant_id=tenant_id, name_filter=name, skip=skip, limit=limit, use_cache=use_cache),
            fields,
        )
    except Exception as e:
        logger.error("Failed to list tags: %s", e, exc_info=True)
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
        logger.error("Failed to create tag: %s", e, exc_info=True)
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
        logger.error("Failed to list chat agent tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat agent tags")


# Workflows Tags Router
workflows_tags_list_router = APIRouter(prefix="/workflows/tags")


@workflows_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for workflows",
    description="Get all tags that are applied to workflows",
)
@authenticate()
async def list_workflow_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to workflows."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for workflows",
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
            resource_type="workflow",
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
        logger.error("Failed to list workflow tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list workflow tags")


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
        logger.error("Failed to list chat widget tags: %s", e, exc_info=True)
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
        logger.error("Failed to list credential tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list credential tags")


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag. Only TENANT_GLOBAL_ADMIN or the tag creator can delete.",
)
@authenticate()
@check_permissions(
    entity="tag", required_permissions=[TenantRolesEnum.TENANT_GLOBAL_ADMIN, UserPermissionEnum.IS_CREATOR]
)
async def delete_tag(
    request: Request, tenant_id: str, tag_id: int, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """
    Delete a tag.

    Only TENANT_GLOBAL_ADMIN or the tag creator can delete a tag.

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
        logger.error("Failed to delete tag: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to get chat agent tags: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to set chat agent tags: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to delete chat agent tags: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat agent tags"
        )


# ========== Workflow Tag Endpoints ==========

workflow_tags_router = APIRouter(prefix="/workflows/{workflow_id}/tags")


@workflow_tags_router.get(
    "",
    response_model=list[TagResponse],
    summary="Get workflow tags",
    description="Get tags for a workflow",
)
@authenticate()
@check_permissions(
    entity="workflow",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.WORKFLOWS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_workflow_tags(
    request: Request, tenant_id: str, workflow_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for a workflow."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get workflow tags",
            extra={
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "user_id": user.identity.get_id(),
            },
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id, resource_type="workflow", resource_id=workflow_id, use_cache=use_cache
        )
    except Exception as e:
        logger.error("Failed to get workflow tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get workflow tags")


@workflow_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set workflow tags",
    description="Set tags for a workflow (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="workflow",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.WORKFLOWS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_workflow_tags(
    request: Request,
    tenant_id: str,
    workflow_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for a workflow."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set workflow tags",
            extra={
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags,
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="workflow",
            resource_id=workflow_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error("Failed to set workflow tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set workflow tags")


@workflow_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workflow tags",
    description="Remove all tags from a workflow",
)
@authenticate()
@check_permissions(
    entity="workflow",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.WORKFLOWS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_workflow_tags(
    request: Request, tenant_id: str, workflow_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a workflow."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete workflow tags",
            extra={
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "user_id": user.identity.get_id(),
            },
        )

        handler.delete_resource_tags(tenant_id=tenant_id, resource_type="workflow", resource_id=workflow_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error("Failed to delete workflow tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete workflow tags")


# ========== Chat Widget Tag Endpoints ==========

chat_widget_tags_router = APIRouter(prefix="/chat-widgets/{chat_widget_id}/tags")


@chat_widget_tags_router.get(
    "", response_model=list[TagResponse], summary="Get chat widget tags", description="Get tags for a chat widget"
)
@authenticate()
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to get chat widget tags: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to set chat widget tags: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to delete chat widget tags: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to get credential tags: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to set credential tags: %s", e, exc_info=True)
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
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
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
        logger.error("Failed to delete credential tags: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete credential tags"
        )


# ========== External App Tags List Router ==========

external_apps_tags_list_router = APIRouter(prefix="/external-apps/tags")


@external_apps_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for external apps",
    description="Get all tags that are applied to external apps",
)
@authenticate()
async def list_external_app_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to external apps."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for external apps",
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
            resource_type="external_app",
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
        logger.error("Failed to list external app tags: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list external app tags"
        )


# ========== External App Tag Endpoints ==========

external_app_tags_router = APIRouter(prefix="/external-apps/{external_app_id}/tags")


@external_app_tags_router.get(
    "",
    response_model=list[TagResponse],
    summary="Get external app tags",
    description="Get tags for an external app",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_external_app_tags(
    request: Request, tenant_id: str, external_app_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for an external app."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get external app tags",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "user_id": user.identity.get_id(),
            },
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id, resource_type="external_app", resource_id=external_app_id, use_cache=use_cache
        )
    except Exception as e:
        logger.error("Failed to get external app tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get external app tags")


@external_app_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set external app tags",
    description="Set tags for an external app (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def set_external_app_tags(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for an external app."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set external app tags",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags,
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="external_app",
            resource_id=external_app_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error("Failed to set external app tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set external app tags")


@external_app_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete external app tags",
    description="Remove all tags from an external app",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def delete_external_app_tags(
    request: Request, tenant_id: str, external_app_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from an external app."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete external app tags",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "user_id": user.identity.get_id(),
            },
        )

        handler.delete_resource_tags(tenant_id=tenant_id, resource_type="external_app", resource_id=external_app_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error("Failed to delete external app tags: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete external app tags"
        )


# ========== Tenant AI Model Tags List Router ==========

ai_models_tags_list_router = APIRouter(prefix="/ai-models/tags")


@ai_models_tags_list_router.get(
    "",
    response_model=list[TagSummary],
    summary="List tags for AI models",
    description="Get all tags that are applied to tenant AI models",
)
@authenticate()
async def list_ai_model_tags(
    request: Request,
    tenant_id: str,
    name: str | None = Query(None, description="Filter by tag name"),
    skip: int = Query(0, ge=0, description="Number of tags to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagSummary]:
    """List all tags that are applied to tenant AI models."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List tags for AI models",
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
            resource_type="tenant_ai_model",
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
        logger.error("Failed to list AI model tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list AI model tags")


# ========== Tenant AI Model Tag Endpoints ==========

ai_model_tags_router = APIRouter(prefix="/ai-models/{tenant_ai_model_id}/tags")


@ai_model_tags_router.get(
    "",
    response_model=list[TagResponse],
    summary="Get AI model tags",
    description="Get tags for a tenant AI model",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ],
)
async def get_ai_model_tags(
    request: Request, tenant_id: str, tenant_ai_model_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> list[TagResponse]:
    """Get tags for a tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: Get AI model tags",
            extra={
                "tenant_id": tenant_id,
                "tenant_ai_model_id": tenant_ai_model_id,
                "user_id": user.identity.get_id(),
            },
        )

        return handler.get_resource_tags(
            tenant_id=tenant_id,
            resource_type="tenant_ai_model",
            resource_id=tenant_ai_model_id,
            use_cache=use_cache,
        )
    except Exception as e:
        logger.error("Failed to get AI model tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get AI model tags")


@ai_model_tags_router.put(
    "",
    response_model=list[TagResponse],
    summary="Set AI model tags",
    description="Set tags for a tenant AI model (replaces existing tags)",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ],
)
async def set_ai_model_tags(
    request: Request,
    tenant_id: str,
    tenant_ai_model_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler),
) -> list[TagResponse]:
    """Set tags for a tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Set AI model tags",
            extra={
                "tenant_id": tenant_id,
                "tenant_ai_model_id": tenant_ai_model_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags,
            },
        )

        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="tenant_ai_model",
            resource_id=tenant_ai_model_id,
            tag_names=tags_request.tags,
            user=user,
        )
    except Exception as e:
        logger.error("Failed to set AI model tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set AI model tags")


@ai_model_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete AI model tags",
    description="Remove all tags from a tenant AI model",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ],
)
async def delete_ai_model_tags(
    request: Request, tenant_id: str, tenant_ai_model_id: str, handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: Delete AI model tags",
            extra={
                "tenant_id": tenant_id,
                "tenant_ai_model_id": tenant_ai_model_id,
                "user_id": user.identity.get_id(),
            },
        )

        handler.delete_resource_tags(
            tenant_id=tenant_id, resource_type="tenant_ai_model", resource_id=tenant_ai_model_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error("Failed to delete AI model tags: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete AI model tags")
