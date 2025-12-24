"""API routes for conversation management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response

from aihub.core.identity.users import ContextIdentityUser
from aihub.handlers.conversations import ConversationHandler
from aihub.handlers.dependencies import get_conversation_handler
from aihub.schema.requests.conversations import CreateConversationRequest, UpdateConversationRequest
from aihub.schema.requests.conversation_permissions import SetConversationPermissionRequest
from aihub.schema.responses.conversations import ConversationResponse
from aihub.schema.responses.conversation_permissions import (
    ConversationPermissionResponse,
    ConversationPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.conversations import ConversationNotFoundError
from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.database.enums import TenantRolesEnum, PermissionActionEnum
from aihub.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/conversations"
)


@router.get(
    "",
    response_model=List[ConversationResponse],
    summary="List conversations",
    description="Get a paginated list of conversations for the current tenant"
)
@authenticate
async def list_conversations(
    request: Request,
    tenant_id: str,
    skip: int = 0,
    limit: int = 100,
    name_filter: Optional[str] = None,
    is_active: Optional[int] = None,
    handler: ConversationHandler = Depends(get_conversation_handler)
) -> List[ConversationResponse]:
    """
    List conversations for a tenant.
    
    Users see only conversations they have permissions for, unless they have
    GLOBAL_ADMIN or CONVERSATIONS_ADMIN on tenant level.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name_filter: Optional filter by conversation name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        handler: Conversation handler dependency
        
    Returns:
        List of conversations
    """
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: List conversations",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit
            }
        )
        
        return handler.list_conversations(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name_filter,
            is_active=is_active,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations"
        )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create conversation",
    description="Create a new conversation"
)
@authenticate
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        TenantRolesEnum.CONVERSATIONS_CREATOR
    ]
)
async def create_conversation(
    request: Request,
    tenant_id: str,
    create_request: CreateConversationRequest,
    handler: ConversationHandler = Depends(get_conversation_handler)
) -> ConversationResponse:
    """
    Create a new conversation.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Conversation creation data
        handler: Conversation handler dependency
        
    Returns:
        Created conversation
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create conversation",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "conversation_name": create_request.name
            }
        )
        return handler.create_conversation(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id()
        )
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}"
        )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation",
    description="Get a specific conversation by ID"
)
@authenticate
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_conversation(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    handler: ConversationHandler = Depends(get_conversation_handler)
) -> ConversationResponse:
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
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id
        )
    except ConversationNotFoundError as e:
        logger.warning(f"Conversation not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation"
        )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation",
    description="Update an existing conversation"
)
@authenticate
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def update_conversation(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    update_request: UpdateConversationRequest,
    handler: ConversationHandler = Depends(get_conversation_handler)
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
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.update_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request=update_request,
            user_id=user.identity.get_id()
        )
    except ConversationNotFoundError as e:
        logger.warning(f"Conversation not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update conversation: {str(e)}"
        )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
    description="Delete a conversation"
)
@authenticate
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_conversation(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    handler: ConversationHandler = Depends(get_conversation_handler)
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
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConversationNotFoundError as e:
        logger.warning(f"Conversation not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )


# ========== Conversation Permission Endpoints ==========

@router.get(
    "/{conversation_id}/principals",
    response_model=ConversationPrincipalsResponse,
    summary="List conversation permissions",
    description="Get all principals with permissions for a conversation"
)
@authenticate
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def list_conversation_permissions(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    handler: ConversationHandler = Depends(get_conversation_handler)
) -> ConversationPrincipalsResponse:
    """
    List all permissions for a conversation.
    
    Requires ADMIN permission on the conversation or CONVERSATIONS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        conversation_id: Conversation ID from path
        handler: Conversation handler dependency
        
    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List conversation permissions",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.list_conversation_permissions(
            tenant_id=tenant_id,
            conversation_id=conversation_id
        )
    except ConversationNotFoundError as e:
        logger.warning(f"Conversation not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list conversation permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversation permissions"
        )


@router.get(
    "/{conversation_id}/principals/{principal_id}",
    response_model=PrincipalPermissionsResponse,
    summary="Get conversation permissions for principal",
    description="Get all permissions for a specific principal on a conversation"
)
@authenticate
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_conversation_permission(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    principal_id: str,
    handler: ConversationHandler = Depends(get_conversation_handler)
) -> PrincipalPermissionsResponse:
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
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_conversation_permission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            principal_id=principal_id
        )
    except ConversationNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get conversation permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation permission"
        )


@router.put(
    "/{conversation_id}/principals",
    response_model=ConversationPermissionResponse,
    summary="Set conversation permission",
    description="Set or update a principal's permission for a conversation"
)
@authenticate
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def set_conversation_permission(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    permission_request: SetConversationPermissionRequest,
    handler: ConversationHandler = Depends(get_conversation_handler)
) -> ConversationPermissionResponse:
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
                "user_id": user.identity.get_id()
            }
        )
        return handler.set_conversation_permission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request=permission_request,
            user_id=user.identity.get_id()
        )
    except ConversationNotFoundError as e:
        logger.warning(f"Conversation not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set conversation permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set conversation permission: {str(e)}"
        )


@router.delete(
    "/{conversation_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation permission",
    description="Remove a principal's permission for a conversation"
)
@authenticate
@check_permissions(
    entity="conversation",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.CONVERSATIONS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_conversation_permission(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    delete_request: SetConversationPermissionRequest,
    handler: ConversationHandler = Depends(get_conversation_handler)
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
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_conversation_permission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            role=delete_request.role.value
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConversationNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete conversation permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation permission"
        )
