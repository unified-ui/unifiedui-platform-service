"""API routes for application management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response

from aihub.core.identity.users import ContextIdentityUser
from aihub.handlers.applications import ApplicationHandler
from aihub.handlers.dependencies import get_application_handler
from aihub.schema.requests.applications import CreateApplicationRequest, UpdateApplicationRequest
from aihub.schema.requests.application_permissions import SetApplicationPermissionRequest
from aihub.schema.responses.applications import ApplicationResponse
from aihub.schema.responses.application_permissions import (
    ApplicationPermissionResponse,
    ApplicationPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.applications import ApplicationNotFoundError
from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.database.enums import TenantPermissionEnum, PermissionActionEnum
from aihub.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/applications"
)


@router.get(
    "",
    response_model=List[ApplicationResponse],
    summary="List applications",
    description="Get a paginated list of applications for the current tenant"
)
@authenticate
async def list_applications(
    request: Request,
    tenant_id: str,
    skip: int = 0,
    limit: int = 100,
    name_filter: Optional[str] = None,
    is_active: Optional[int] = None,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> List[ApplicationResponse]:
    """
    List applications for a tenant.
    
    Users see only applications they have permissions for, unless they have
    GLOBAL_ADMIN or APPLICATIONS_ADMIN on tenant level.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name_filter: Optional filter by application name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        handler: Application handler dependency
        
    Returns:
        List of applications
    """
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: List applications",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit
            }
        )
        
        return handler.list_applications(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name_filter,
            is_active=is_active,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to list applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list applications"
        )


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create application",
    description="Create a new application"
)
@authenticate
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        TenantPermissionEnum.APPLICATIONS_CREATOR
    ]
)
async def create_application(
    request: Request,
    tenant_id: str,
    create_request: CreateApplicationRequest,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> ApplicationResponse:
    """
    Create a new application.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Application creation data
        handler: Application handler dependency
        
    Returns:
        Created application
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create application",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "app_name": create_request.name
            }
        )
        return handler.create_application(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id()
        )
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create application: {str(e)}"
        )


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get application",
    description="Get a specific application by ID"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_application(
    request: Request,
    tenant_id: str,
    application_id: str,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> ApplicationResponse:
    """
    Get a specific application.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        handler: Application handler dependency
        
    Returns:
        Application details
        
    Raises:
        HTTPException: If application not found or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get application",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_application(
            tenant_id=tenant_id,
            application_id=application_id
        )
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get application"
        )


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Update application",
    description="Update an existing application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE
    ]
)
async def update_application(
    request: Request,
    tenant_id: str,
    application_id: str,
    update_request: UpdateApplicationRequest,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> ApplicationResponse:
    """
    Update an application.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        update_request: Application update data
        handler: Application handler dependency
        
    Returns:
        Updated application
        
    Raises:
        HTTPException: If application not found or update fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update application",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.update_application(
            tenant_id=tenant_id,
            application_id=application_id,
            request=update_request,
            user_id=user.identity.get_id()
        )
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application: {str(e)}"
        )


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete application",
    description="Delete an application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_application(
    request: Request,
    tenant_id: str,
    application_id: str,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> Response:
    """
    Delete an application.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        handler: Application handler dependency
        
    Returns:
        No content (204)
        
    Raises:
        HTTPException: If application not found or deletion fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete application",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_application(
            tenant_id=tenant_id,
            application_id=application_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete application"
        )


# ========== Application Permission Endpoints ==========

@router.get(
    "/{application_id}/principals",
    response_model=ApplicationPrincipalsResponse,
    summary="List application permissions",
    description="Get all principals with permissions for an application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def list_application_permissions(
    request: Request,
    tenant_id: str,
    application_id: str,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> ApplicationPrincipalsResponse:
    """
    List all permissions for an application.
    
    Requires ADMIN permission on the application or APPLICATIONS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        handler: Application handler dependency
        
    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List application permissions",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.list_application_permissions(
            tenant_id=tenant_id,
            application_id=application_id
        )
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list application permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list application permissions"
        )


@router.get(
    "/{application_id}/principals/{principal_id}",
    response_model=PrincipalPermissionsResponse,
    summary="Get application permissions for principal",
    description="Get all permissions for a specific principal on an application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_application_permission(
    request: Request,
    tenant_id: str,
    application_id: str,
    principal_id: str,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> PrincipalPermissionsResponse:
    """
    Get all permissions for a specific principal on an application.
    
    Requires ADMIN permission on the application or APPLICATIONS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        principal_id: Principal ID from path
        handler: Application handler dependency
        
    Returns:
        Principal with all their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get application permission",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_application_permission(
            tenant_id=tenant_id,
            application_id=application_id,
            principal_id=principal_id
        )
    except ApplicationNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get application permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get application permission"
        )


@router.put(
    "/{application_id}/principals",
    response_model=ApplicationPermissionResponse,
    summary="Set application permission",
    description="Set or update a principal's permission for an application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def set_application_permission(
    request: Request,
    tenant_id: str,
    application_id: str,
    permission_request: SetApplicationPermissionRequest,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> ApplicationPermissionResponse:
    """
    Set or update an application permission.
    
    Requires ADMIN permission on the application or APPLICATIONS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        permission_request: Permission data
        handler: Application handler dependency
        
    Returns:
        Created or updated permission
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set application permission",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "principal_id": permission_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.set_application_permission(
            tenant_id=tenant_id,
            application_id=application_id,
            request=permission_request,
            user_id=user.identity.get_id()
        )
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set application permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set application permission: {str(e)}"
        )


@router.delete(
    "/{application_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete application permission",
    description="Remove a principal's permission for an application"
)
@authenticate
@check_permissions(
    entity="application",
    required_permissions=[
        TenantPermissionEnum.GLOBAL_ADMIN,
        TenantPermissionEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def delete_application_permission(
    request: Request,
    tenant_id: str,
    application_id: str,
    delete_request: SetApplicationPermissionRequest,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> Response:
    """
    Delete an application permission.
    
    Requires ADMIN permission on the application or APPLICATIONS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        delete_request: Permission deletion data (principal_id, principal_type, permission)
        handler: Application handler dependency
        
    Returns:
        No content (204)
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete application permission",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "principal_id": delete_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_application_permission(
            tenant_id=tenant_id,
            application_id=application_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            permission=delete_request.role.value
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ApplicationNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete application permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete application permission"
        )
