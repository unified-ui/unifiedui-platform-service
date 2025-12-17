"""Custom Groups API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, Request

from aihub.core.handlers.custom_groups import CustomGroupHandler
from aihub.core.handlers.dependencies import get_custom_group_handler
from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.identity.users import ContextIdentityUser
from aihub.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    UpdateCustomGroupRequest,
    SetCustomGroupPermissionRequest,
    DeleteCustomGroupPermissionRequest
)
from aihub.schema.responses.custom_groups import (
    CustomGroupResponse,
    CustomGroupPermissionsResponse
)


router = APIRouter()


@router.get(
    "",
    response_model=list[CustomGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="List Custom Groups",
    description="Get a paginated list of custom groups in a tenant (readable by all tenant members)"
)
@authenticate
async def list_custom_groups(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: Optional[str] = Query(None, description="Filter by group name"),
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> list[CustomGroupResponse]:
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
    return handler.list_custom_groups(
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
        name_filter=name
    )


@router.get(
    "/{custom_group_id}",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Custom Group",
    description="Get a specific custom group by ID"
)
@authenticate
async def get_custom_group(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
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
    return handler.get_custom_group(tenant_id, custom_group_id)


@router.post(
    "",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Group",
    description="Create a new custom group and assign creator as ADMIN (requires CUSTOM_GROUP_CREATOR, CUSTOM_GROUPS_ADMIN, or GLOBAL_ADMIN on tenant)"
)
@authenticate
@check_permissions(entity="tenant", required_permissions=["CUSTOM_GROUP_CREATOR", "CUSTOM_GROUPS_ADMIN", "GLOBAL_ADMIN"])
async def create_custom_group(
    request: Request,
    tenant_id: str,
    group_data: CreateCustomGroupRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
    """
    Create a new custom group and assign the creator as ADMIN.
    Requires CUSTOM_GROUP_CREATOR, CUSTOM_GROUPS_ADMIN, or GLOBAL_ADMIN permission on tenant.
    
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
    
    return handler.create_custom_group(tenant_id, group_data, user_id)


@router.patch(
    "/{custom_group_id}",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Custom Group",
    description="Update an existing custom group (requires WRITE/ADMIN on group or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant)"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=["WRITE", "ADMIN"])
async def update_custom_group(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    group_data: UpdateCustomGroupRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
    """
    Update an existing custom group.
    Requires WRITE or ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
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
    description="Delete a custom group (requires ADMIN on group or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant)"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=["ADMIN"])
async def delete_custom_group(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> None:
    """
    Delete a custom group.
    Requires ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        handler: Custom group handler dependency
    """
    handler.delete_custom_group(tenant_id, custom_group_id)


# Permission Management Routes

@router.get(
    "/{custom_group_id}/permissions",
    response_model=CustomGroupPermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Custom Group Permissions",
    description="Get all permissions for a custom group"
)
@authenticate
async def get_custom_group_permissions(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupPermissionsResponse:
    """
    Get all permissions for a specific custom group.
    Accessible by all authenticated tenant members.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupPermissionsResponse: All permissions for the custom group
    """
    return handler.get_custom_group_permissions(tenant_id, custom_group_id)


@router.put(
    "/{custom_group_id}/permissions",
    response_model=CustomGroupPermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Custom Group Permission",
    description="Add or update a permission on a custom group (requires ADMIN)"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=["ADMIN"])
async def set_custom_group_permission(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    permission_data: SetCustomGroupPermissionRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupPermissionsResponse:
    """
    Add or update a permission for a principal on a custom group.
    Requires ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        permission_data: Permission data to set
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupPermissionsResponse: Updated permissions for the custom group
    """
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    return handler.set_custom_group_permission(
        tenant_id=tenant_id,
        custom_group_id=custom_group_id,
        permission_data=permission_data,
        user_id=user_id
    )


@router.delete(
    "/{custom_group_id}/permissions",
    response_model=CustomGroupPermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Custom Group Permission",
    description="Remove a permission from a custom group (requires ADMIN)"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=["ADMIN"])
async def delete_custom_group_permission(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    permission_data: DeleteCustomGroupPermissionRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupPermissionsResponse:
    """
    Remove a permission from a custom group.
    Requires ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        permission_data: Permission data to delete
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupPermissionsResponse: Remaining permissions for the custom group
    """
    return handler.delete_custom_group_permission(
        tenant_id=tenant_id,
        custom_group_id=custom_group_id,
        permission_data=permission_data
    )
