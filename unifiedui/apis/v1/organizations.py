"""Organization API endpoints."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from unifiedui.core.database.enums import OrganizationRoleEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.handlers.dependencies import get_organization_handler
from unifiedui.handlers.organizations import OrganizationHandler
from unifiedui.schema.requests.organizations import (
    CreateOrganizationRequest,
    CreateTenantInOrganizationRequest,
    DeleteOrganizationPrincipalRequest,
    SetOrganizationPrincipalRequest,
    UpdateOrganizationRequest,
)
from unifiedui.schema.responses.organizations import (
    OrganizationPrincipalRoleResponse,
    OrganizationPrincipalsResponse,
    OrganizationResponse,
    TenantWithOrganizationResponse,
)

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

router = APIRouter()

ORG_GLOBAL_ADMIN_ROLES = [
    OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value,
]

ORG_TENANT_MANAGE_ROLES = [
    OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value,
    OrganizationRoleEnum.ORGANISATION_TENANT_ADMIN.value,
]

ORG_ALL_ROLES = [role.value for role in OrganizationRoleEnum]


# ---------- Organization CRUD ----------


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Organization",
    description="Get a specific organization by ID",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_ALL_ROLES)
async def get_organization(
    request: Request,
    organization_id: str,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> OrganizationResponse:
    """Get a specific organization by ID."""
    return handler.get_organization(organization_id)


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
    description="Create a new organization with a default tenant (restricted to system admin emails)",
)
@authenticate()
async def create_organization(
    request: Request,
    org_data: CreateOrganizationRequest,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> OrganizationResponse:
    """Create a new organization with a default tenant."""
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    profile = user._get_user_profile()
    user_mail = profile.mail or user.identity.get_mail()
    user_principal = profile.principal_name or user.identity.get_principal_name()

    from unifiedui.core.config import settings
    from unifiedui.core.identity.users import _is_system_admin

    idp = user.identity.get_identity_provider()
    if not _is_system_admin(idp, user_mail, user_principal, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only system administrators can create organizations",
        )

    return handler.create_organization(org_data, user_id, user=user)


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Organization",
    description="Update an existing organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_GLOBAL_ADMIN_ROLES)
async def update_organization(
    request: Request,
    organization_id: str,
    org_data: UpdateOrganizationRequest,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> OrganizationResponse:
    """Update an existing organization."""
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    return handler.update_organization(organization_id, org_data, user_id)


# ---------- Organization Principals ----------


@router.get(
    "/{organization_id}/principals",
    response_model=OrganizationPrincipalsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Organization Principals",
    description="List all principals of an organization with optional search and pagination",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_GLOBAL_ADMIN_ROLES)
async def list_organization_principals(
    request: Request,
    organization_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> OrganizationPrincipalsResponse:
    """List all principals of an organization."""
    return handler.list_principals(
        organization_id,
        skip=skip,
        limit=limit,
        search=search,
        order_by=order_by,
        order_direction=order_direction,
    )


@router.post(
    "/{organization_id}/principals",
    response_model=OrganizationPrincipalRoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set Organization Principal",
    description="Add or set a principal role in the organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_GLOBAL_ADMIN_ROLES)
async def set_organization_principal(
    request: Request,
    organization_id: str,
    principal_data: SetOrganizationPrincipalRequest,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> OrganizationPrincipalRoleResponse:
    """Add or set a principal role in the organization."""
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    return handler.set_principal(organization_id, principal_data, user_id)


@router.delete(
    "/{organization_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Organization Principal",
    description="Remove a principal role from the organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_GLOBAL_ADMIN_ROLES)
async def delete_organization_principal(
    request: Request,
    organization_id: str,
    principal_data: DeleteOrganizationPrincipalRequest,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> None:
    """Remove a principal role from the organization."""
    handler.delete_principal(organization_id, principal_data)


# ---------- Organization Tenants ----------


@router.get(
    "/{organization_id}/tenants",
    response_model=list[TenantWithOrganizationResponse],
    status_code=status.HTTP_200_OK,
    summary="List Organization Tenants",
    description="List all tenants in an organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_ALL_ROLES)
async def list_organization_tenants(
    request: Request,
    organization_id: str,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> list[TenantWithOrganizationResponse]:
    """List all tenants in an organization."""
    return handler.list_tenants(organization_id)


@router.post(
    "/{organization_id}/tenants",
    response_model=TenantWithOrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Tenant in Organization",
    description="Create a new tenant within an organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_ALL_ROLES)
async def create_tenant_in_organization(
    request: Request,
    organization_id: str,
    tenant_data: CreateTenantInOrganizationRequest,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> TenantWithOrganizationResponse:
    """Create a new tenant within an organization."""
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    return handler.create_tenant(organization_id, tenant_data, user_id, user)


@router.delete(
    "/{organization_id}/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Tenant in Organization",
    description="Delete a tenant within an organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_TENANT_MANAGE_ROLES)
async def delete_tenant_in_organization(
    request: Request,
    organization_id: str,
    tenant_id: str,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> None:
    """Delete a tenant within an organization (respecting can_be_deleted flag)."""
    handler.delete_tenant_in_organization(organization_id, tenant_id)
