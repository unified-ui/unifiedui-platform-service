"""API routes for application management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import Response

from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.handlers.applications import ApplicationHandler
from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.handlers.dependencies import get_application_handler, get_credential_handler
from unifiedui.schema.requests.applications import CreateApplicationRequest, UpdateApplicationRequest
from unifiedui.schema.requests.application_permissions import SetApplicationPermissionRequest
from unifiedui.schema.responses.applications import ApplicationResponse, ApplicationConfigResponse
from unifiedui.schema.responses.principals import (
    PrincipalWithRolesResponse,
    ResourcePrincipalsResponse
)
from unifiedui.exc.applications import ApplicationNotFoundError
from unifiedui.exc.application_config import (
    ApplicationConfigValidationError,
    UnsupportedApplicationTypeError,
    InvalidCredentialError
)
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.core.database.enums import TenantRolesEnum, PermissionActionEnum, OrderDirectionEnum, ListViewEnum
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/applications"
)


@router.get(
    "",
    summary="List applications",
    description="Get a paginated list of applications for the current tenant. Use view=quick-list to get only id and name."
)
@authenticate()
async def list_applications(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: Optional[str] = Query(None, description="Filter by application name"),
    is_active: Optional[int] = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tag IDs to filter by (e.g., '10001,10002,10003')"),
    order_by: Optional[str] = Query(None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"),
    order_direction: Optional[OrderDirectionEnum] = Query(None, description="Sort direction: 'asc' or 'desc'"),
    view: Optional[ListViewEnum] = Query(None, description="View type: 'full' (default) or 'quick-list' (returns only id and name)"),
    handler: ApplicationHandler = Depends(get_application_handler)
):
    """
    List applications for a tenant.
    
    Users see only applications they have permissions for, unless they have
    GLOBAL_ADMIN or APPLICATIONS_ADMIN on tenant level.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name: Optional filter by application name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        tags: Optional comma-separated tag IDs to filter by
        handler: Application handler dependency
        
    Returns:
        List of applications
    """
    try:
        user: ContextIdentityUser = request.state.user
        
        # Parse tag IDs from comma-separated string
        tag_ids = None
        if tags:
            try:
                tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tag IDs format. Must be comma-separated integers."
                )
        
        logger.info(
            "API: List applications",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit,
                "tags": tag_ids
            }
        )
        
        return handler.list_applications(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name,
            is_active=is_active,
            tag_ids=tag_ids,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
            view=view.value if view else None,
            user=user
        )
    except HTTPException:
        raise
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
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
        TenantRolesEnum.APPLICATIONS_CREATOR
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
            user_id=user.identity.get_id(),
            user=user
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
@authenticate()
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
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
@authenticate()
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
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
@authenticate()
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
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


# ========== Application Config Endpoint (for Agent Service) ==========

@router.get(
    "/{application_id}/config",
    response_model=ApplicationConfigResponse,
    summary="Get application config with credentials",
    description="Get the full application configuration including credential secrets and user data. For internal agent-service use. Requires X-Service-Key header."
)
@authenticate(required_service_auth_key="X_AGENT_SERVICE_KEY")
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def get_application_config(
    request: Request,
    tenant_id: str,
    application_id: str,
    handler: ApplicationHandler = Depends(get_application_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler)
) -> ApplicationConfigResponse:
    """
    Get the full application configuration including credential secrets.
    
    This endpoint is intended for the agent-service to fetch complete
    configuration including resolved credential secrets and user information.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        handler: Application handler dependency
        credential_handler: Credential handler dependency
        
    Returns:
        ApplicationConfigResponse with full config including secrets
        
    Raises:
        HTTPException: If application not found, credentials invalid, or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get application config",
            extra={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_application_config(
            tenant_id=tenant_id,
            application_id=application_id,
            user=user,
            credential_handler=credential_handler
        )
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InvalidCredentialError as e:
        logger.error(f"Invalid credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.message)
        )
    except Exception as e:
        logger.error(f"Failed to get application config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get application config: {str(e)}"
        )


# ========== Application Permission Endpoints ==========

@router.get(
    "/{application_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List application permissions",
    description="Get all principals with permissions for an application"
)
@authenticate()
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ
    ]
)
async def list_application_permissions(
    request: Request,
    tenant_id: str,
    application_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: Optional[str] = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: Optional[str] = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: Optional[bool] = Query(None, description="Filter by is_active status"),
    order_by: Optional[str] = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: Optional[str] = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: ApplicationHandler = Depends(get_application_handler)
) -> ResourcePrincipalsResponse:
    """
    List all permissions for an application.
    
    Requires ADMIN permission on the application or APPLICATIONS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        application_id: Application ID from path
        skip: Number of principals to skip
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated roles to filter by (OR logic)
        is_active: Filter by is_active status
        order_by: Column to order by
        order_direction: Sort direction
        handler: Application handler dependency
        
    Returns:
        Unified ResourcePrincipalsResponse with enriched principal data
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
        
        # Parse comma-separated roles
        roles_list = [r.strip() for r in roles.split(",")] if roles else None
        
        return handler.list_application_permissions(
            tenant_id=tenant_id,
            application_id=application_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction
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
    response_model=PrincipalWithRolesResponse,
    summary="Get application permissions for principal",
    description="Get all permissions for a specific principal on an application"
)
@authenticate()
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
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
) -> PrincipalWithRolesResponse:
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
        Unified PrincipalWithRolesResponse with enriched principal data
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
    response_model=PrincipalWithRolesResponse,
    summary="Set application permission",
    description="Set or update a principal's permission for an application"
)
@authenticate()
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
        PermissionActionEnum.ADMIN
    ]
)
async def set_application_permission(
    request: Request,
    tenant_id: str,
    application_id: str,
    permission_request: SetApplicationPermissionRequest,
    handler: ApplicationHandler = Depends(get_application_handler)
) -> PrincipalWithRolesResponse:
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
        Updated principal with their roles and enriched data
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
            user_id=user.identity.get_id(),
            user=user
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
@authenticate()
@check_permissions(
    entity="application",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.APPLICATIONS_ADMIN,
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
