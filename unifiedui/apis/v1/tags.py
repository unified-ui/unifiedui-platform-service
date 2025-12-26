"""API routes for tag management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import Response

from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.handlers.tags import TagHandler
from unifiedui.handlers.dependencies import get_tag_handler
from unifiedui.schema.requests.tags import CreateTagRequest, SetResourceTagsRequest
from unifiedui.schema.responses.tags import TagResponse, TagListResponse, ResourceTagsResponse
from unifiedui.exc.tags import TagNotFoundError, TagDeleteNotAllowedError
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.core.database.enums import TenantRolesEnum, PermissionActionEnum, UserPermissionEnum
from unifiedui.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tags")


# ========== Tenant Tag Endpoints ==========

@router.get(
    "",
    response_model=TagListResponse,
    summary="List tags",
    description="Get a list of tags for the current tenant"
)
@authenticate
async def list_tags(
    request: Request,
    tenant_id: str,
    name: Optional[str] = Query(None, description="Filter by tag name"),
    handler: TagHandler = Depends(get_tag_handler)
) -> TagListResponse:
    """
    List tags for a tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        name: Optional filter by tag name (disables caching when used)
        handler: Tag handler dependency
        
    Returns:
        List of tags with total count
    """
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"
        
        logger.info(
            "API: List tags",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "name_filter": name
            }
        )
        
        return handler.list_tags(
            tenant_id=tenant_id,
            name_filter=name,
            use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to list tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tags"
        )


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create a new tag. Any authenticated tenant member can create tags."
)
@authenticate
async def create_tag(
    request: Request,
    tenant_id: str,
    create_request: CreateTagRequest,
    handler: TagHandler = Depends(get_tag_handler)
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
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "tag_name": create_request.name
            }
        )
        
        return handler.create_tag(
            tenant_id=tenant_id,
            name=create_request.name,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to create tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tag"
        )


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag. Only GLOBAL_ADMIN or the tag creator can delete."
)
@authenticate
@check_permissions(
    entity="tag",
    required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, UserPermissionEnum.IS_CREATOR]
)
async def delete_tag(
    request: Request,
    tenant_id: str,
    tag_id: int,
    handler: TagHandler = Depends(get_tag_handler)
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
            "API: Delete tag",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "tag_id": tag_id
            }
        )
        
        handler.delete_tag(
            tenant_id=tenant_id,
            tag_id=tag_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except TagNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tag"
        )


# ========== Application Tag Endpoints ==========

application_tags_router = APIRouter(prefix="/applications/{application_id}/tags")


@application_tags_router.get(
    "",
    response_model=ResourceTagsResponse,
    summary="Get application tags",
    description="Get tags for an application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_application_tags(
    request: Request,
    tenant_id: str,
    application_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Get tags for an application."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"
        
        logger.info(
            "API: Get application tags",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id()
            }
        )
        
        return handler.get_resource_tags(
            tenant_id=tenant_id,
            resource_type="application",
            resource_id=application_id,
            use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get application tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get application tags"
        )


@application_tags_router.put(
    "",
    response_model=ResourceTagsResponse,
    summary="Set application tags",
    description="Set tags for an application (replaces existing tags)"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def set_application_tags(
    request: Request,
    tenant_id: str,
    application_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Set tags for an application."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Set application tags",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags
            }
        )
        
        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="application",
            resource_id=application_id,
            tag_names=tags_request.tags,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to set application tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set application tags"
        )


@application_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete application tags",
    description="Remove all tags from an application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def delete_application_tags(
    request: Request,
    tenant_id: str,
    application_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from an application."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Delete application tags",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id()
            }
        )
        
        handler.delete_resource_tags(
            tenant_id=tenant_id,
            resource_type="application",
            resource_id=application_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete application tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete application tags"
        )


# ========== Autonomous Agent Tag Endpoints ==========

autonomous_agent_tags_router = APIRouter(prefix="/autonomous-agents/{autonomous_agent_id}/tags")


@autonomous_agent_tags_router.get(
    "",
    response_model=ResourceTagsResponse,
    summary="Get autonomous agent tags",
    description="Get tags for an autonomous agent"
)
@authenticate
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_autonomous_agent_tags(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Get tags for an autonomous agent."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"
        
        logger.info(
            "API: Get autonomous agent tags",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "user_id": user.identity.get_id()
            }
        )
        
        return handler.get_resource_tags(
            tenant_id=tenant_id,
            resource_type="autonomous_agent",
            resource_id=autonomous_agent_id,
            use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get autonomous agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get autonomous agent tags"
        )


@autonomous_agent_tags_router.put(
    "",
    response_model=ResourceTagsResponse,
    summary="Set autonomous agent tags",
    description="Set tags for an autonomous agent (replaces existing tags)"
)
@authenticate
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def set_autonomous_agent_tags(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Set tags for an autonomous agent."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Set autonomous agent tags",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags
            }
        )
        
        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="autonomous_agent",
            resource_id=autonomous_agent_id,
            tag_names=tags_request.tags,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to set autonomous agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set autonomous agent tags"
        )


@autonomous_agent_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete autonomous agent tags",
    description="Remove all tags from an autonomous agent"
)
@authenticate
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def delete_autonomous_agent_tags(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from an autonomous agent."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Delete autonomous agent tags",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "user_id": user.identity.get_id()
            }
        )
        
        handler.delete_resource_tags(
            tenant_id=tenant_id,
            resource_type="autonomous_agent",
            resource_id=autonomous_agent_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete autonomous agent tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete autonomous agent tags"
        )


# ========== Chat Widget Tag Endpoints ==========

chat_widget_tags_router = APIRouter(prefix="/chat-widgets/{chat_widget_id}/tags")


@chat_widget_tags_router.get(
    "",
    response_model=ResourceTagsResponse,
    summary="Get chat widget tags",
    description="Get tags for a chat widget"
)
@authenticate
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_chat_widget_tags(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Get tags for a chat widget."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"
        
        logger.info(
            "API: Get chat widget tags",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id()
            }
        )
        
        return handler.get_resource_tags(
            tenant_id=tenant_id,
            resource_type="chat_widget",
            resource_id=chat_widget_id,
            use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get chat widget tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat widget tags"
        )


@chat_widget_tags_router.put(
    "",
    response_model=ResourceTagsResponse,
    summary="Set chat widget tags",
    description="Set tags for a chat widget (replaces existing tags)"
)
@authenticate
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def set_chat_widget_tags(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Set tags for a chat widget."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Set chat widget tags",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags
            }
        )
        
        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="chat_widget",
            resource_id=chat_widget_id,
            tag_names=tags_request.tags,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to set chat widget tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set chat widget tags"
        )


@chat_widget_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat widget tags",
    description="Remove all tags from a chat widget"
)
@authenticate
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def delete_chat_widget_tags(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a chat widget."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Delete chat widget tags",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id()
            }
        )
        
        handler.delete_resource_tags(
            tenant_id=tenant_id,
            resource_type="chat_widget",
            resource_id=chat_widget_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete chat widget tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat widget tags"
        )


# ========== Credential Tag Endpoints ==========

credential_tags_router = APIRouter(prefix="/credentials/{credential_id}/tags")


@credential_tags_router.get(
    "",
    response_model=ResourceTagsResponse,
    summary="Get credential tags",
    description="Get tags for a credential"
)
@authenticate
@check_permissions(
    entity="credential",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_credential_tags(
    request: Request,
    tenant_id: str,
    credential_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Get tags for a credential."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"
        
        logger.info(
            "API: Get credential tags",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id()
            }
        )
        
        return handler.get_resource_tags(
            tenant_id=tenant_id,
            resource_type="credential",
            resource_id=credential_id,
            use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get credential tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get credential tags"
        )


@credential_tags_router.put(
    "",
    response_model=ResourceTagsResponse,
    summary="Set credential tags",
    description="Set tags for a credential (replaces existing tags)"
)
@authenticate
@check_permissions(
    entity="credential",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def set_credential_tags(
    request: Request,
    tenant_id: str,
    credential_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Set tags for a credential."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Set credential tags",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags
            }
        )
        
        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="credential",
            resource_id=credential_id,
            tag_names=tags_request.tags,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to set credential tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set credential tags"
        )


@credential_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credential tags",
    description="Remove all tags from a credential"
)
@authenticate
@check_permissions(
    entity="credential",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def delete_credential_tags(
    request: Request,
    tenant_id: str,
    credential_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a credential."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Delete credential tags",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id()
            }
        )
        
        handler.delete_resource_tags(
            tenant_id=tenant_id,
            resource_type="credential",
            resource_id=credential_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete credential tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete credential tags"
        )


# ========== Development Platform Tag Endpoints ==========

development_platform_tags_router = APIRouter(prefix="/development-platforms/{development_platform_id}/tags")


@development_platform_tags_router.get(
    "",
    response_model=ResourceTagsResponse,
    summary="Get development platform tags",
    description="Get tags for a development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_development_platform_tags(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Get tags for a development platform."""
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"
        
        logger.info(
            "API: Get development platform tags",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "user_id": user.identity.get_id()
            }
        )
        
        return handler.get_resource_tags(
            tenant_id=tenant_id,
            resource_type="development_platform",
            resource_id=development_platform_id,
            use_cache=use_cache
        )
    except Exception as e:
        logger.error(f"Failed to get development platform tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get development platform tags"
        )


@development_platform_tags_router.put(
    "",
    response_model=ResourceTagsResponse,
    summary="Set development platform tags",
    description="Set tags for a development platform (replaces existing tags)"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def set_development_platform_tags(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    tags_request: SetResourceTagsRequest,
    handler: TagHandler = Depends(get_tag_handler)
) -> ResourceTagsResponse:
    """Set tags for a development platform."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Set development platform tags",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "user_id": user.identity.get_id(),
                "tags": tags_request.tags
            }
        )
        
        return handler.set_resource_tags(
            tenant_id=tenant_id,
            resource_type="development_platform",
            resource_id=development_platform_id,
            tag_names=tags_request.tags,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to set development platform tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set development platform tags"
        )


@development_platform_tags_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete development platform tags",
    description="Remove all tags from a development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def delete_development_platform_tags(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    handler: TagHandler = Depends(get_tag_handler)
) -> Response:
    """Remove all tags from a development platform."""
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: Delete development platform tags",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "user_id": user.identity.get_id()
            }
        )
        
        handler.delete_resource_tags(
            tenant_id=tenant_id,
            resource_type="development_platform",
            resource_id=development_platform_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Failed to delete development platform tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete development platform tags"
        )
