"""API routes for chat widget management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import Response

from aihub.core.identity.users import ContextIdentityUser
from aihub.handlers.chat_widgets import ChatWidgetHandler
from aihub.handlers.dependencies import get_chat_widget_handler
from aihub.schema.requests.chat_widgets import CreateChatWidgetRequest, UpdateChatWidgetRequest
from aihub.schema.requests.chat_widget_permissions import SetChatWidgetPermissionRequest
from aihub.schema.responses.chat_widgets import ChatWidgetResponse
from aihub.schema.responses.chat_widget_permissions import (
    ChatWidgetPermissionResponse,
    ChatWidgetPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.chat_widgets import ChatWidgetNotFoundError
from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.database.enums import TenantRolesEnum, PermissionActionEnum, OrderDirectionEnum
from aihub.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/chat-widgets"
)


@router.get(
    "",
    response_model=List[ChatWidgetResponse],
    summary="List chat widgets",
    description="Get a paginated list of chat widgets for the current tenant"
)
@authenticate
async def list_chat_widgets(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name_filter: Optional[str] = Query(None, description="Filter by chat widget name"),
    is_active: Optional[int] = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tag IDs to filter by (e.g., '10001,10002,10003')"),
    order_by: Optional[str] = Query(None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"),
    order_direction: Optional[OrderDirectionEnum] = Query(None, description="Sort direction: 'asc' or 'desc'"),
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> List[ChatWidgetResponse]:
    """
    List chat widgets for a tenant.
    
    Users see only chat widgets they have permissions for, unless they have
    GLOBAL_ADMIN or CHAT_WIDGETS_ADMIN on tenant level.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name_filter: Optional filter by chat widget name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        tags: Optional comma-separated tag IDs to filter by
        handler: Chat widget handler dependency
        
    Returns:
        List of chat widgets
    """
    try:
        # Parse tag IDs from comma-separated string
        tag_ids = None
        if tags:
            try:
                tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tag IDs format. Must be comma-separated integers."
                )
        
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: List chat widgets",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit
            }
        )
        
        return handler.list_chat_widgets(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name_filter,
            is_active=is_active,
            user=user,
            tag_ids=tag_ids,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list chat widgets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list chat widgets"
        )


@router.post(
    "",
    response_model=ChatWidgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chat widget",
    description="Create a new chat widget"
)
@authenticate
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_CREATOR
    ]
)
async def create_chat_widget(
    request: Request,
    tenant_id: str,
    create_request: CreateChatWidgetRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> ChatWidgetResponse:
    """
    Create a new chat widget.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Chat widget creation data
        handler: Chat widget handler dependency
        
    Returns:
        Created chat widget
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create chat widget",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "cw_name": create_request.name
            }
        )
        return handler.create_chat_widget(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id()
        )
    except Exception as e:
        logger.error(f"Failed to create chat widget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat widget: {str(e)}"
        )


@router.get(
    "/{chat_widget_id}",
    response_model=ChatWidgetResponse,
    summary="Get chat widget",
    description="Get a specific chat widget by ID"
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
async def get_chat_widget(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> ChatWidgetResponse:
    """
    Get a specific chat widget.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        handler: Chat widget handler dependency
        
    Returns:
        Chat widget details
        
    Raises:
        HTTPException: If chat widget not found or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get chat widget",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_chat_widget(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id
        )
    except ChatWidgetNotFoundError as e:
        logger.warning(f"Chat widget not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get chat widget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat widget"
        )


@router.patch(
    "/{chat_widget_id}",
    response_model=ChatWidgetResponse,
    summary="Update chat widget",
    description="Update an existing chat widget"
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
async def update_chat_widget(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    update_request: UpdateChatWidgetRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> ChatWidgetResponse:
    """
    Update a chat widget.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        update_request: Chat widget update data
        handler: Chat widget handler dependency
        
    Returns:
        Updated chat widget
        
    Raises:
        HTTPException: If chat widget not found or update fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update chat widget",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.update_chat_widget(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id,
            request=update_request,
            user_id=user.identity.get_id()
        )
    except ChatWidgetNotFoundError as e:
        logger.warning(f"Chat widget not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update chat widget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update chat widget: {str(e)}"
        )


@router.delete(
    "/{chat_widget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat widget",
    description="Delete a chat widget"
)
@authenticate
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_chat_widget(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> Response:
    """
    Delete a chat widget.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        handler: Chat widget handler dependency
        
    Returns:
        No content (204)
        
    Raises:
        HTTPException: If chat widget not found or deletion fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete chat widget",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_chat_widget(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ChatWidgetNotFoundError as e:
        logger.warning(f"Chat widget not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete chat widget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat widget"
        )


# ========== Chat Widget Permission Endpoints ==========

@router.get(
    "/{chat_widget_id}/principals",
    response_model=ChatWidgetPrincipalsResponse,
    summary="List chat widget permissions",
    description="Get all principals with permissions for a chat widget"
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
async def list_chat_widget_permissions(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> ChatWidgetPrincipalsResponse:
    """
    List all permissions for a chat widget.
    
    Requires ADMIN permission on the chat widget or CHAT_WIDGETS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        handler: Chat widget handler dependency
        
    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List chat widget permissions",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.list_chat_widget_permissions(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id
        )
    except ChatWidgetNotFoundError as e:
        logger.warning(f"Chat widget not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list chat widget permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list chat widget permissions"
        )


@router.get(
    "/{chat_widget_id}/principals/{principal_id}",
    response_model=PrincipalPermissionsResponse,
    summary="Get chat widget permissions for principal",
    description="Get all permissions for a specific principal on a chat widget"
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
async def get_chat_widget_permission(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    principal_id: str,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> PrincipalPermissionsResponse:
    """
    Get all permissions for a specific principal on a chat widget.
    
    Requires ADMIN permission on the chat widget or CHAT_WIDGETS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        principal_id: Principal ID from path
        handler: Chat widget handler dependency
        
    Returns:
        Principal with all their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get chat widget permission",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_chat_widget_permission(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id,
            principal_id=principal_id
        )
    except ChatWidgetNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get chat widget permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat widget permission"
        )


@router.put(
    "/{chat_widget_id}/principals",
    response_model=ChatWidgetPermissionResponse,
    summary="Set chat widget permission",
    description="Set or update a principal's permission for a chat widget"
)
@authenticate
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def set_chat_widget_permission(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    permission_request: SetChatWidgetPermissionRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> ChatWidgetPermissionResponse:
    """
    Set or update a chat widget permission.
    
    Requires ADMIN permission on the chat widget or CHAT_WIDGETS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        permission_request: Permission data
        handler: Chat widget handler dependency
        
    Returns:
        Created or updated permission
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set chat widget permission",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "principal_id": permission_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.set_chat_widget_permission(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id,
            request=permission_request,
            user_id=user.identity.get_id()
        )
    except ChatWidgetNotFoundError as e:
        logger.warning(f"Chat widget not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set chat widget permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set chat widget permission: {str(e)}"
        )


@router.delete(
    "/{chat_widget_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat widget permission",
    description="Remove a principal's permission for a chat widget"
)
@authenticate
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_chat_widget_permission(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    delete_request: SetChatWidgetPermissionRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
) -> Response:
    """
    Delete a chat widget permission.
    
    Requires ADMIN permission on the chat widget or CHAT_WIDGETS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        delete_request: Permission deletion data (principal_id, principal_type, permission)
        handler: Chat widget handler dependency
        
    Returns:
        No content (204)
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete chat widget permission",
            extra={
                "tenant_id": tenant_id,
                "chat_widget_id": chat_widget_id,
                "principal_id": delete_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_chat_widget_permission(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            permission=delete_request.role.value
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ChatWidgetNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete chat widget permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat widget permission"
        )
