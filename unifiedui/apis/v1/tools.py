"""API routes for tool management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import ListViewEnum, OrderDirectionEnum, PermissionActionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.tools import InvalidToolCredentialError, ToolConfigValidationError, ToolNotFoundError
from unifiedui.handlers.dependencies import get_tool_handler
from unifiedui.handlers.tools import ToolHandler
from unifiedui.logger import get_logger
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
from unifiedui.schema.requests.tools import CreateToolRequest, UpdateToolRequest
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.tools import ToolResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/tools")


@router.get(
    "",
    summary="List tools",
    description="Get a paginated list of tools for the current tenant. Use view=quick-list to get only id and name.",
)
@authenticate()
async def list_tools(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by tool name"),
    type: str | None = Query(
        None, description="Comma-separated list of tool types to filter by (e.g., 'MCP_SERVER,OPENAPI_DEFINITION')"
    ),
    is_active: int | None = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    tags: str | None = Query(None, description="Comma-separated list of tag IDs to filter by"),
    order_by: str | None = Query(
        None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    view: ListViewEnum | None = Query(None, description="View type: 'full' (default) or 'quick-list'"),
    handler: ToolHandler = Depends(get_tool_handler),
):
    """
    List tools for a tenant.

    Users see only tools they have permissions for, unless they have
    TENANT_GLOBAL_ADMIN or REACT_AGENT_ADMIN on tenant level.
    """
    try:
        user: ContextIdentityUser = request.state.user

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

        # Parse type filter from comma-separated string
        types = None
        if type:
            types = [t.strip() for t in type.split(",") if t.strip()]

        logger.info(
            "API: List tools",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit,
                "tags": tag_ids,
                "type": types,
            },
        )

        return handler.list_tools(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name,
            type_filter=types,
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
        logger.error("Failed to list tools: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list tools")


@router.post(
    "",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tool",
    description="Create a new tool",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        TenantRolesEnum.REACT_AGENT_CREATOR,
    ],
)
async def create_tool(
    request: Request,
    tenant_id: str,
    create_request: CreateToolRequest,
    handler: ToolHandler = Depends(get_tool_handler),
) -> ToolResponse:
    """
    Create a new tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create tool",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "tool_name": create_request.name},
        )
        return handler.create_tool(
            tenant_id=tenant_id, request=create_request, user_id=user.identity.get_id(), user=user
        )
    except InvalidToolCredentialError as e:
        logger.warning("Invalid credential: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ToolConfigValidationError as e:
        logger.warning("Tool config validation failed: %s", e.message, extra={"errors": e.errors})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool config validation failed: {e.message}. Errors: {'; '.join(e.errors)}",
        )
    except Exception as e:
        logger.error("Failed to create tool: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create tool: {e!s}")


@router.get("/{tool_id}", response_model=ToolResponse, summary="Get tool", description="Get a specific tool by ID")
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_tool(
    request: Request, tenant_id: str, tool_id: str, handler: ToolHandler = Depends(get_tool_handler)
) -> ToolResponse:
    """
    Get a specific tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get tool", extra={"tenant_id": tenant_id, "tool_id": tool_id, "user_id": user.identity.get_id()}
        )
        return handler.get_tool(tenant_id=tenant_id, tool_id=tool_id, user=user)
    except ToolNotFoundError as e:
        logger.warning("Tool not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get tool: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get tool")


@router.patch("/{tool_id}", response_model=ToolResponse, summary="Update tool", description="Update an existing tool")
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def update_tool(
    request: Request,
    tenant_id: str,
    tool_id: str,
    update_request: UpdateToolRequest,
    handler: ToolHandler = Depends(get_tool_handler),
) -> ToolResponse:
    """
    Update a tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update tool", extra={"tenant_id": tenant_id, "tool_id": tool_id, "user_id": user.identity.get_id()}
        )
        return handler.update_tool(
            tenant_id=tenant_id, tool_id=tool_id, request=update_request, user_id=user.identity.get_id()
        )
    except ToolNotFoundError as e:
        logger.warning("Tool not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidToolCredentialError as e:
        logger.warning("Invalid credential: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ToolConfigValidationError as e:
        logger.warning("Tool config validation failed: %s", e.message, extra={"errors": e.errors})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool config validation failed: {e.message}. Errors: {'; '.join(e.errors)}",
        )
    except Exception as e:
        logger.error("Failed to update tool: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update tool: {e!s}")


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete tool", description="Delete a tool")
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_tool(
    request: Request, tenant_id: str, tool_id: str, handler: ToolHandler = Depends(get_tool_handler)
) -> Response:
    """
    Delete a tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete tool", extra={"tenant_id": tenant_id, "tool_id": tool_id, "user_id": user.identity.get_id()}
        )
        handler.delete_tool(tenant_id=tenant_id, tool_id=tool_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ToolNotFoundError as e:
        logger.warning("Tool not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete tool: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tool")


# ========== Permission Management Endpoints ==========


@router.get(
    "/{tool_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List tool permissions",
    description="Get all principals with permissions on this tool",
)
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def list_tool_permissions(
    request: Request,
    tenant_id: str,
    tool_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(
        None, description="Comma-separated list of roles to filter by (e.g., 'READ,WRITE,ADMIN')"
    ),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(
        None, description="Column to order by (e.g., 'display_name', 'principal_name', 'mail', 'created_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    handler: ToolHandler = Depends(get_tool_handler),
) -> ResourcePrincipalsResponse:
    """
    List all principals with permissions on a tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List tool permissions",
            extra={"tenant_id": tenant_id, "tool_id": tool_id, "user_id": user.identity.get_id()},
        )

        # Parse roles from comma-separated string
        role_list = None
        if roles:
            role_list = [r.strip() for r in roles.split(",") if r.strip()]

        return handler.list_tool_permissions(
            tenant_id=tenant_id,
            tool_id=tool_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=role_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
        )
    except ToolNotFoundError as e:
        logger.warning("Tool not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to list tool permissions: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list tool permissions")


@router.get(
    "/{tool_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get tool permission",
    description="Get permissions for a specific principal on this tool",
)
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def get_tool_permission(
    request: Request, tenant_id: str, tool_id: str, principal_id: str, handler: ToolHandler = Depends(get_tool_handler)
) -> PrincipalWithRolesResponse:
    """
    Get permissions for a specific principal on a tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get tool permission",
            extra={
                "tenant_id": tenant_id,
                "tool_id": tool_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.get_tool_permission(tenant_id=tenant_id, tool_id=tool_id, principal_id=principal_id)
    except ToolNotFoundError as e:
        logger.warning("Tool or permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get tool permission: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get tool permission")


@router.put(
    "/{tool_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set tool permission",
    description="Set or update a permission for a principal on this tool",
)
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def set_tool_permission(
    request: Request,
    tenant_id: str,
    tool_id: str,
    permission_request: SetResourcePermissionRequest,
    handler: ToolHandler = Depends(get_tool_handler),
) -> PrincipalWithRolesResponse:
    """
    Set or update a permission for a principal on a tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set tool permission",
            extra={
                "tenant_id": tenant_id,
                "tool_id": tool_id,
                "principal_id": permission_request.principal_id,
                "role": permission_request.role.value,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.set_tool_permission(
            tenant_id=tenant_id, tool_id=tool_id, request=permission_request, user_id=user.identity.get_id(), user=user
        )
    except ToolNotFoundError as e:
        logger.warning("Tool not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to set tool permission: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set tool permission")


@router.delete(
    "/{tool_id}/principals/{principal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tool permission",
    description="Delete a permission for a principal on this tool",
)
@authenticate()
@check_permissions(
    entity="tool",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_tool_permission(
    request: Request,
    tenant_id: str,
    tool_id: str,
    principal_id: str,
    principal_type: str = Query(..., description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)"),
    permission: str = Query(..., description="Permission to delete (READ, WRITE, ADMIN)"),
    handler: ToolHandler = Depends(get_tool_handler),
) -> Response:
    """
    Delete a permission for a principal on a tool.
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete tool permission",
            extra={
                "tenant_id": tenant_id,
                "tool_id": tool_id,
                "principal_id": principal_id,
                "permission": permission,
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_tool_permission(
            tenant_id=tenant_id,
            tool_id=tool_id,
            principal_id=principal_id,
            principal_type=principal_type,
            permission=permission,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ToolNotFoundError as e:
        logger.warning("Tool or permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete tool permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tool permission"
        )
