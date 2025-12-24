"""API routes for development platform management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response

from aihub.core.identity.users import ContextIdentityUser
from aihub.handlers.development_platforms import DevelopmentPlatformHandler
from aihub.handlers.dependencies import get_development_platform_handler
from aihub.schema.requests.development_platforms import CreateDevelopmentPlatformRequest, UpdateDevelopmentPlatformRequest
from aihub.schema.requests.development_platform_permissions import SetDevelopmentPlatformPermissionRequest
from aihub.schema.responses.development_platforms import DevelopmentPlatformResponse
from aihub.schema.responses.development_platform_permissions import (
    DevelopmentPlatformPermissionResponse,
    DevelopmentPlatformPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.development_platforms import DevelopmentPlatformNotFoundError
from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.database.enums import TenantPermissionEnum, PermissionActionEnum
from aihub.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/development-platforms"
)


@router.get(
    "",
    response_model=List[DevelopmentPlatformResponse],
    summary="List development platforms",
    description="Get a paginated list of development platforms for the current tenant"
)
@authenticate
async def list_development_platforms(
    request: Request,
    tenant_id: str,
    skip: int = 0,
    limit: int = 100,
    name_filter: Optional[str] = None,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> List[DevelopmentPlatformResponse]:
    """
    List development platforms for a tenant.
    
    Users see only development platforms they have permissions for, unless they have
    GLOBAL_ADMIN or DEVELOPMENT_PLATFORMS_ADMIN on tenant level.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name_filter: Optional filter by development platform name
        handler: Development platform handler dependency
        
    Returns:
        List of development platforms
    """
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: List development platforms",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit
            }
        )
        
        return handler.list_development_platforms(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name_filter,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to list development platforms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list development platforms"
        )


@router.post(
    "",
    response_model=DevelopmentPlatformResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create development platform",
    description="Create a new development platform"
)
@authenticate
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_CREATOR
    ]
)
async def create_development_platform(
    request: Request,
    tenant_id: str,
    create_request: CreateDevelopmentPlatformRequest,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> DevelopmentPlatformResponse:
    """
    Create a new development platform.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Development platform creation data
        handler: Development platform handler dependency
        
    Returns:
        Created development platform
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create development platform",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "dp_name": create_request.name
            }
        )
        return handler.create_development_platform(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id()
        )
    except Exception as e:
        logger.error(f"Failed to create development platform: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create development platform: {str(e)}"
        )


@router.get(
    "/{development_platform_id}",
    response_model=DevelopmentPlatformResponse,
    summary="Get development platform",
    description="Get a specific development platform by ID"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_development_platform(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> DevelopmentPlatformResponse:
    """
    Get a specific development platform.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        development_platform_id: Development platform ID from path
        handler: Development platform handler dependency
        
    Returns:
        Development platform details
        
    Raises:
        HTTPException: If development platform not found or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get development platform",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_development_platform(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id
        )
    except DevelopmentPlatformNotFoundError as e:
        logger.warning(f"Development platform not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get development platform: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get development platform"
        )


@router.patch(
    "/{development_platform_id}",
    response_model=DevelopmentPlatformResponse,
    summary="Update development platform",
    description="Update an existing development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def update_development_platform(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    update_request: UpdateDevelopmentPlatformRequest,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> DevelopmentPlatformResponse:
    """
    Update a development platform.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        development_platform_id: Development platform ID from path
        update_request: Development platform update data
        handler: Development platform handler dependency
        
    Returns:
        Updated development platform
        
    Raises:
        HTTPException: If development platform not found or update fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update development platform",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.update_development_platform(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id,
            request=update_request,
            user_id=user.identity.get_id()
        )
    except DevelopmentPlatformNotFoundError as e:
        logger.warning(f"Development platform not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update development platform: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update development platform: {str(e)}"
        )


@router.delete(
    "/{development_platform_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete development platform",
    description="Delete a development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_development_platform(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> Response:
    """
    Delete a development platform.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        development_platform_id: Development platform ID from path
        handler: Development platform handler dependency
        
    Returns:
        No content (204)
        
    Raises:
        HTTPException: If development platform not found or deletion fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete development platform",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_development_platform(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except DevelopmentPlatformNotFoundError as e:
        logger.warning(f"Development platform not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete development platform: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete development platform"
        )


# ========== Development Platform Permission Endpoints ==========

@router.get(
    "/{development_platform_id}/principals",
    response_model=DevelopmentPlatformPrincipalsResponse,
    summary="List development platform permissions",
    description="Get all principals with permissions for a development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def list_development_platform_permissions(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> DevelopmentPlatformPrincipalsResponse:
    """
    List all permissions for a development platform.
    
    Requires ADMIN permission on the development platform or DEVELOPMENT_PLATFORMS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        development_platform_id: Development platform ID from path
        handler: Development platform handler dependency
        
    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List development platform permissions",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.list_development_platform_permissions(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id
        )
    except DevelopmentPlatformNotFoundError as e:
        logger.warning(f"Development platform not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list development platform permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list development platform permissions"
        )


@router.get(
    "/{development_platform_id}/principals/{principal_id}",
    response_model=PrincipalPermissionsResponse,
    summary="Get development platform permissions for principal",
    description="Get all permissions for a specific principal on a development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_development_platform_permission(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    principal_id: str,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> PrincipalPermissionsResponse:
    """
    Get all permissions for a specific principal on a development platform.
    
    Requires ADMIN permission on the development platform or DEVELOPMENT_PLATFORMS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        development_platform_id: Development platform ID from path
        principal_id: Principal ID from path
        handler: Development platform handler dependency
        
    Returns:
        Principal with all their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get development platform permission",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_development_platform_permission(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id,
            principal_id=principal_id
        )
    except DevelopmentPlatformNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get development platform permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get development platform permission"
        )


@router.put(
    "/{development_platform_id}/principals",
    response_model=DevelopmentPlatformPermissionResponse,
    summary="Set development platform permission",
    description="Set or update a principal's permission for a development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def set_development_platform_permission(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    permission_request: SetDevelopmentPlatformPermissionRequest,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> DevelopmentPlatformPermissionResponse:
    """
    Set or update a development platform permission.
    
    Requires ADMIN permission on the development platform or DEVELOPMENT_PLATFORMS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        development_platform_id: Development platform ID from path
        permission_request: Permission data
        handler: Development platform handler dependency
        
    Returns:
        Created or updated permission
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set development platform permission",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "principal_id": permission_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.set_development_platform_permission(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id,
            request=permission_request,
            user_id=user.identity.get_id()
        )
    except DevelopmentPlatformNotFoundError as e:
        logger.warning(f"Development platform not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set development platform permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set development platform permission: {str(e)}"
        )


@router.delete(
    "/{development_platform_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete development platform permission",
    description="Remove a principal's permission for a development platform"
)
@authenticate
@check_permissions(
    entity="development_platform",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.DEVELOPMENT_PLATFORMS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_development_platform_permission(
    request: Request,
    tenant_id: str,
    development_platform_id: str,
    delete_request: SetDevelopmentPlatformPermissionRequest,
    handler: DevelopmentPlatformHandler = Depends(get_development_platform_handler)
) -> Response:
    """
    Delete a development platform permission.
    
    Requires ADMIN permission on the development platform or DEVELOPMENT_PLATFORMS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        development_platform_id: Development platform ID from path
        delete_request: Permission deletion data (principal_id, principal_type, permission)
        handler: Development platform handler dependency
        
    Returns:
        No content (204)
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete development platform permission",
            extra={
                "tenant_id": tenant_id,
                "development_platform_id": development_platform_id,
                "principal_id": delete_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_development_platform_permission(
            tenant_id=tenant_id,
            development_platform_id=development_platform_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            permission=delete_request.role.value
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except DevelopmentPlatformNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete development platform permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete development platform permission"
        )
