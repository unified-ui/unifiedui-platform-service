"""Tenants API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, Request

from aihub.core.handlers.tenants import TenantHandler
from aihub.core.handlers.dependencies import get_tenant_handler
from aihub.core.middleware.apis.v1.auth import authenticate
from aihub.core.identity.users import IdentityUser
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse


router = APIRouter()


@router.get(
    "",
    response_model=list[TenantResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tenants",
    description="Get a paginated list of tenants"
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
    Get a paginated list of tenants.
    
    Args:
        request: FastAPI request object
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        name: Optional filter by tenant name
        handler: Tenant handler dependency
    
    Returns:
        list[TenantResponse]: List of tenants
    """
    return handler.list_tenants(
        skip=skip,
        limit=limit,
        name_filter=name
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
    description="Create a new tenant and assign creator as GLOBAL_ADMIN"
)
@authenticate
async def create_tenant(
    request: Request,
    tenant_data: CreateTenantRequest,
    handler: TenantHandler = Depends(get_tenant_handler)
) -> TenantResponse:
    """
    Create a new tenant and assign the creator as GLOBAL_ADMIN.
    
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
