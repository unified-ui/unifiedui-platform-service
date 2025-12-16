"""Tenants API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, Request

from aihub.core.handlers.tenants import TenantHandler
from aihub.core.handlers.dependencies import get_tenant_handler
from aihub.core.handlers.permissions import PermissionHandler
from aihub.core.handlers.dependencies_permissions import get_permission_handler
from aihub.core.middleware.apis.v1.auth import authenticate
from aihub.core.identity.users import IdentityUser
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse
from aihub.schema.requests.permissions import SetPermissionsRequest, DeletePermissionRequest
from aihub.schema.responses.permissions import ResourcePermissionsResponse


router = APIRouter()


@router.get(
    "",
    response_model=list[TenantResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tenants",
    description="Get a paginated list of tenants (filtered by permissions)"
)
@authenticate
async def list_tenants(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: Optional[str] = Query(None, description="Filter by tenant name"),
    handler: TenantHandler = Depends(get_tenant_handler)
) -> list[TenantResponse]:
    """
    Get a paginated list of tenants (filtered by user permissions).
    
    Args:
        request: FastAPI request object
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        name: Optional filter by tenant name
        handler: Tenant handler dependency
    
    Returns:
        list[TenantResponse]: List of tenants user has access to
    """
    user: IdentityUser = request.state.user
    
    # Get accessible tenant IDs from user.tenants
    tenant_ids = [t.id for t in user.tenants]
    
    # Build filters
    filters = {}
    if name:
        filters["name"] = {"$regex": name, "$options": "i"}
    
    return handler.list_tenants(
        filters=filters,
        skip=skip,
        limit=limit,
        tenant_ids=tenant_ids
    )


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Tenant",
    description="Get a specific tenant by ID"
)
@authenticate
async def get_tenant(
    request: Request,
    tenant_id: str,
    handler: TenantHandler = Depends(get_tenant_handler)
) -> TenantResponse:
    """
    Get a specific tenant by ID.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant to retrieve
        handler: Tenant handler dependency
    
    Returns:
        TenantResponse: The tenant information
    
    Raises:
        TenantNotFoundError: If tenant not found (handled by global exception handler)
    """
    return handler.get_tenant(tenant_id)


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Tenant",
    description="Create a new tenant"
)
@authenticate
async def create_tenant(
    request: Request,
    tenant_data: CreateTenantRequest,
    handler: TenantHandler = Depends(get_tenant_handler)
) -> TenantResponse:
    """
    Create a new tenant.
    
    Args:
        request: FastAPI request object (contains user in request.state)
        tenant_data: Tenant creation data
        handler: Tenant handler dependency
    
    Returns:
        TenantResponse: The created tenant
    """
    user: IdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    return handler.create_tenant(tenant_data, user_id)


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Tenant",
    description="Update an existing tenant"
)
@authenticate
async def update_tenant(
    request: Request,
    tenant_id: str,
    tenant_data: UpdateTenantRequest,
    handler: TenantHandler = Depends(get_tenant_handler)
) -> TenantResponse:
    """
    Update an existing tenant.
    
    Args:
        request: FastAPI request object (contains user in request.state)
        tenant_id: The ID of the tenant to update
        tenant_data: Tenant update data
        handler: Tenant handler dependency
    
    Returns:
        TenantResponse: The updated tenant
    
    Raises:
        TenantNotFoundError: If tenant not found (handled by global exception handler)
    """
    user: IdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    return handler.update_tenant(tenant_id, tenant_data, user_id)


@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Tenant",
    description="Delete a tenant by ID"
)
@authenticate
async def delete_tenant(
    request: Request,
    tenant_id: str,
    handler: TenantHandler = Depends(get_tenant_handler)
) -> None:
    """
    Delete a tenant by ID.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant to delete
        handler: Tenant handler dependency
    
    Raises:
        TenantNotFoundError: If tenant not found (handled by global exception handler)
    """
    handler.delete_tenant(tenant_id)


# Permission Management Routes

@router.get(
    "/{tenant_id}/permissions",
    response_model=ResourcePermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Tenant Permissions",
    description="Get all permissions for a specific tenant"
)
@authenticate
async def get_tenant_permissions(
    request: Request,
    tenant_id: str,
    handler: PermissionHandler = Depends(get_permission_handler)
) -> ResourcePermissionsResponse:
    """
    Get all permissions for a specific tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        handler: Permission handler dependency
    
    Returns:
        ResourcePermissionsResponse: All permissions for the tenant
    """
    user: IdentityUser = request.state.user
    # TODO: Check if user has 'admin' permission on this tenant
    
    return handler.get_resource_permissions(
        resource_type="tenants",
        resource_id=tenant_id,
        tenant_id=tenant_id  # Self-referential
    )


@router.put(
    "/{tenant_id}/permissions",
    response_model=ResourcePermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Tenant Permissions",
    description="Set permissions for a tenant (replaces existing)"
)
@authenticate
async def set_tenant_permissions(
    request: Request,
    tenant_id: str,
    permission_data: SetPermissionsRequest,
    handler: PermissionHandler = Depends(get_permission_handler)
) -> ResourcePermissionsResponse:
    """
    Set permissions for a tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        permission_data: Permission assignments
        handler: Permission handler dependency
    
    Returns:
        ResourcePermissionsResponse: Updated permissions
    """
    user: IdentityUser = request.state.user
    user_id = user.identity.get_id()
    # TODO: Check if user has 'admin' permission on this tenant
    
    return handler.set_resource_permissions(
        resource_type="tenants",
        resource_id=tenant_id,
        tenant_id=tenant_id,  # Self-referential
        request=permission_data,
        user_id=user_id
    )


@router.delete(
    "/{tenant_id}/permissions",
    response_model=ResourcePermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Tenant Permissions",
    description="Delete permissions for a specific user/group on a tenant"
)
@authenticate
async def delete_tenant_permissions(
    request: Request,
    tenant_id: str,
    permission_data: DeletePermissionRequest,
    handler: PermissionHandler = Depends(get_permission_handler)
) -> ResourcePermissionsResponse:
    """
    Delete permissions for a specific user/group on a tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        permission_data: Entity to remove permissions for
        handler: Permission handler dependency
    
    Returns:
        ResourcePermissionsResponse: Updated permissions
    """
    user: IdentityUser = request.state.user
    # TODO: Check if user has 'admin' permission on this tenant
    
    return handler.delete_resource_permission(
        resource_type="tenants",
        resource_id=tenant_id,
        tenant_id=tenant_id,  # Self-referential
        request=permission_data
    )
