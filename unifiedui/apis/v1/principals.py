"""Principals API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, Request

from unifiedui.handlers.principals import PrincipalHandler
from unifiedui.handlers.dependencies.principals import get_principal_handler
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.core.database.enums import TenantRolesEnum
from unifiedui.schema.requests.principals import (
    TenantRefreshPrincipalRequest,
    UpdatePrincipalStatusRequest
)
from unifiedui.schema.requests.tenants import (
    SetPrincipalRequest,
    DeletePrincipalRequest
)
from unifiedui.schema.responses.principals import PrincipalResponse
from unifiedui.schema.responses.tenants import (
    TenantPrincipalsResponse,
    PrincipalsResponse
)


router = APIRouter()


# Tenant Principal Role Management Routes

@router.get(
    "",
    response_model=TenantPrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Tenant Principals",
    description="Get all principals and their roles for a tenant with optional filtering, search, and pagination"
)
@authenticate()
async def list_tenant_principals(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: Optional[str] = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: Optional[str] = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: Optional[bool] = Query(None, description="Filter by is_active status"),
    order_by: Optional[str] = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: Optional[str] = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: PrincipalHandler = Depends(get_principal_handler)
) -> TenantPrincipalsResponse:
    """
    Get all principals and their roles for a specific tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        skip: Number of principals to skip (for pagination)
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated list of roles to filter by (OR logic)
        is_active: Filter by principal's active status
        order_by: Column to order by (currently only 'display_name')
        order_direction: Sort direction ('asc' or 'desc')
        handler: Principal handler dependency
    
    Returns:
        TenantPrincipalsResponse: All principals with their roles on the tenant
    
    Raises:
        TenantNotFoundError: If tenant not found
    """
    # Parse comma-separated roles
    roles_list = [r.strip() for r in roles.split(",")] if roles else None
    
    return handler.list_tenant_principals(
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
        search=search,
        roles=roles_list,
        is_active=is_active,
        order_by=order_by,
        order_direction=order_direction
    )


@router.get(
    "/{principal_id}",
    response_model=PrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Principal Roles",
    description="Get all roles for a specific principal on a tenant"
)
@authenticate()
async def get_principal_permissions(
    request: Request,
    tenant_id: str,
    principal_id: str,
    handler: PrincipalHandler = Depends(get_principal_handler)
) -> PrincipalsResponse:
    """
    Get all roles for a specific principal on a tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        principal_id: The ID of the principal
        handler: Principal handler dependency
    
    Returns:
        PrincipalsResponse: Principal's roles on the tenant
    
    Raises:
        TenantNotFoundError: If tenant not found
    """
    result = handler.get_principal_permissions(tenant_id, principal_id)
    return PrincipalsResponse(**result)


@router.put(
    "",
    response_model=PrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Principal Role",
    description="Add or update a role for a principal on a tenant"
)
@authenticate()
@check_permissions(entity="tenant", required_permissions=[TenantRolesEnum.GLOBAL_ADMIN])
async def set_principal_permission(
    request: Request,
    tenant_id: str,
    role_data: SetPrincipalRequest,
    handler: PrincipalHandler = Depends(get_principal_handler)
) -> PrincipalsResponse:
    """
    Add or update a role for a principal on a tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        role_data: Role data to set
        handler: Principal handler dependency
    
    Returns:
        PrincipalsResponse: Updated principal's roles on the tenant
    
    Raises:
        TenantNotFoundError: If tenant not found
    """
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    
    result = handler.set_principal_permission(
        tenant_id=tenant_id,
        principal_id=role_data.principal_id,
        principal_type=role_data.principal_type,
        permission=role_data.role,
        user_id=user_id,
        user=user
    )
    return PrincipalsResponse(**result)


@router.delete(
    "",
    response_model=PrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Principal Role",
    description="Remove a specific role from a principal on a tenant"
)
@authenticate()
@check_permissions(entity="tenant", required_permissions=[TenantRolesEnum.GLOBAL_ADMIN])
async def delete_principal_permission(
    request: Request,
    tenant_id: str,
    role_data: DeletePrincipalRequest,
    handler: PrincipalHandler = Depends(get_principal_handler)
) -> PrincipalsResponse:
    """
    Remove a specific role from a principal on a tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        role_data: Role data to delete
        handler: Principal handler dependency
    
    Returns:
        PrincipalsResponse: Remaining principal's roles on the tenant
    
    Raises:
        TenantNotFoundError: If tenant not found
    """
    result = handler.delete_principal_permission(
        tenant_id=tenant_id,
        principal_id=role_data.principal_id,
        principal_type=role_data.principal_type,
        permission=role_data.role
    )
    return PrincipalsResponse(**result)


# Principal Entity Operations

@router.patch(
    "/{principal_id}/refresh",
    response_model=PrincipalResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Principal",
    description="Refresh a principal's data from the identity provider"
)
@authenticate()
@check_permissions(entity="tenant", required_permissions=[TenantRolesEnum.GLOBAL_ADMIN])
async def refresh_principal(
    request: Request,
    tenant_id: str,
    principal_id: str,
    body: TenantRefreshPrincipalRequest,
    handler: PrincipalHandler = Depends(get_principal_handler)
) -> PrincipalResponse:
    """
    Refresh a principal's data from the identity provider.
    
    This fetches the latest user/group information from the identity provider
    and updates the local principal record.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        principal_id: The ID of the principal to refresh
        body: Request containing the principal type
        handler: Principal handler dependency
    
    Returns:
        PrincipalResponse: The refreshed principal data
    
    Raises:
        PermissionDeniedError: If user doesn't have GLOBAL_ADMIN role
        ValueError: If principal type is invalid
    """
    user: ContextIdentityUser = request.state.user
    return handler.refresh_principal(
        tenant_id=tenant_id,
        principal_id=principal_id,
        principal_type=body.principal_type,
        user=user
    )


@router.patch(
    "/{principal_id}/status",
    response_model=PrincipalResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Principal Status",
    description="Update a principal's is_active status (GLOBAL_ADMIN only)"
)
@authenticate()
@check_permissions(entity="tenant", required_permissions=[TenantRolesEnum.GLOBAL_ADMIN])
async def update_principal_status(
    request: Request,
    tenant_id: str,
    principal_id: str,
    body: UpdatePrincipalStatusRequest,
    handler: PrincipalHandler = Depends(get_principal_handler)
) -> PrincipalResponse:
    """
    Update a principal's is_active status.
    
    Only GLOBAL_ADMIN users can activate/deactivate principals.
    Deactivated principals cannot access any resources in the tenant.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant
        principal_id: The ID of the principal to update
        body: Request containing the new is_active status
        handler: Principal handler dependency
    
    Returns:
        PrincipalResponse: The updated principal data
    
    Raises:
        PermissionDeniedError: If user doesn't have GLOBAL_ADMIN role
        ValueError: If principal is not found
    """
    return handler.update_principal_status(
        tenant_id=tenant_id,
        principal_id=principal_id,
        is_active=body.is_active
    )
