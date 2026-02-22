"""Organization API endpoints."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status

from unifiedui.core.database.enums import OrganizationRoleEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.handlers.dependencies import get_organization_handler
from unifiedui.handlers.organizations import OrganizationHandler
from unifiedui.schema.requests.organizations import (
    CreateOrganizationRequest,
    CreateTenantInOrganizationRequest,
    DeleteOrganizationMemberRequest,
    SetOrganizationMemberRequest,
    UpdateOrganizationRequest,
)
from unifiedui.schema.responses.organizations import (
    OrganizationMemberRoleResponse,
    OrganizationMembersResponse,
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
    user_mail = user.identity.get_mail()

    from unifiedui.core.config import settings

    if settings.system_admin_email and (not user_mail or user_mail != settings.system_admin_email):
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


# ---------- Organization Members ----------


@router.get(
    "/{organization_id}/members",
    response_model=OrganizationMembersResponse,
    status_code=status.HTTP_200_OK,
    summary="List Organization Members",
    description="List all members of an organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_GLOBAL_ADMIN_ROLES)
async def list_organization_members(
    request: Request,
    organization_id: str,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> OrganizationMembersResponse:
    """List all members of an organization."""
    return handler.list_members(organization_id)


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberRoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set Organization Member",
    description="Add or set a member role in the organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_GLOBAL_ADMIN_ROLES)
async def set_organization_member(
    request: Request,
    organization_id: str,
    member_data: SetOrganizationMemberRequest,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> OrganizationMemberRoleResponse:
    """Add or set a member role in the organization."""
    user: ContextIdentityUser = request.state.user
    user_id = user.identity.get_id()
    return handler.set_member(organization_id, member_data, user_id)


@router.delete(
    "/{organization_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Organization Member",
    description="Remove a member role from the organization",
)
@authenticate()
@check_permissions(entity="organization", required_org_roles=ORG_GLOBAL_ADMIN_ROLES)
async def delete_organization_member(
    request: Request,
    organization_id: str,
    member_data: DeleteOrganizationMemberRequest,
    handler: OrganizationHandler = Depends(get_organization_handler),
) -> None:
    """Remove a member role from the organization."""
    handler.delete_member(organization_id, member_data)


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
