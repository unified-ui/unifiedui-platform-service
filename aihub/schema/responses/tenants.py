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


class TenantRoleResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the role")
    role: str = Field(..., description="Role type (e.g., GLOBAL_ADMIN, READER)")
    name: str = Field(..., description="Name of the role")
    description: str | None = Field(None, description="Optional description of the role")
    created_at: datetime = Field(..., description="Timestamp when the role was created")


class TenantWithRolesResponse(BaseModel):
    tenant: TenantResponse = Field(..., description="Tenant information")
    roles: List[TenantRoleResponse] = Field(..., description="List of roles the principal has on this tenant")
