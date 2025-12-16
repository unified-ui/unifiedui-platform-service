"""Custom groups API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, Request

from aihub.core.handlers.custom_groups import CustomGroupHandler
from aihub.core.handlers.dependencies_custom_groups import get_custom_group_handler
from aihub.core.middleware.apis.v1.auth import authenticate
from aihub.core.identity.users import IdentityUser
from aihub.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    UpdateCustomGroupRequest,
    AddMembersRequest,
    RemoveMembersRequest
)
from aihub.schema.responses.custom_groups import CustomGroupResponse
from aihub.exc.permissions import PermissionDeniedError


router = APIRouter()


@router.get(
    "",
    response_model=list[CustomGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="List Custom Groups",
    description="Get a paginated list of custom groups for a tenant"
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
    Get a paginated list of custom groups for a tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: Tenant ID from path
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        name: Optional filter by group name
        handler: Custom group handler dependency
    
    Returns:
        list[CustomGroupResponse]: List of custom groups
    """
    user: IdentityUser = request.state.user
    
    # Check if user has access to this tenant
    accessible_tenant_ids = [t.id for t in user.tenants]
    if tenant_id not in accessible_tenant_ids:
        raise PermissionDeniedError("tenants", tenant_id, "read")
    
    return handler.list_custom_groups(
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
        name=name
    )


@router.get(
    "/{group_id}",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Custom Group",
    description="Get a specific custom group by ID"
)
@authenticate
async def get_custom_group(
    request: Request,
    tenant_id: str,
    group_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
    """
    Get a specific custom group by ID.
    
    Args:
        request: FastAPI request object
        tenant_id: Tenant ID from path
        group_id: The ID of the custom group to retrieve
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupResponse: The custom group information
    
    Raises:
        CustomGroupNotFoundError: If group not found
        PermissionDeniedError: If user doesn't have access to this tenant
    """
    user: IdentityUser = request.state.user
    
    # Check if user has access to this tenant
    accessible_tenant_ids = [t.id for t in user.tenants]
    if tenant_id not in accessible_tenant_ids:
        raise PermissionDeniedError("tenants", tenant_id, "read")
    
    group = handler.get_custom_group(group_id)
    
    # Verify group belongs to the tenant
    if group.tenant_id != tenant_id:
        raise PermissionDeniedError("custom_groups", group_id, "read")
    
    return group


@router.post(
    "",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Group",
    description="Create a new custom group"
)
@authenticate
async def create_custom_group(
    request: Request,
    tenant_id: str,
    group_data: CreateCustomGroupRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
    """
    Create a new custom group.
    
    Args:
        request: FastAPI request object
        tenant_id: Tenant ID from path
        group_data: Group creation data
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupResponse: The created custom group
    """
    user: IdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    # Check if user has access to this tenant
    accessible_tenant_ids = [t.id for t in user.tenants]
    if tenant_id not in accessible_tenant_ids:
        raise PermissionDeniedError("tenants", tenant_id, "write")
    
    return handler.create_custom_group(
        tenant_id=tenant_id,
        data=group_data,
        user_id=user_id
    )


@router.patch(
    "/{group_id}",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Custom Group",
    description="Update an existing custom group"
)
@authenticate
async def update_custom_group(
    request: Request,
    tenant_id: str,
    group_id: str,
    group_data: UpdateCustomGroupRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
    """
    Update an existing custom group.
    
    Args:
        request: FastAPI request object
        tenant_id: Tenant ID from path
        group_id: The ID of the custom group to update
        group_data: Group update data
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupResponse: The updated custom group
    
    Raises:
        CustomGroupNotFoundError: If group not found
        PermissionDeniedError: If user doesn't have access
    """
    user: IdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    # Check if user has access to this tenant
    accessible_tenant_ids = [t.id for t in user.tenants]
    if tenant_id not in accessible_tenant_ids:
        raise PermissionDeniedError("tenants", tenant_id, "write")
    
    # Get group to verify it belongs to tenant
    group = handler.get_custom_group(group_id)
    if group.tenant_id != tenant_id:
        raise PermissionDeniedError("custom_groups", group_id, "write")
    
    return handler.update_custom_group(
        group_id=group_id,
        data=group_data,
        user_id=user_id
    )


@router.post(
    "/{group_id}/members",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Add Members",
    description="Add members to a custom group"
)
@authenticate
async def add_members(
    request: Request,
    tenant_id: str,
    group_id: str,
    members_data: AddMembersRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
    """
    Add members to a custom group.
    
    Args:
        request: FastAPI request object
        tenant_id: Tenant ID from path
        group_id: The ID of the custom group
        members_data: Members to add
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupResponse: The updated custom group
    """
    user: IdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    # Check if user has access to this tenant
    accessible_tenant_ids = [t.id for t in user.tenants]
    if tenant_id not in accessible_tenant_ids:
        raise PermissionDeniedError("tenants", tenant_id, "write")
    
    # Get group to verify it belongs to tenant
    group = handler.get_custom_group(group_id)
    if group.tenant_id != tenant_id:
        raise PermissionDeniedError("custom_groups", group_id, "write")
    
    return handler.add_members(
        group_id=group_id,
        data=members_data,
        user_id=user_id
    )


@router.delete(
    "/{group_id}/members",
    response_model=CustomGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove Members",
    description="Remove members from a custom group"
)
@authenticate
async def remove_members(
    request: Request,
    tenant_id: str,
    group_id: str,
    members_data: RemoveMembersRequest,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> CustomGroupResponse:
    """
    Remove members from a custom group.
    
    Args:
        request: FastAPI request object
        tenant_id: Tenant ID from path
        group_id: The ID of the custom group
        members_data: Members to remove
        handler: Custom group handler dependency
    
    Returns:
        CustomGroupResponse: The updated custom group
    """
    user: IdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    # Check if user has access to this tenant
    accessible_tenant_ids = [t.id for t in user.tenants]
    if tenant_id not in accessible_tenant_ids:
        raise PermissionDeniedError("tenants", tenant_id, "write")
    
    # Get group to verify it belongs to tenant
    group = handler.get_custom_group(group_id)
    if group.tenant_id != tenant_id:
        raise PermissionDeniedError("custom_groups", group_id, "write")
    
    return handler.remove_members(
        group_id=group_id,
        data=members_data,
        user_id=user_id
    )


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Custom Group",
    description="Delete a custom group by ID"
)
@authenticate
async def delete_custom_group(
    request: Request,
    tenant_id: str,
    group_id: str,
    handler: CustomGroupHandler = Depends(get_custom_group_handler)
) -> None:
    """
    Delete a custom group by ID.
    
    Args:
        request: FastAPI request object
        tenant_id: Tenant ID from path
        group_id: The ID of the custom group to delete
        handler: Custom group handler dependency
    
    Raises:
        CustomGroupNotFoundError: If group not found
        PermissionDeniedError: If user doesn't have access
    """
    user: IdentityUser = request.state.user
    
    # Check if user has access to this tenant
    accessible_tenant_ids = [t.id for t in user.tenants]
    if tenant_id not in accessible_tenant_ids:
        raise PermissionDeniedError("tenants", tenant_id, "admin")
    
    # Get group to verify it belongs to tenant
    group = handler.get_custom_group(group_id)
    if group.tenant_id != tenant_id:
        raise PermissionDeniedError("custom_groups", group_id, "admin")
    
    handler.delete_custom_group(group_id)
