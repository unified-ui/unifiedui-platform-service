from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

# filepath: /Users/enricogoerlitz/Developer/repos/aihub/aihub/schema/responses/tenants.py


class TenantResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the tenant")
    name: str = Field(..., description="Name of the tenant")
    description: str | None = Field(None, description="Optional description of the tenant")
    created_at: datetime = Field(..., description="Timestamp when the tenant was created")
    updated_at: datetime = Field(..., description="Timestamp when the tenant was last updated")
    created_by: str | None = Field(None, description="User ID who created this tenant")
    updated_by: str | None = Field(None, description="User ID who last updated this tenant")


class TenantPermissionResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the permission")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    permission: str = Field(..., description="Permission type (e.g., GLOBAL_ADMIN, READER)")
    name: str = Field(..., description="Name of the permission")
    description: str | None = Field(None, description="Optional description of the permission")
    created_at: datetime = Field(..., description="Timestamp when the permission was created")


class TenantWithPermissionsResponse(BaseModel):
    tenant: TenantResponse = Field(..., description="Tenant information")
    permissions: List[TenantPermissionResponse] = Field(..., description="List of permissions the principal has on this tenant")


class PrincipalsResponse(BaseModel):
    """Response containing all permissions for a principal on a specific tenant."""
    tenant_id: str = Field(..., description="The tenant ID")
    principal_id: str = Field(..., description="The principal ID")
    permissions: List[TenantPermissionResponse] = Field(..., description="List of permissions the principal has on this tenant")


class TenantPrincipalsResponse(BaseModel):
    """Response containing all principals and their permissions for a tenant."""
    tenant_id: str = Field(..., description="The tenant ID")
    principals: List[dict] = Field(..., description="List of principals with their permissions")
