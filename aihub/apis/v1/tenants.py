"""Tenants API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, HTTPException, Query, Depends, Request

from aihub.database.client import DatabaseClient
from aihub.database.dependencies import get_db_client
from aihub.core.handlers.tenants import TenantHandler
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
    db_client: DatabaseClient = Depends(get_db_client)
) -> list[TenantResponse]:
    """
    Get a paginated list of tenants.
    
    Args:
        request: FastAPI request object
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        name: Optional filter by tenant name
        db_client: Database client dependency
    
    Returns:
        list[TenantResponse]: List of tenants
    """
    try:
        handler = TenantHandler(db_client)
        
        # Build filters
        filters = {}
        if name:
            filters["name"] = {"$regex": name, "$options": "i"}
        
        return handler.list_tenants(filters=filters, skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tenants: {str(e)}"
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
    db_client: DatabaseClient = Depends(get_db_client)
) -> TenantResponse:
    """
    Get a specific tenant by ID.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant to retrieve
        db_client: Database client dependency
    
    Returns:
        TenantResponse: The tenant information
    
    Raises:
        HTTPException: If tenant not found
    """
    try:
        handler = TenantHandler(db_client)
        tenant = handler.get_tenant(tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with ID '{tenant_id}' not found"
            )
        
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tenant: {str(e)}"
        )


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Tenant",
    description="Create a new tenant"
)
@authenticate
async def create_tenant(
    http_request: Request,
    request: CreateTenantRequest,
    db_client: DatabaseClient = Depends(get_db_client)
) -> TenantResponse:
    """
    Create a new tenant.
    
    Args:
        http_request: FastAPI request object (contains user in request.state)
        request: Tenant creation data
        db_client: Database client dependency
    
    Returns:
        TenantResponse: The created tenant
    """
    try:
        user: IdentityUser = http_request.state.user
        user_id = user.identity.get_id()
        
        handler = TenantHandler(db_client)
        return handler.create_tenant(request, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant: {str(e)}"
        )


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Tenant",
    description="Update an existing tenant"
)
@authenticate
async def update_tenant(
    http_request: Request,
    tenant_id: str,
    request: UpdateTenantRequest,
    db_client: DatabaseClient = Depends(get_db_client)
) -> TenantResponse:
    """
    Update an existing tenant.
    
    Args:
        http_request: FastAPI request object (contains user in request.state)
        tenant_id: The ID of the tenant to update
        request: Tenant update data
        db_client: Database client dependency
    
    Returns:
        TenantResponse: The updated tenant
    
    Raises:
        HTTPException: If tenant not found
    """
    try:
        user: IdentityUser = http_request.state.user
        user_id = user.identity.get_id()
        
        handler = TenantHandler(db_client)
        updated_tenant = handler.update_tenant(tenant_id, request, user_id)
        
        if not updated_tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with ID '{tenant_id}' not found"
            )
        
        return updated_tenant
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant: {str(e)}"
        )


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
    db_client: DatabaseClient = Depends(get_db_client)
) -> None:
    """
    Delete a tenant by ID.
    
    Args:
        request: FastAPI request object
        tenant_id: The ID of the tenant to delete
        db_client: Database client dependency
    
    Raises:
        HTTPException: If tenant not found
    """
    try:
        handler = TenantHandler(db_client)
        success = handler.delete_tenant(tenant_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with ID '{tenant_id}' not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tenant: {str(e)}"
        )
