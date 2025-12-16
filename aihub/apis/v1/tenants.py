"""Tenants API endpoints."""
from typing import Optional
from fastapi import APIRouter, status, HTTPException, Query, Depends

from aihub.database.client import DatabaseClient
from aihub.database.dependencies import get_db_client
from aihub.core.database.models.tenants import TenantModel
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest
from aihub.schema.responses.tenants import TenantResponse, TenantsListResponse


router = APIRouter()


@router.get(
    "",
    response_model=list[TenantResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tenants",
    description="Get a paginated list of tenants"
)
async def list_tenants(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: Optional[str] = Query(None, description="Filter by tenant name"),
    db_client: DatabaseClient = Depends(get_db_client)
) -> list[TenantResponse]:
    """
    Get a paginated list of tenants.
    
    Args:
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        name: Optional filter by tenant name
        db_client: Database client dependency
    
    Returns:
        list[TenantResponse]: List of tenants
    """
    try:
        # Build filters
        filters = {}
        if name:
            filters["name"] = {"$regex": name, "$options": "i"}  # Case-insensitive search
        
        # Get tenants
        tenants = db_client.tenants.get_list(filters=filters, skip=skip, limit=limit)
        
        # Convert to response models
        tenant_responses = [
            TenantResponse(
                id=tenant.id,
                name=tenant.name,
                description=tenant.description,
                meta=tenant.meta,
                created_at=tenant.created_at,
                updated_at=tenant.updated_at
            )
            for tenant in tenants
        ]
        
        return tenant_responses
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
async def get_tenant(
    tenant_id: str,
    db_client: DatabaseClient = Depends(get_db_client)
) -> TenantResponse:
    """
    Get a specific tenant by ID.
    
    Args:
        tenant_id: The ID of the tenant to retrieve
        db_client: Database client dependency
    
    Returns:
        TenantResponse: The tenant information
    
    Raises:
        HTTPException: If tenant not found
    """
    try:
        tenant = db_client.tenants.get(tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with ID '{tenant_id}' not found"
            )
        
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            meta=tenant.meta,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )
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
async def create_tenant(
    request: CreateTenantRequest,
    db_client: DatabaseClient = Depends(get_db_client)
) -> TenantResponse:
    """
    Create a new tenant.
    
    Args:
        request: Tenant creation data
        db_client: Database client dependency
    
    Returns:
        TenantResponse: The created tenant
    """
    try:
        # Create tenant model
        tenant = TenantModel(
            name=request.name,
            description=request.description,
            meta=request.meta
        )
        
        # Save to database
        created_tenant = db_client.tenants.create(tenant)
        
        return TenantResponse(
            id=created_tenant.id,
            name=created_tenant.name,
            description=created_tenant.description,
            meta=created_tenant.meta,
            created_at=created_tenant.created_at,
            updated_at=created_tenant.updated_at
        )
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
async def update_tenant(
    tenant_id: str,
    request: UpdateTenantRequest,
    db_client: DatabaseClient = Depends(get_db_client)
) -> TenantResponse:
    """
    Update an existing tenant.
    
    Args:
        tenant_id: The ID of the tenant to update
        request: Tenant update data
        db_client: Database client dependency
    
    Returns:
        TenantResponse: The updated tenant
    
    Raises:
        HTTPException: If tenant not found
    """
    try:
        # Build update data (only include provided fields)
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.meta is not None:
            update_data["meta"] = request.meta
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Update tenant
        updated_tenant = db_client.tenants.update(tenant_id, update_data)
        
        if not updated_tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with ID '{tenant_id}' not found"
            )
        
        return TenantResponse(
            id=updated_tenant.id,
            name=updated_tenant.name,
            description=updated_tenant.description,
            meta=updated_tenant.meta,
            created_at=updated_tenant.created_at,
            updated_at=updated_tenant.updated_at
        )
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
async def delete_tenant(
    tenant_id: str,
    db_client: DatabaseClient = Depends(get_db_client)
) -> None:
    """
    Delete a tenant by ID.
    
    Args:
        tenant_id: The ID of the tenant to delete
        db_client: Database client dependency
    
    Raises:
        HTTPException: If tenant not found
    """
    try:
        success = db_client.tenants.delete(tenant_id)
        
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
