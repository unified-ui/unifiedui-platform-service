"""API routes for ReACT agent management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import ListViewEnum, OrderDirectionEnum, PermissionActionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.re_act_agents import ReActAgentNotFoundError
from unifiedui.handlers.dependencies.re_act_agents import get_re_act_agent_handler
from unifiedui.handlers.re_act_agents import ReActAgentHandler
from unifiedui.logger import get_logger
from unifiedui.schema.requests.re_act_agent_permissions import SetReActAgentPermissionRequest
from unifiedui.schema.requests.re_act_agents import CreateReActAgentRequest, UpdateReActAgentRequest
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.re_act_agents import ReActAgentResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/re-act-agents")


@router.get("", summary="List ReACT agents", description="Get a paginated list of ReACT agents for the current tenant.")
@authenticate()
async def list_re_act_agents(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by agent name"),
    is_active: int | None = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    tags: str | None = Query(None, description="Comma-separated list of tag IDs to filter by"),
    order_by: str | None = Query(None, description="Column name to order by"),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    view: ListViewEnum | None = Query(None, description="View type: 'full' (default) or 'quick-list'"),
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
):
    """List ReACT agents for a tenant."""
    try:
        user: ContextIdentityUser = request.state.user

        tag_ids = None
        if tags:
            try:
                tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tag IDs format. Must be comma-separated integers.",
                )

        logger.info(
            "API: List ReACT agents",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit,
                "tags": tag_ids,
            },
        )

        return handler.list_re_act_agents(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name,
            is_active=is_active,
            tag_ids=tag_ids,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
            view=view.value if view else None,
            user=user,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list ReACT agents: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list ReACT agents")


@router.post(
    "",
    response_model=ReActAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ReACT agent",
    description="Create a new ReACT agent",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        TenantRolesEnum.REACT_AGENT_CREATOR,
    ],
)
async def create_re_act_agent(
    request: Request,
    tenant_id: str,
    create_request: CreateReActAgentRequest,
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> ReActAgentResponse:
    """Create a new ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create ReACT agent",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "agent_name": create_request.name},
        )
        return handler.create_re_act_agent(
            tenant_id=tenant_id, request=create_request, user_id=user.identity.get_id(), user=user
        )
    except Exception as e:
        logger.error(f"Failed to create ReACT agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create ReACT agent: {e!s}"
        )


@router.get(
    "/{re_act_agent_id}",
    response_model=ReActAgentResponse,
    summary="Get ReACT agent",
    description="Get a specific ReACT agent by ID",
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
async def get_re_act_agent(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> ReActAgentResponse:
    """Get a specific ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get ReACT agent",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "user_id": user.identity.get_id()},
        )
        return handler.get_re_act_agent(tenant_id=tenant_id, re_act_agent_id=re_act_agent_id, user=user)
    except ReActAgentNotFoundError as e:
        logger.warning(f"ReACT agent not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get ReACT agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get ReACT agent")


@router.patch(
    "/{re_act_agent_id}",
    response_model=ReActAgentResponse,
    summary="Update ReACT agent",
    description="Update an existing ReACT agent",
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
async def update_re_act_agent(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    update_request: UpdateReActAgentRequest,
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> ReActAgentResponse:
    """Update an existing ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update ReACT agent",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "user_id": user.identity.get_id()},
        )
        return handler.update_re_act_agent(
            tenant_id=tenant_id, re_act_agent_id=re_act_agent_id, request=update_request, user_id=user.identity.get_id()
        )
    except ReActAgentNotFoundError as e:
        logger.warning(f"ReACT agent not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update ReACT agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update ReACT agent: {e!s}"
        )


@router.delete(
    "/{re_act_agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete ReACT agent",
    description="Delete a ReACT agent",
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.REACT_AGENT_ADMIN, PermissionActionEnum.ADMIN],
)
async def delete_re_act_agent(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> Response:
    """Delete a ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete ReACT agent",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "user_id": user.identity.get_id()},
        )
        handler.delete_re_act_agent(tenant_id=tenant_id, re_act_agent_id=re_act_agent_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ReActAgentNotFoundError as e:
        logger.warning(f"ReACT agent not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete ReACT agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete ReACT agent")


@router.get(
    "/{re_act_agent_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List ReACT agent permissions",
    description="Get all principals with permissions on this ReACT agent",
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.REACT_AGENT_ADMIN, PermissionActionEnum.ADMIN],
)
async def list_re_act_agent_permissions(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = Query(None),
    roles: str | None = Query(None),
    is_active: bool | None = Query(None),
    order_by: str | None = Query(None),
    order_direction: OrderDirectionEnum | None = Query(None),
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> ResourcePrincipalsResponse:
    """List all principals with permissions on a ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List ReACT agent permissions",
            extra={"tenant_id": tenant_id, "re_act_agent_id": re_act_agent_id, "user_id": user.identity.get_id()},
        )

        role_list = None
        if roles:
            role_list = [r.strip() for r in roles.split(",") if r.strip()]

        return handler.list_re_act_agent_permissions(
            tenant_id=tenant_id,
            re_act_agent_id=re_act_agent_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=role_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
        )
    except ReActAgentNotFoundError as e:
        logger.warning(f"ReACT agent not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list ReACT agent permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list ReACT agent permissions"
        )


@router.get(
    "/{re_act_agent_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get ReACT agent permission",
    description="Get permissions for a specific principal on this ReACT agent",
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.REACT_AGENT_ADMIN, PermissionActionEnum.ADMIN],
)
async def get_re_act_agent_permission(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    principal_id: str,
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> PrincipalWithRolesResponse:
    """Get permission for a specific principal on a ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get ReACT agent permission",
            extra={
                "tenant_id": tenant_id,
                "re_act_agent_id": re_act_agent_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.get_re_act_agent_permission(
            tenant_id=tenant_id, re_act_agent_id=re_act_agent_id, principal_id=principal_id
        )
    except ReActAgentNotFoundError as e:
        logger.warning(f"ReACT agent or permission not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get ReACT agent permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get ReACT agent permission"
        )


@router.put(
    "/{re_act_agent_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set ReACT agent permission",
    description="Set or update a permission for a principal on this ReACT agent",
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.REACT_AGENT_ADMIN, PermissionActionEnum.ADMIN],
)
async def set_re_act_agent_permission(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    permission_request: SetReActAgentPermissionRequest,
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> PrincipalWithRolesResponse:
    """Set a permission for a principal on a ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set ReACT agent permission",
            extra={
                "tenant_id": tenant_id,
                "re_act_agent_id": re_act_agent_id,
                "principal_id": permission_request.principal_id,
                "role": permission_request.role.value,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.set_re_act_agent_permission(
            tenant_id=tenant_id,
            re_act_agent_id=re_act_agent_id,
            request=permission_request,
            user_id=user.identity.get_id(),
            user=user,
        )
    except ReActAgentNotFoundError as e:
        logger.warning(f"ReACT agent not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to set ReACT agent permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set ReACT agent permission"
        )


@router.delete(
    "/{re_act_agent_id}/principals/{principal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete ReACT agent permission",
    description="Delete a permission for a principal on this ReACT agent",
)
@authenticate()
@check_permissions(
    entity="re_act_agent",
    required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.REACT_AGENT_ADMIN, PermissionActionEnum.ADMIN],
)
async def delete_re_act_agent_permission(
    request: Request,
    tenant_id: str,
    re_act_agent_id: str,
    principal_id: str,
    principal_type: str = Query(..., description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)"),
    permission: str = Query(..., description="Permission to delete (READ, WRITE, ADMIN)"),
    handler: ReActAgentHandler = Depends(get_re_act_agent_handler),
) -> Response:
    """Delete a permission for a principal on a ReACT agent."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete ReACT agent permission",
            extra={
                "tenant_id": tenant_id,
                "re_act_agent_id": re_act_agent_id,
                "principal_id": principal_id,
                "permission": permission,
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_re_act_agent_permission(
            tenant_id=tenant_id,
            re_act_agent_id=re_act_agent_id,
            principal_id=principal_id,
            principal_type=principal_type,
            permission=permission,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ReActAgentNotFoundError as e:
        logger.warning(f"ReACT agent or permission not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete ReACT agent permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete ReACT agent permission"
        )
