"""API routes for autonomous agent management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import ListViewEnum, OrderDirectionEnum, PermissionActionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import (
    authenticate,
    authenticate_autonomous_agent_api_key,
    check_permissions,
)
from unifiedui.exc.autonomous_agents import (
    AutonomousAgentApiKeysNotAllowedError,
    AutonomousAgentConfigValidationError,
    AutonomousAgentKeyNotFoundError,
    AutonomousAgentNotFoundError,
    AutonomousAgentPermissionNotFoundError,
    UnsupportedAutonomousAgentTypeError,
)
from unifiedui.exc.chat_agent_config import InvalidCredentialError
from unifiedui.handlers.autonomous_agents import AutonomousAgentHandler
from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.handlers.dependencies import get_autonomous_agent_handler, get_credential_handler
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.logger import get_logger
from unifiedui.schema.requests.autonomous_agents import (
    CreateAutonomousAgentRequest,
    StartWorkflowRequest,
    UpdateAutonomousAgentRequest,
)
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
from unifiedui.schema.responses.autonomous_agents import (
    AutonomousAgentConfigResponse,
    AutonomousAgentKeyResponse,
    AutonomousAgentResponse,
    WorkflowRunDetailResponse,
    WorkflowRunRetryResponse,
    WorkflowRunsListResponse,
)
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/autonomous-agents")


@router.get(
    "",
    summary="List autonomous agents",
    description="Get a paginated list of autonomous agents for the current tenant. Use view=quick-list to get only id and name.",
)
@authenticate()
async def list_autonomous_agents(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by autonomous agent name"),
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
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
):
    """
    List autonomous agents for a tenant.

    Users see only autonomous agents they have permissions for, unless they have
    TENANT_GLOBAL_ADMIN or AUTONOMOUS_AGENTS_ADMIN on tenant level.

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
                    detail="Invalid tag IDs format. Must be comma-separated integers.",
                )

        user: ContextIdentityUser = request.state.user
        return filtered_response(
            handler.list_autonomous_agents(
                tenant_id=tenant_id,
                user=user,
                skip=skip,
                limit=limit,
                name_filter=name,
                is_active=is_active,
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
        logger.error("Failed to list autonomous agents: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list autonomous agents"
        )


@router.post(
    "",
    response_model=AutonomousAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create autonomous agent",
    description="Create a new autonomous agent",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_CREATOR,
    ],
)
async def create_autonomous_agent(
    request: Request,
    tenant_id: str,
    create_request: CreateAutonomousAgentRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> AutonomousAgentResponse:
    """
    Create a new autonomous agent.

    Requires TENANT_GLOBAL_ADMIN, AUTONOMOUS_AGENTS_ADMIN, or AUTONOMOUS_AGENTS_CREATOR permission on tenant level.
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

        return handler.create_autonomous_agent(tenant_id=tenant_id, request=create_request, user_id=user_id, user=user)
    except AutonomousAgentConfigValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnsupportedAutonomousAgentTypeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to create autonomous agent: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create autonomous agent"
        )


@router.get(
    "/{autonomous_agent_id}",
    response_model=AutonomousAgentResponse,
    summary="Get autonomous agent",
    description="Get a specific autonomous agent by ID",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_autonomous_agent(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
):
    """
    Get a specific autonomous agent by ID.

    Requires READ permission or higher on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        handler: Autonomous agent handler dependency

    Returns:
        Autonomous agent details
    """
    try:
        user: ContextIdentityUser = request.state.user
        return filtered_response(
            handler.get_autonomous_agent(tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id, user=user),
            fields,
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get autonomous agent: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get autonomous agent")


@router.patch(
    "/{autonomous_agent_id}",
    response_model=AutonomousAgentResponse,
    summary="Update autonomous agent",
    description="Update an existing autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def update_autonomous_agent(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    update_request: UpdateAutonomousAgentRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> AutonomousAgentResponse:
    """
    Update an existing autonomous agent.

    Requires WRITE permission or higher on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

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
            tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id, request=update_request, user_id=user_id
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AutonomousAgentConfigValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to update autonomous agent: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update autonomous agent"
        )


@router.delete(
    "/{autonomous_agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete autonomous agent",
    description="Delete an autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_autonomous_agent(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> Response:
    """
    Delete an autonomous agent.

    Requires WRITE permission or higher on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        handler: Autonomous agent handler dependency

    Returns:
        204 No Content on success
    """
    try:
        handler.delete_autonomous_agent(tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete autonomous agent: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete autonomous agent"
        )


@router.post(
    "/{autonomous_agent_id}/duplicate",
    response_model=AutonomousAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate autonomous agent",
    description="Create an exact copy of an autonomous agent with name + ' Copy'",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_CREATOR,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def duplicate_autonomous_agent(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> AutonomousAgentResponse:
    """
    Duplicate an autonomous agent.

    Creates an exact copy of the autonomous agent with name + " Copy".
    New API keys are generated for the duplicate.
    Requires WRITE permission or higher, or AUTONOMOUS_AGENTS_CREATOR on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID to duplicate

    Returns:
        The newly created autonomous agent
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Duplicate autonomous agent",
            extra={
                "tenant_id": tenant_id,
                "autonomous_agent_id": autonomous_agent_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.duplicate_autonomous_agent(
            tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id, user_id=user.identity.get_id(), user=user
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to duplicate autonomous agent: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to duplicate autonomous agent: {e!s}"
        )


# ========== Autonomous Agent Permission Endpoints ==========


@router.get(
    "/{autonomous_agent_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List autonomous agent permissions",
    description="Get all principals with permissions for an autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def list_autonomous_agent_permissions(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> ResourcePrincipalsResponse:
    """
    Get all principals with permissions for an autonomous agent.

    Requires READ permission or higher on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

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
            order_direction=order_direction,
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to list autonomous agent permissions: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list autonomous agent permissions"
        )


@router.get(
    "/{autonomous_agent_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get autonomous agent permissions for principal",
    description="Get all permissions for a specific principal on an autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_autonomous_agent_permission(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    principal_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> PrincipalWithRolesResponse:
    """
    Get all permissions for a specific principal on an autonomous agent.

    Requires READ permission or higher on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

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
            tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id, principal_id=principal_id
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get autonomous agent permission: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get autonomous agent permission"
        )


@router.put(
    "/{autonomous_agent_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set autonomous agent permission",
    description="Set or update a principal's permission for an autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def set_autonomous_agent_permission(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    permission_request: SetResourcePermissionRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> PrincipalWithRolesResponse:
    """
    Set or update a principal's permission for an autonomous agent.

    Requires ADMIN permission on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

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
            user=user,
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to set autonomous agent permission: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set autonomous agent permission"
        )


@router.delete(
    "/{autonomous_agent_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete autonomous agent permission",
    description="Remove a principal's permission for an autonomous agent",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_autonomous_agent_permission(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    delete_request: SetResourcePermissionRequest,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> Response:
    """
    Remove a principal's permission for an autonomous agent.

    Requires ADMIN permission on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

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
            role=delete_request.role,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AutonomousAgentPermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete autonomous agent permission: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete autonomous agent permission"
        )


# ========== API Key Management Endpoints ==========


@router.get(
    "/{autonomous_agent_id}/keys/{key_number}",
    response_model=AutonomousAgentKeyResponse,
    summary="Get autonomous agent API key",
    description="Get an API key for an autonomous agent (1 = primary, 2 = secondary)",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def get_autonomous_agent_key(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    key_number: int,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> AutonomousAgentKeyResponse:
    """
    Get an API key for an autonomous agent.

    Requires WRITE or ADMIN permission on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="key_number must be 1 or 2")

        return handler.get_api_key(tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id, key_number=key_number)
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AutonomousAgentApiKeysNotAllowedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AutonomousAgentKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get autonomous agent key: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get autonomous agent key"
        )


@router.put(
    "/{autonomous_agent_id}/keys/{key_number}/rotate",
    response_model=AutonomousAgentKeyResponse,
    summary="Rotate autonomous agent API key",
    description="Rotate an API key for an autonomous agent (1 = primary, 2 = secondary)",
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def rotate_autonomous_agent_key(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    key_number: int,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> AutonomousAgentKeyResponse:
    """
    Rotate an API key for an autonomous agent.

    This generates a new random API key and replaces the existing one.
    Requires WRITE or ADMIN permission on the autonomous agent, or TENANT_GLOBAL_ADMIN/AUTONOMOUS_AGENTS_ADMIN on tenant.

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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="key_number must be 1 or 2")

        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()

        return handler.rotate_api_key(
            tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id, key_number=key_number, user_id=user_id
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AutonomousAgentApiKeysNotAllowedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AutonomousAgentKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to rotate autonomous agent key: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to rotate autonomous agent key"
        )


# ========== API Key Validation Endpoint (Agent Service) ==========


@router.post(
    "/{autonomous_agent_id}/validate-api-key",
    summary="Validate autonomous agent API key",
    description="""
    Lightweight endpoint to validate an autonomous agent API key without loading
    the full configuration or credential secrets.

    **Authentication**: This endpoint uses API key authentication via the
    `X-Unified-UI-Autonomous-Agent-API-Key` header (NOT Bearer token).

    Returns the autonomous agent ID and tenant ID if the API key is valid.
    This is used by the agent-service to validate API keys for trace ingestion
    without triggering credential secret resolution.
    """,
)
@authenticate_autonomous_agent_api_key()
async def validate_autonomous_agent_api_key(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
) -> dict:
    autonomous_agent = request.state.autonomous_agent
    return {
        "valid": True,
        "autonomous_agent_id": str(autonomous_agent.id),
        "tenant_id": tenant_id,
    }


# ========== Config Endpoint (Agent Service) ==========


@router.get(
    "/{autonomous_agent_id}/config",
    response_model=AutonomousAgentConfigResponse,
    summary="Get autonomous agent configuration (API Key)",
    description="""
    Get the full autonomous agent configuration including credential secrets.

    **Authentication**: This endpoint uses API key authentication via the
    `X-Unified-UI-Autonomous-Agent-API-Key` header (NOT Bearer token).

    The API key must match either the primary or secondary key of the autonomous agent.

    This endpoint is designed for external systems (like N8N) to fetch configuration
    and credentials needed to perform autonomous agent operations.

    **IMPORTANT**: No caching is used for this endpoint to ensure key rotation
    takes effect immediately.
    """,
)
@authenticate_autonomous_agent_api_key()
async def get_autonomous_agent_config(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> AutonomousAgentConfigResponse:
    """
    Get autonomous agent configuration with resolved credentials via API Key auth.

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
        autonomous_agent = request.state.autonomous_agent

        return handler.get_autonomous_agent_config(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            autonomous_agent=autonomous_agent,
            credential_handler=credential_handler,
        )
    except InvalidCredentialError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get autonomous agent config: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get autonomous agent configuration"
        )


@router.get(
    "/{autonomous_agent_id}/config/bearer",
    response_model=AutonomousAgentConfigResponse,
    summary="Get autonomous agent configuration (Bearer)",
    description="""
    Get the full autonomous agent configuration including credential secrets.

    **Authentication**: This endpoint uses Bearer token authentication.
    Requires WRITE or ADMIN permission on the autonomous agent (direct or via group).

    This enables users and service principals to fetch agent configuration
    for trace import operations without needing the agent's API key.
    """,
)
@authenticate("X_AGENT_SERVICE_KEY")
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def get_autonomous_agent_config_bearer(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> AutonomousAgentConfigResponse:
    """
    Get autonomous agent configuration with resolved credentials via Bearer auth.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        handler: Autonomous agent handler dependency
        credential_handler: Credential handler for fetching secrets

    Returns:
        AutonomousAgentConfigResponse with full config including secrets
    """
    try:
        autonomous_agent = handler.get_autonomous_agent_model(
            tenant_id=tenant_id, autonomous_agent_id=autonomous_agent_id
        )

        return handler.get_autonomous_agent_config(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            autonomous_agent=autonomous_agent,
            credential_handler=credential_handler,
        )
    except InvalidCredentialError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get autonomous agent config: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get autonomous agent configuration"
        )


@router.get(
    "/{autonomous_agent_id}/workflow-runs",
    response_model=WorkflowRunsListResponse,
    summary="List workflow runs",
    description="""
    List workflow execution runs from the external workflow platform (e.g., N8N).
    Fetches recent executions using the agent's stored configuration and credentials.

    Requires WRITE or ADMIN permission on the autonomous agent.
    """,
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def list_workflow_runs(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of runs to return"),
    cursor: str | None = Query(None, description="Pagination cursor for next page"),
    execution_status: str | None = Query(
        None, alias="status", description="Filter by execution status (e.g., success, error, running)"
    ),
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> WorkflowRunsListResponse:
    """List workflow runs for an autonomous agent.

    Args:
        request: FastAPI request
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        limit: Maximum number of runs to return
        cursor: Pagination cursor for next page
        execution_status: Filter by execution status
        handler: Autonomous agent handler dependency
        credential_handler: Credential handler for fetching secrets

    Returns:
        WorkflowRunsListResponse with list of execution runs
    """
    try:
        return handler.get_workflow_runs(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            credential_handler=credential_handler,
            limit=limit,
            cursor=cursor,
            status=execution_status,
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnsupportedAutonomousAgentTypeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list workflow runs: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list workflow runs")


@router.get(
    "/{autonomous_agent_id}/workflow-runs/{execution_id}",
    response_model=WorkflowRunDetailResponse,
    summary="Get workflow run detail",
    description="""
    Get a single workflow execution with full data (input/output) from the external platform.
    Uses includeData=true to fetch the complete execution data.

    Requires WRITE or ADMIN permission on the autonomous agent.
    """,
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def get_workflow_run_detail(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    execution_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> WorkflowRunDetailResponse:
    """Get full details of a single workflow execution.

    Args:
        request: FastAPI request
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        execution_id: Execution ID from path
        handler: Autonomous agent handler dependency
        credential_handler: Credential handler for fetching secrets

    Returns:
        WorkflowRunDetailResponse with full execution data
    """
    try:
        return handler.get_workflow_run_detail(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            execution_id=execution_id,
            credential_handler=credential_handler,
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnsupportedAutonomousAgentTypeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AutonomousAgentConfigValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get workflow run detail: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get workflow run detail"
        )


@router.post(
    "/{autonomous_agent_id}/workflow-runs/{execution_id}/retry",
    response_model=WorkflowRunRetryResponse,
    summary="Retry workflow execution",
    description="""
    Retry a failed workflow execution. Only executions with status 'error' can be retried.

    Requires WRITE or ADMIN permission on the autonomous agent.
    """,
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def retry_workflow_run(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    execution_id: str,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> WorkflowRunRetryResponse:
    """Retry a failed workflow execution.

    Args:
        request: FastAPI request
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        execution_id: Execution ID to retry
        handler: Autonomous agent handler dependency
        credential_handler: Credential handler for fetching secrets

    Returns:
        WorkflowRunRetryResponse with retry result
    """
    try:
        return handler.retry_workflow_run(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            execution_id=execution_id,
            credential_handler=credential_handler,
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnsupportedAutonomousAgentTypeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AutonomousAgentConfigValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retry workflow execution: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retry workflow execution"
        )


@router.post(
    "/{autonomous_agent_id}/workflow-start",
    summary="Start workflow",
    description="""
    Trigger the workflow via its configured webhook URL.
    The autonomous agent must have a webhook_url configured.

    Requires WRITE or ADMIN permission on the autonomous agent.
    """,
)
@authenticate()
@check_permissions(
    entity="autonomous_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def start_workflow(
    request: Request,
    tenant_id: str,
    autonomous_agent_id: str,
    body: StartWorkflowRequest | None = None,
    handler: AutonomousAgentHandler = Depends(get_autonomous_agent_handler),
) -> dict:
    """
    Trigger a workflow via webhook.

    Args:
        request: FastAPI request
        tenant_id: Tenant ID from path
        autonomous_agent_id: Autonomous agent ID from path
        body: Optional request body with webhook payload
        handler: Autonomous agent handler dependency

    Returns:
        Response from the webhook endpoint
    """
    try:
        return handler.start_workflow(
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            body=body.body if body else None,
            files=[f.model_dump(by_alias=True) for f in body.files] if body and body.files else None,
            query_params=body.query_params if body else None,
        )
    except AutonomousAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnsupportedAutonomousAgentTypeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AutonomousAgentConfigValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start workflow: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start workflow")
