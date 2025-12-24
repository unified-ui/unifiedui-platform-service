"""Custom Groups API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, Request

from aihub.handlers.custom_groups import CustomGroupHandler
from aihub.handlers.dependencies import get_custom_group_handler
from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.identity.users import ContextIdentityUser
from aihub.core.database.enums import TenantRolesEnum, PermissionActionEnum
from aihub.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    UpdateCustomGroupRequest,
    SetPrincipalRoleRequest,
    DeletePrincipalRoleRequest
)
from aihub.schema.responses.custom_groups import (
    CustomGroupResponse,
    CustomGroupPrincipalsResponse,
    PrincipalsResponse
)


router = APIRouter()


@router.get(
    "",
    response_model=list[CustomGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="List Custom Groups",
    description="Get a paginated list of custom groups in a tenant"
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
@check_permissions(entity="tenant", required_permissions=[TenantRolesEnum.CUSTOM_GROUP_CREATOR, TenantRolesEnum.CUSTOM_GROUPS_ADMIN, TenantRolesEnum.GLOBAL_ADMIN])
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
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN])
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
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.ADMIN])
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


# Principal Management Routes

@router.get(
    "/{custom_group_id}/principals",
    response_model=CustomGroupPrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Custom Group Principals",
    description="Get all principals and their permissions for a custom group"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.READ, PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN])
async def list_custom_group_principals(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupPrincipalsResponse:
    """
    Get all principals and their permissions for a specific custom group.
    Requires READ, WRITE, or ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupPrincipalsResponse: All principals with their permissions on the custom group
    """
    result = handler.list_custom_group_principals(tenant_id, custom_group_id)
    return CustomGroupPrincipalsResponse(**result)


@router.get(
    "/{custom_group_id}/principals/{principal_id}",
    response_model=PrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Principal Permissions",
    description="Get all permissions for a specific principal on a custom group"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.READ, PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN])
async def get_principal_permissions(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    principal_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> PrincipalsResponse:
    """
    Get all permissions for a specific principal on a custom group.
    Requires READ, WRITE, or ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        principal_id: The ID of the principal
        handler: Custom group handler dependency
    
    Returns:
        PrincipalsResponse: Principal's permissions on the custom group
    """
    result = handler.get_principal_permissions(tenant_id, custom_group_id, principal_id)
    return PrincipalsResponse(**result)


@router.put(
    "/{custom_group_id}/principals",
    response_model=PrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Principal Permission",
    description="Add or update a permission for a principal on a custom group (requires ADMIN)"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.ADMIN])
async def set_principal_permission(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    role_data: SetPrincipalRoleRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> PrincipalsResponse:
    """
    Add or update a permission for a principal on a custom group.
    Requires ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        principal_id: The ID of the principal (from path, must match request body)
        permission_data: Permission data to set
        handler: Custom group handler dependency
    
    Returns:
        PrincipalsResponse: Updated principal's permissions on the custom group
    """
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    result = handler.set_principal_permission(
        tenant_id=tenant_id,
        custom_group_id=custom_group_id,
        principal_id=role_data.principal_id,
        principal_type=role_data.principal_type,
        role=role_data.role,
        user_id=user_id
    )
    return PrincipalsResponse(**result)


@router.delete(
    "/{custom_group_id}/principals",
    response_model=PrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Principal Permission",
    description="Remove a specific permission from a principal on a custom group (requires ADMIN)"
)
@authenticate
@check_permissions(entity="custom_group", required_permissions=[PermissionActionEnum.ADMIN])
async def delete_principal_permission(
    request: Request,
    tenant_id: str,
    custom_group_id: str,
    role_data: DeletePrincipalRoleRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> PrincipalsResponse:
    """
    Remove a specific permission from a principal on a custom group.
    Requires ADMIN permission on the group, or GLOBAL_ADMIN/CUSTOM_GROUPS_ADMIN on tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        custom_group_id: The ID of the custom group
        principal_id: The ID of the principal (from path, must match request body)
        permission_data: Permission data to delete
        handler: Custom group handler dependency
    
    Returns:
        PrincipalsResponse: Remaining principal's permissions on the custom group
    """
    result = handler.delete_principal_permission(
        tenant_id=tenant_id,
        custom_group_id=custom_group_id,
        principal_id=role_data.principal_id,
        principal_type=role_data.principal_type,
        role=role_data.role
    )
    return PrincipalsResponse(**result)
