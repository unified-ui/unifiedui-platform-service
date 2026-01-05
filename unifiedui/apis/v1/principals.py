"""Principals API endpoints."""
from fastapi import APIRouter, status, Depends, Request

from unifiedui.handlers.principals import PrincipalHandler
from unifiedui.handlers.dependencies.principals import get_principal_handler
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.core.database.enums import TenantRolesEnum
from unifiedui.schema.requests.principals import (
    TenantRefreshPrincipalRequest,
    UpdatePrincipalStatusRequest
)
from unifiedui.schema.responses.principals import PrincipalResponse


router = APIRouter()


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
