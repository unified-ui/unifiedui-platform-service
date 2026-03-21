"""API routes for conversation management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import ListViewEnum, OrderDirectionEnum, PermissionActionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.conversations import ConversationNotFoundError, FoundryConversationCreationError
from unifiedui.handlers.conversations import ConversationHandler
from unifiedui.handlers.dependencies import get_conversation_handler
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.logger import get_logger
from unifiedui.schema.requests.conversations import CreateConversationRequest, UpdateConversationRequest
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
from unifiedui.schema.responses.conversations import ConversationResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations")


@router.get(
    "",
    summary="List conversations",
    description="Get a paginated list of conversations for the current tenant. Use view=quick-list to get only id and name.",
)
@authenticate()
async def list_conversations(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by conversation name"),
    is_active: int | None = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    order_by: str | None = Query(
        None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    view: ListViewEnum | None = Query(
        None, description="View type: 'full' (default) or 'quick-list' (returns only id and name)"
    ),
    ids: str | None = Query(None, description="Comma-separated list of IDs to filter by"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ConversationHandler = Depends(get_conversation_handler),
):
    """
    List conversations for a tenant.

    Users see only conversations they have permissions for, unless they have
    TENANT_GLOBAL_ADMIN or CONVERSATIONS_ADMIN on tenant level.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name: Optional filter by conversation name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        handler: Conversation handler dependency

    Returns:
        List of conversations
    """
    try:
        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: List conversations",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "skip": skip, "limit": limit},
        )

        return filtered_response(
            handler.list_conversations(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                name_filter=name,
                is_active=is_active,
                order_by=order_by,
                order_direction=order_direction.value if order_direction else None,
                view=view.value if view else None,
                user=user,
                id_list=parse_ids(ids),
            ),
            fields,
        )
    except Exception as e:
        logger.error("Failed to list conversations: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list conversations")


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create conversation",
    description="Create a new conversation. For MICROSOFT_FOUNDRY chat agents, include the X-Microsoft-Foundry-API-Key header.",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        TenantRolesEnum.CONVERSATIONS_CREATOR,
    ],
)
async def create_conversation(
    request: Request,
    tenant_id: str,
    create_request: CreateConversationRequest,
    handler: ConversationHandler = Depends(get_conversation_handler),
    x_microsoft_foundry_api_key: str | None = Header(None, alias="X-Microsoft-Foundry-API-Key"),
) -> ConversationResponse:
    """
    Create a new conversation.

    For MICROSOFT_FOUNDRY chat agents, a conversation will also be created in the
    Foundry service. The X-Microsoft-Foundry-API-Key header is required for these chat agents.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Conversation creation data
        handler: Conversation handler dependency
        x_microsoft_foundry_api_key: Optional API key for Microsoft Foundry

    Returns:
        Created conversation
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create conversation",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "conversation_name": create_request.name},
        )
        return handler.create_conversation(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id(),
            user=user,
            foundry_api_key=x_microsoft_foundry_api_key,
        )
    except FoundryConversationCreationError as e:
        logger.error("Failed to create Foundry conversation: %s", e)
        raise HTTPException(status_code=e.status_code or status.HTTP_502_BAD_GATEWAY, detail=e.message)
    except Exception as e:
        logger.error("Failed to create conversation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create conversation: {e!s}"
        )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation",
    description="Get a specific conversation by ID",
)
@authenticate()
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_conversation(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ConversationHandler = Depends(get_conversation_handler),
):
    """
    Get a specific conversation.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        handler: Conversation handler dependency

    Returns:
        Conversation details

    Raises:
        HTTPException: If conversation not found or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get conversation",
            extra={"tenant_id": tenant_id, "conversation_id": conversation_id, "user_id": user.identity.get_id()},
        )
        return filtered_response(
            handler.get_conversation(tenant_id=tenant_id, conversation_id=conversation_id, user=user),
            fields,
        )
    except ConversationNotFoundError as e:
        logger.warning("Conversation not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get conversation: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get conversation")


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation",
    description="Update an existing conversation",
)
@authenticate()
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def update_conversation(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    update_request: UpdateConversationRequest,
    handler: ConversationHandler = Depends(get_conversation_handler),
) -> ConversationResponse:
    """
    Update a conversation.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        update_request: Conversation update data
        handler: Conversation handler dependency

    Returns:
        Updated conversation

    Raises:
        HTTPException: If conversation not found or update fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update conversation",
            extra={"tenant_id": tenant_id, "conversation_id": conversation_id, "user_id": user.identity.get_id()},
        )
        return handler.update_conversation(
            tenant_id=tenant_id, conversation_id=conversation_id, request=update_request, user_id=user.identity.get_id()
        )
    except ConversationNotFoundError as e:
        logger.warning("Conversation not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to update conversation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update conversation: {e!s}"
        )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
    description="Delete a conversation",
)
@authenticate()
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_conversation(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    handler: ConversationHandler = Depends(get_conversation_handler),
) -> Response:
    """
    Delete a conversation.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        handler: Conversation handler dependency

    Returns:
        No content (204)

    Raises:
        HTTPException: If conversation not found or deletion fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete conversation",
            extra={"tenant_id": tenant_id, "conversation_id": conversation_id, "user_id": user.identity.get_id()},
        )
        handler.delete_conversation(tenant_id=tenant_id, conversation_id=conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConversationNotFoundError as e:
        logger.warning("Conversation not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete conversation: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete conversation")


# ========== Conversation Permission Endpoints ==========


@router.get(
    "/{conversation_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List conversation permissions",
    description="Get all principals with permissions for a conversation",
)
@authenticate()
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def list_conversation_permissions(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: ConversationHandler = Depends(get_conversation_handler),
) -> ResourcePrincipalsResponse:
    """
    List all permissions for a conversation.

    Requires ADMIN permission on the conversation or CONVERSATIONS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        skip: Number of principals to skip
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated roles to filter by (OR logic)
        is_active: Filter by is_active status
        order_by: Column to order by
        order_direction: Sort direction
        handler: Conversation handler dependency

    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List conversation permissions",
            extra={"tenant_id": tenant_id, "conversation_id": conversation_id, "user_id": user.identity.get_id()},
        )

        # Parse comma-separated roles
        roles_list = [r.strip() for r in roles.split(",")] if roles else None

        return handler.list_conversation_permissions(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction,
        )
    except ConversationNotFoundError as e:
        logger.warning("Conversation not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to list conversation permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list conversation permissions"
        )


@router.get(
    "/{conversation_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get conversation permissions for principal",
    description="Get all permissions for a specific principal on a conversation",
)
@authenticate()
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_conversation_permission(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    principal_id: str,
    handler: ConversationHandler = Depends(get_conversation_handler),
) -> PrincipalWithRolesResponse:
    """
    Get all permissions for a specific principal on a conversation.

    Requires ADMIN permission on the conversation or CONVERSATIONS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        principal_id: Principal ID from path
        handler: Conversation handler dependency

    Returns:
        Principal with all their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get conversation permission",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.get_conversation_permission(
            tenant_id=tenant_id, conversation_id=conversation_id, principal_id=principal_id
        )
    except ConversationNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get conversation permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get conversation permission"
        )


@router.put(
    "/{conversation_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set conversation permission",
    description="Set or update a principal's permission for a conversation",
)
@authenticate()
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def set_conversation_permission(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    permission_request: SetResourcePermissionRequest,
    handler: ConversationHandler = Depends(get_conversation_handler),
) -> PrincipalWithRolesResponse:
    """
    Set or update a conversation permission.

    Requires ADMIN permission on the conversation or CONVERSATIONS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        permission_request: Permission data
        handler: Conversation handler dependency

    Returns:
        Created or updated permission
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set conversation permission",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "principal_id": permission_request.principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.set_conversation_permission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request=permission_request,
            user_id=user.identity.get_id(),
            user=user,
        )
    except ConversationNotFoundError as e:
        logger.warning("Conversation not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to set conversation permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to set conversation permission: {e!s}"
        )


@router.delete(
    "/{conversation_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation permission",
    description="Remove a principal's permission for a conversation",
)
@authenticate()
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_conversation_permission(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    delete_request: SetResourcePermissionRequest,
    handler: ConversationHandler = Depends(get_conversation_handler),
) -> Response:
    """
    Delete a conversation permission.

    Requires ADMIN permission on the conversation or CONVERSATIONS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        delete_request: Permission deletion data (principal_id, principal_type, permission)
        handler: Conversation handler dependency

    Returns:
        No content (204)
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete conversation permission",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "principal_id": delete_request.principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_conversation_permission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            role=delete_request.role.value,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConversationNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete conversation permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete conversation permission"
        )
