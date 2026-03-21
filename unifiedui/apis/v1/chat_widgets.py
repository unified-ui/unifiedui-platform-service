"""API routes for chat widget management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import ListViewEnum, OrderDirectionEnum, PermissionActionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.chat_widgets import ChatWidgetNotFoundError
from unifiedui.handlers.chat_widgets import ChatWidgetHandler
from unifiedui.handlers.dependencies import get_chat_widget_handler
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.logger import get_logger
from unifiedui.schema.requests.chat_widgets import CreateChatWidgetRequest, UpdateChatWidgetRequest
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
from unifiedui.schema.responses.chat_widgets import ChatWidgetResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/chat-widgets")


@router.get(
    "",
    summary="List chat widgets",
    description="Get a paginated list of chat widgets for the current tenant. Use view=quick-list to get only id and name.",
)
@authenticate()
async def list_chat_widgets(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by chat widget name"),
    is_active: int | None = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    tags: str | None = Query(
        None, description="Comma-separated list of tag IDs to filter by (e.g., '10001,10002,10003')"
    ),
    order_by: str | None = Query(
        None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    view: ListViewEnum | None = Query(
        None, description="View type: 'full' (default) or 'quick-list' (returns only id and name)"
    ),
    ids: str | None = Query(None, description="Comma-separated list of IDs to filter by"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
):
    """
    List chat widgets for a tenant.

    Users see only chat widgets they have permissions for, unless they have
    TENANT_GLOBAL_ADMIN or CHAT_WIDGETS_ADMIN on tenant level.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name: Optional filter by chat widget name
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
                    detail="Invalid tag IDs format. Must be comma-separated integers.",
                )

        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: List chat widgets",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "skip": skip, "limit": limit},
        )

        return filtered_response(
            handler.list_chat_widgets(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                name_filter=name,
                is_active=is_active,
                user=user,
                tag_ids=tag_ids,
                order_by=order_by,
                order_direction=order_direction.value if order_direction else None,
                view=view.value if view else None,
                id_list=parse_ids(ids),
            ),
            fields,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list chat widgets: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat widgets")


@router.post(
    "",
    response_model=ChatWidgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chat widget",
    description="Create a new chat widget",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_CREATOR,
    ],
)
async def create_chat_widget(
    request: Request,
    tenant_id: str,
    create_request: CreateChatWidgetRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
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
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "cw_name": create_request.name},
        )
        return handler.create_chat_widget(
            tenant_id=tenant_id, request=create_request, user_id=user.identity.get_id(), user=user
        )
    except Exception as e:
        logger.error("Failed to create chat widget: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create chat widget: {e!s}"
        )


@router.get(
    "/{chat_widget_id}",
    response_model=ChatWidgetResponse,
    summary="Get chat widget",
    description="Get a specific chat widget by ID",
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
async def get_chat_widget(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
):
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
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "user_id": user.identity.get_id()},
        )
        return filtered_response(
            handler.get_chat_widget(tenant_id=tenant_id, chat_widget_id=chat_widget_id, user=user),
            fields,
        )
    except ChatWidgetNotFoundError as e:
        logger.warning("Chat widget not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get chat widget: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat widget")


@router.patch(
    "/{chat_widget_id}",
    response_model=ChatWidgetResponse,
    summary="Update chat widget",
    description="Update an existing chat widget",
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
async def update_chat_widget(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    update_request: UpdateChatWidgetRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
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
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "user_id": user.identity.get_id()},
        )
        return handler.update_chat_widget(
            tenant_id=tenant_id, chat_widget_id=chat_widget_id, request=update_request, user_id=user.identity.get_id()
        )
    except ChatWidgetNotFoundError as e:
        logger.warning("Chat widget not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to update chat widget: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update chat widget: {e!s}"
        )


@router.delete(
    "/{chat_widget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat widget",
    description="Delete a chat widget",
)
@authenticate()
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_chat_widget(
    request: Request, tenant_id: str, chat_widget_id: str, handler: ChatWidgetHandler = Depends(get_chat_widget_handler)
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
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "user_id": user.identity.get_id()},
        )
        handler.delete_chat_widget(tenant_id=tenant_id, chat_widget_id=chat_widget_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ChatWidgetNotFoundError as e:
        logger.warning("Chat widget not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete chat widget: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat widget")


# ========== Chat Widget Permission Endpoints ==========


@router.get(
    "/{chat_widget_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List chat widget permissions",
    description="Get all principals with permissions for a chat widget",
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
async def list_chat_widget_permissions(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
) -> ResourcePrincipalsResponse:
    """
    List all permissions for a chat widget.

    Requires ADMIN permission on the chat widget or CHAT_WIDGETS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_widget_id: Chat widget ID from path
        skip: Number of principals to skip
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated roles to filter by (OR logic)
        is_active: Filter by is_active status
        order_by: Column to order by
        order_direction: Sort direction
        handler: Chat widget handler dependency

    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List chat widget permissions",
            extra={"tenant_id": tenant_id, "chat_widget_id": chat_widget_id, "user_id": user.identity.get_id()},
        )

        # Parse comma-separated roles
        roles_list = [r.strip() for r in roles.split(",")] if roles else None

        return handler.list_chat_widget_permissions(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction,
        )
    except ChatWidgetNotFoundError as e:
        logger.warning("Chat widget not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to list chat widget permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat widget permissions"
        )


@router.get(
    "/{chat_widget_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get chat widget permissions for principal",
    description="Get all permissions for a specific principal on a chat widget",
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
async def get_chat_widget_permission(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    principal_id: str,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
) -> PrincipalWithRolesResponse:
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
                "user_id": user.identity.get_id(),
            },
        )
        return handler.get_chat_widget_permission(
            tenant_id=tenant_id, chat_widget_id=chat_widget_id, principal_id=principal_id
        )
    except ChatWidgetNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get chat widget permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat widget permission"
        )


@router.put(
    "/{chat_widget_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set chat widget permission",
    description="Set or update a principal's permission for a chat widget",
)
@authenticate()
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def set_chat_widget_permission(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    permission_request: SetResourcePermissionRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
) -> PrincipalWithRolesResponse:
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
                "user_id": user.identity.get_id(),
            },
        )
        return handler.set_chat_widget_permission(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id,
            request=permission_request,
            user_id=user.identity.get_id(),
            user=user,
        )
    except ChatWidgetNotFoundError as e:
        logger.warning("Chat widget not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to set chat widget permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to set chat widget permission: {e!s}"
        )


@router.delete(
    "/{chat_widget_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat widget permission",
    description="Remove a principal's permission for a chat widget",
)
@authenticate()
@check_permissions(
    entity="chat_widget",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_chat_widget_permission(
    request: Request,
    tenant_id: str,
    chat_widget_id: str,
    delete_request: SetResourcePermissionRequest,
    handler: ChatWidgetHandler = Depends(get_chat_widget_handler),
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
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_chat_widget_permission(
            tenant_id=tenant_id,
            chat_widget_id=chat_widget_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            permission=delete_request.role.value,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ChatWidgetNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete chat widget permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat widget permission"
        )
