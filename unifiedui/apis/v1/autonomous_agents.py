"""API routes for autonomous agent management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import Response

from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.handlers.autonomous_agents import AutonomousAgentHandler
from unifiedui.handlers.dependencies import get_autonomous_agent_handler, get_credential_handler
from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.schema.requests.autonomous_agents import CreateAutonomousAgentRequest, UpdateAutonomousAgentRequest
from unifiedui.schema.requests.autonomous_agent_permissions import SetAutonomousAgentPermissionRequest
from unifiedui.schema.responses.autonomous_agents import (
    AutonomousAgentResponse, 
    AutonomousAgentKeyResponse,
    AutonomousAgentConfigResponse
)
from unifiedui.schema.responses.principals import (
    PrincipalWithRolesResponse,
    ResourcePrincipalsResponse
)
from unifiedui.exc.autonomous_agents import (
    AutonomousAgentNotFoundError, 
    AutonomousAgentPermissionNotFoundError,
    AutonomousAgentConfigValidationError,
    UnsupportedAutonomousAgentTypeError,
    AutonomousAgentKeyNotFoundError
)
from unifiedui.exc.application_config import InvalidCredentialError
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions, authenticate_autonomous_agent_api_key
from unifiedui.core.database.enums import TenantRolesEnum, PermissionActionEnum, OrderDirectionEnum, ListViewEnum
from unifiedui.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/autonomous-agents"
)


@router.get(
    "",
    summary="List autonomous agents",
    description="Get a paginated list of autonomous agents for the current tenant. Use view=quick-list to get only id and name."
)
@authenticate()
async def list_autonomous_agents(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: Optional[str] = Query(None, description="Filter by autonomous agent name"),
    is_active: Optional[int] = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tag IDs to filter by (e.g., '10001,10002,10003')"),
    order_by: Optional[str] = Query(None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"),
    order_direction: Optional[OrderDirectionEnum] = Query(None, description="Sort direction: 'asc' or 'desc'"),
    view: Optional[ListViewEnum] = Query(None, description="View type: 'full' (default) or 'quick-list' (returns only id and name)"),
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
):
    """
    List autonomous agents for a tenant.
    
    Users see only autonomous agents they have permissions for, unless they have
    GLOBAL_ADMIN or AUTONOMOUS_AGENTS_ADMIN on tenant level.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name: Optional filter by autonomous agent name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        tags: Optional comma-separated tag IDs to filter by
        handler: Autonomous agent handler dependency
        
    Returns:
        List of autonomous agents
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
        return handler.list_autonomous_agents(
            tenant_id=tenant_id,
            user=user,
            skip=skip,
            limit=limit,
            name_filter=name,
            is_active=is_active,
            tag_ids=tag_ids,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
            view=view.value if view else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list autonomous agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list autonomous agents"
        )


@router.post(
    "",
    response_model=AutonomousAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create autonomous agent",
    description="Create a new autonomous agent"
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_CREATOR
    ]
)
async def create_autonomous_agent(
    request: Request,
    tenant_id: str,
    create_request: CreateAutonomousAgentRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> AutonomousAgentResponse:
    """
    Create a new autonomous agent.
    
    Requires GLOBAL_ADMIN, AUTONOMOUS_AGENTS_ADMIN, or AUTONOMOUS_AGENTS_CREATOR permission on tenant level.
    Creator is automatically assigned ADMIN permission on the autonomous agent.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Autonomous agent creation data
        handler: Autonomous agent handler dependency
        
    Returns:
        Created autonomous agent
    """
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        
        return handler.create_autonomous_agent(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user_id,
            user=user
        )
    except AutonomousAgentConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except UnsupportedAutonomousAgentTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create autonomous agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create autonomous agent"
        )


@router.get(
    "/{autonomous_agent_id}",
    response_model=AutonomousAgentResponse,
    summary="Get autonomous agent",
    description="Get a specific autonomous agent by ID"
)
@authenticate()
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
async def get_autonomous_agent(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> AutonomousAgentResponse:
    """
    Get a specific autonomous agent by ID.
    
    Requires READ permission or higher on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        handler: Autonomous agent handler dependency
        
    Returns:
        Autonomous agent details
    """
    try:
        return handler.get_autonomous_agent(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get autonomous agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get autonomous agent"
        )


@router.patch(
    "/{autonomous_agent_id}",
    response_model=AutonomousAgentResponse,
    summary="Update autonomous agent",
    description="Update an existing autonomous agent"
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def update_autonomous_agent(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    update_request: UpdateAutonomousAgentRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> AutonomousAgentResponse:
    """
    Update an existing autonomous agent.
    
    Requires WRITE permission or higher on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        update_request: Autonomous agent update data
        handler: Autonomous agent handler dependency
        
    Returns:
        Updated autonomous agent
    """
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        
        return handler.update_autonomous_agent(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            request=update_request,
            user_id=user_id
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AutonomousAgentConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update autonomous agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update autonomous agent"
        )


@router.delete(
    "/{autonomous_agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete autonomous agent",
    description="Delete an autonomous agent"
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_autonomous_agent(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> Response:
    """
    Delete an autonomous agent.
    
    Requires WRITE permission or higher on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        handler: Autonomous agent handler dependency
        
    Returns:
        204 No Content on success
    """
    try:
        handler.delete_autonomous_agent(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete autonomous agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete autonomous agent"
        )


# ========== Autonomous Agent Permission Endpoints ==========

@router.get(
    "/{autonomous_agent_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List autonomous agent permissions",
    description="Get all principals with permissions for an autonomous agent"
)
@authenticate()
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
async def list_autonomous_agent_permissions(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: Optional[str] = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: Optional[str] = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: Optional[bool] = Query(None, description="Filter by is_active status"),
    order_by: Optional[str] = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: Optional[str] = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> ResourcePrincipalsResponse:
    """
    Get all principals with permissions for an autonomous agent.
    
    Requires READ permission or higher on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        skip: Number of principals to skip
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated roles to filter by (OR logic)
        is_active: Filter by is_active status
        order_by: Column to order by
        order_direction: Sort direction
        handler: Autonomous agent handler dependency
        
    Returns:
        List of principals with their permissions
    """
    try:
        # Parse comma-separated roles
        roles_list = [r.strip() for r in roles.split(",")] if roles else None
        
        return handler.list_autonomous_agent_permissions(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list autonomous agent permissions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list autonomous agent permissions"
        )


@router.get(
    "/{autonomous_agent_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get autonomous agent permissions for principal",
    description="Get all permissions for a specific principal on an autonomous agent"
)
@authenticate()
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
async def get_autonomous_agent_permission(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    principal_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> PrincipalWithRolesResponse:
    """
    Get all permissions for a specific principal on an autonomous agent.
    
    Requires READ permission or higher on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        principal_id: Principal ID from path
        handler: Autonomous agent handler dependency
        
    Returns:
        Principal's permissions on the autonomous agent
    """
    try:
        return handler.get_autonomous_agent_permission(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            principal_id=principal_id
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get autonomous agent permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get autonomous agent permission"
        )


@router.put(
    "/{autonomous_agent_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set autonomous agent permission",
    description="Set or update a principal's permission for an autonomous agent"
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def set_autonomous_agent_permission(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    permission_request: SetAutonomousAgentPermissionRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> PrincipalWithRolesResponse:
    """
    Set or update a principal's permission for an autonomous agent.
    
    Requires ADMIN permission on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        permission_request: Permission data
        handler: Autonomous agent handler dependency
        
    Returns:
        Created or updated permission
    """
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        
        return handler.set_autonomous_agent_permission(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            request=permission_request,
            user_id=user_id,
            user=user
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set autonomous agent permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set autonomous agent permission"
        )


@router.delete(
    "/{autonomous_agent_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete autonomous agent permission",
    description="Remove a principal's permission for an autonomous agent"
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_autonomous_agent_permission(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    delete_request: SetAutonomousAgentPermissionRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> Response:
    """
    Remove a principal's permission for an autonomous agent.
    
    Requires ADMIN permission on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        delete_request: Permission data (principal_id, principal_type, permission)
        handler: Autonomous agent handler dependency
        
    Returns:
        204 No Content on success
    """
    try:
        handler.delete_autonomous_agent_permission(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type,
            role=delete_request.role
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AutonomousAgentPermissionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete autonomous agent permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete autonomous agent permission"
        )


# ========== API Key Management Endpoints ==========

@router.get(
    "/{autonomous_agent_id}/keys/{key_number}",
    response_model=AutonomousAgentKeyResponse,
    summary="Get autonomous agent API key",
    description="Get an API key for an autonomous agent (1 = primary, 2 = secondary)"
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def get_autonomous_agent_key(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    key_number: int,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> AutonomousAgentKeyResponse:
    """
    Get an API key for an autonomous agent.
    
    Requires WRITE or ADMIN permission on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        key_number: Key number (1 for primary, 2 for secondary)
        handler: Autonomous agent handler dependency
        
    Returns:
        The API key
    """
    try:
        if key_number not in [1, 2]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="key_number must be 1 or 2"
            )
        
        return handler.get_api_key(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            key_number=key_number
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AutonomousAgentKeyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get autonomous agent key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get autonomous agent key"
        )


@router.put(
    "/{autonomous_agent_id}/keys/{key_number}/rotate",
    response_model=AutonomousAgentKeyResponse,
    summary="Rotate autonomous agent API key",
    description="Rotate an API key for an autonomous agent (1 = primary, 2 = secondary)"
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def rotate_autonomous_agent_key(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    key_number: int,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler)
) -> AutonomousAgentKeyResponse:
    """
    Rotate an API key for an autonomous agent.
    
    This generates a new random API key and replaces the existing one.
    Requires WRITE or ADMIN permission on the autonomous agent, or GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        key_number: Key number (1 for primary, 2 for secondary)
        handler: Autonomous agent handler dependency
        
    Returns:
        The new API key
    """
    try:
        if key_number not in [1, 2]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="key_number must be 1 or 2"
            )
        
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        
        return handler.rotate_api_key(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            key_number=key_number,
            user_id=user_id
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AutonomousAgentKeyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rotate autonomous agent key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate autonomous agent key"
        )


# ========== Config Endpoint (Agent Service) ==========

@router.get(
    "/{autonomous_agent_id}/config",
    response_model=AutonomousAgentConfigResponse,
    summary="Get autonomous agent configuration",
    description="""
    Get the full autonomous agent configuration including credential secrets.
    
    **Authentication**: This endpoint uses API key authentication via the 
    `X-Unified-UI-Autonomous-Agent-API-Key` header (NOT Bearer token).
    
    The API key must match either the primary or secondary key of the autonomous agent.
    
    This endpoint is designed for external systems (like N8N) to fetch configuration
    and credentials needed to perform autonomous agent operations.
    
    **IMPORTANT**: No caching is used for this endpoint to ensure key rotation 
    takes effect immediately.
    """
)
@authenticate_autonomous_agent_api_key()
async def get_autonomous_agent_config(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler)
) -> AutonomousAgentConfigResponse:
    """
    Get autonomous agent configuration with resolved credentials.
    
    This endpoint is authenticated via X-Unified-UI-Autonomous-Agent-API-Key header.
    The autonomous agent must be active.
    
    Args:
        request: FastAPI request with autonomous_agent in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        handler: Autonomous agent handler dependency
        credential_handler: Credential handler for fetching secrets
        
    Returns:
        AutonomousAgentConfigResponse with full config including secrets
    """
    try:
        # The autonomous agent is already validated and stored in request.state
        # by the authenticate_autonomous_agent_api_key decorator
        autonomous_agent = request.state.autonomous_agent
        
        return handler.get_autonomous_agent_config(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            autonomous_agent=autonomous_agent,
            credential_handler=credential_handler
        )
    except InvalidCredentialError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get autonomous agent config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get autonomous agent configuration"
        )
