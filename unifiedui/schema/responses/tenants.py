from datetime import datetime

from pydantic import BaseModel, Field

# filepath: /Users/enricogoerlitz/Developer/repos/unifiedui/unifiedui/schema/responses/tenants.py


class TenantResponse(BaseModel):
    """Response schema for a tenant."""

    id: str = Field(..., description="Unique identifier for the tenant")
    name: str = Field(..., description="Name of the tenant")
    description: str | None = Field(None, description="Optional description of the tenant")
    organization_id: str = Field(..., description="ID of the parent organization")
    environment_type: str = Field("SANDBOX", description="Environment type (SANDBOX or PRODUCTION)")
    is_default: bool = Field(False, description="Whether this is the default tenant")
    can_be_deleted: bool = Field(True, description="Whether this tenant can be deleted")
    created_at: datetime = Field(..., description="Timestamp when the tenant was created")
    updated_at: datetime = Field(..., description="Timestamp when the tenant was last updated")
    created_by: str | None = Field(None, description="User ID who created this tenant")
    updated_by: str | None = Field(None, description="User ID who last updated this tenant")


class TenantRoleDetailResponse(BaseModel):
    """Detailed role response including display name and creation info."""

    role: str = Field(..., description="Role type (e.g., TENANT_GLOBAL_ADMIN, READER)")
    display_name: str | None = Field(None, description="Human-readable role name")
    created_at: datetime | None = Field(None, description="When this role was assigned")


class TenantRoleResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the role")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    role: str = Field(..., description="Role type (e.g., TENANT_GLOBAL_ADMIN, READER)")
    name: str | None = Field(None, description="Name of the role (derived from role value)")
    description: str | None = Field(None, description="Optional description of the role")
    created_at: datetime = Field(..., description="Timestamp when the role was created")


class TenantWithRolesResponse(BaseModel):
    tenant: TenantResponse = Field(..., description="Tenant information")
    roles: list[TenantRoleResponse] = Field(..., description="List of roles the principal has on this tenant")


class TenantPrincipalResponse(BaseModel):
    """Response for a single principal with their roles on a tenant."""

    principal_id: str = Field(..., description="The principal ID")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    display_name: str | None = Field(None, description="Display name of the principal")
    principal_name: str | None = Field(None, description="Principal name (email for users)")
    mail: str | None = Field(None, description="Email address if available")
    description: str | None = Field(None, description="Description of the principal")
    is_active: bool = Field(True, description="Whether the principal is active")
    roles: list[TenantRoleDetailResponse] = Field(..., description="List of roles with details")


class PrincipalsResponse(BaseModel):
    """Response containing all roles for a principal on a specific tenant."""

    tenant_id: str = Field(..., description="The tenant ID")
    principal_id: str = Field(..., description="The principal ID")
    principal_type: str | None = Field(
        None, description="The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)"
    )
    is_active: bool = Field(True, description="Whether the principal is active")
    roles: list[str] = Field(..., description="List of roles the principal has on this tenant")


class TenantPrincipalsResponse(BaseModel):
    """Response containing all principals and their roles for a tenant."""

    tenant_id: str = Field(..., description="The tenant ID")
    principals: list[TenantPrincipalResponse] = Field(..., description="List of principals with their roles")
