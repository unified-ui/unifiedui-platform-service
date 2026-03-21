"""Custom Groups API endpoints."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request, status

from unifiedui.core.database.enums import OrderDirectionEnum, PermissionActionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.handlers.custom_groups import CustomGroupHandler
from unifiedui.handlers.dependencies import get_custom_group_handler
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    DeletePrincipalRoleRequest,
    SetPrincipalRoleRequest,
    UpdateCustomGroupRequest,
)
from unifiedui.schema.responses.custom_groups import CustomGroupResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

router = APIRouter()


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List Custom Groups",
    description="Get a paginated list of custom groups in a tenant",
)
@authenticate()
async def list_custom_groups(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by group name"),
    ids: str | None = Query(None, description="Comma-separated list of IDs to filter by"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    order_by: str | None = Query(
        None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
):
    """
    Get a paginated list of custom groups.
    Accessible by all authenticated tenant members.

    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        name: Optional filter by group name
        handler: Custom group handler dependency

    Returns:
        list[CustomGroupResponse]: List of custom groups
    """
    return filtered_response(
        handler.list_custom_groups(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
            id_list=parse_ids(ids),
        ),
        fields,
    )


@router.get(
    "/{custom_group_id}",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Custom Group",
    description="Get a specific custom group by ID",
)
@authenticate()
async def get_custom_group(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
):
    """
    Get a specific custom group by ID.
    Accessible by all authenticated tenant members.

    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        handler: Custom group handler dependency

    Returns:
        CustomGroupResponse: The custom group information
    """
    return filtered_response(
        handler.get_custom_group(tenant_id, custom_group_id),
        fields,
    )


@router.post(
    "",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Group",
    description="Create a new custom group and assign creator as ADMIN (requires CUSTOM_GROUP_CREATOR, CUSTOM_GROUPS_ADMIN, or TENANT_GLOBAL_ADMIN on tenant)",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.CUSTOM_GROUP_CREATOR,
        TenantRolesEnum.CUSTOM_GROUPS_ADMIN,
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
    ],
)
async def create_custom_group(
    request: Request,
    tenant_id: str,
    group_data: CreateCustomGroupRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
) -> CustomGroupResponse:
    """
    Create a new custom group and assign the creator as ADMIN.
    Requires CUSTOM_GROUP_CREATOR, CUSTOM_GROUPS_ADMIN, or TENANT_GLOBAL_ADMIN permission on tenant.

    Args:
        request: FastAPI request object (contains user in request.state)
        tenant_id: The ID of the tenant
        group_data: Custom group creation data
        handler: Custom group handler dependency

    Returns:
        CustomGroupResponse: The created custom group
    """
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()

    return handler.create_custom_group(tenant_id, group_data, user_id, user)


@router.patch(
    "/{custom_group_id}",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Custom Group",
    description="Update an existing custom group (requires WRITE/ADMIN on group or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant)",
)
@authenticate()
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN])
async def update_custom_group(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    group_data: UpdateCustomGroupRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
) -> CustomGroupResponse:
    """
    Update an existing custom group.
    Requires WRITE or ADMIN permission on the group, or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.

    Args:
        request: FastAPI request object (contains user in request.state)
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        group_data: Custom group update data
        handler: Custom group handler dependency

    Returns:
        CustomGroupResponse: The updated custom group
    """
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()

    return handler.update_custom_group(tenant_id, custom_group_id, group_data, user_id)


@router.delete(
    "/{custom_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Custom Group",
    description="Delete a custom group (requires ADMIN on group or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant)",
)
@authenticate()
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.ADMIN])
async def delete_custom_group(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
) -> None:
    """
    Delete a custom group.
    Requires ADMIN permission on the group, or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.

    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        handler: Custom group handler dependency
    """
    handler.delete_custom_group(tenant_id, custom_group_id)


# Principal Management Routes


@router.get(
    "/{custom_group_id}/principals",
    response_model=ResourcePrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Custom Group Principals",
    description="Get all principals and their permissions for a custom group",
)
@authenticate()
@check_permissions(
    entity="custom_group",
    required_permissions=[PermissionActionEnum.READ, PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN],
)
async def list_custom_group_principals(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
) -> ResourcePrincipalsResponse:
    """
    Get all principals and their permissions for a specific custom group.
    Requires READ, WRITE, or ADMIN permission on the group, or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.

    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        skip: Number of principals to skip
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated roles to filter by (OR logic)
        is_active: Filter by is_active status
        order_by: Column to order by
        order_direction: Sort direction
        handler: Custom group handler dependency

    Returns:
        ResourcePrincipalsResponse: All principals with their permissions on the custom group
    """
    # Parse comma-separated roles
    roles_list = [r.strip() for r in roles.split(",")] if roles else None

    return handler.list_custom_group_principals(
        tenant_id=tenant_id,
        custom_group_id=custom_group_id,
        skip=skip,
        limit=limit,
        search=search,
        roles=roles_list,
        is_active=is_active,
        order_by=order_by,
        order_direction=order_direction,
    )


@router.get(
    "/{custom_group_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Principal Permissions",
    description="Get all permissions for a specific principal on a custom group",
)
@authenticate()
@check_permissions(
    entity="custom_group",
    required_permissions=[PermissionActionEnum.READ, PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN],
)
async def get_principal_permissions(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    principal_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
) -> PrincipalWithRolesResponse:
    """
    Get all permissions for a specific principal on a custom group.
    Requires READ, WRITE, or ADMIN permission on the group, or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.

    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        principal_id: The ID of the principal
        handler: Custom group handler dependency

    Returns:
        PrincipalWithRolesResponse: Principal's permissions on the custom group
    """
    return handler.get_principal_permissions(tenant_id, custom_group_id, principal_id)


@router.put(
    "/{custom_group_id}/principals",
    response_model=PrincipalWithRolesResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Principal Permission",
    description="Add or update a permission for a principal on a custom group (requires ADMIN)",
)
@authenticate()
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.ADMIN])
async def set_principal_permission(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    role_data: SetPrincipalRoleRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
) -> PrincipalWithRolesResponse:
    """
    Add or update a permission for a principal on a custom group.
    Requires ADMIN permission on the group, or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.

    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        principal_id: The ID of the principal (from path, must match request body)
        permission_data: Permission data to set
        handler: Custom group handler dependency

    Returns:
        PrincipalWithRolesResponse: Updated principal's permissions on the custom group
    """
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()

    return handler.set_principal_permission(
        tenant_id=tenant_id,
        custom_group_id=custom_group_id,
        principal_id=role_data.principal_id,
        principal_type=role_data.principal_type,
        role=role_data.role,
        user_id=user_id,
        user=user,
    )


@router.delete(
    "/{custom_group_id}/principals",
    response_model=PrincipalWithRolesResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Principal Permission",
    description="Remove a specific permission from a principal on a custom group (requires ADMIN)",
)
@authenticate()
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.ADMIN])
async def delete_principal_permission(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    role_data: DeletePrincipalRoleRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler),
) -> PrincipalWithRolesResponse:
    """
    Remove a specific permission from a principal on a custom group.
    Requires ADMIN permission on the group, or TENANT_GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.

    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        principal_id: The ID of the principal (from path, must match request body)
        permission_data: Permission data to delete
        handler: Custom group handler dependency

    Returns:
        PrincipalWithRolesResponse: Remaining principal's permissions on the custom group
    """
    return handler.delete_principal_permission(
        tenant_id=tenant_id,
        custom_group_id=custom_group_id,
        principal_id=role_data.principal_id,
        principal_type=role_data.principal_type,
        role=role_data.role,
    )
