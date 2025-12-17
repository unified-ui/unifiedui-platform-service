"""Response schemas for custom groups."""
from datetime import datetime
from pydantic import BaseModel, Field


class CustomGroupResponse(BaseModel):
    """Response model for a custom group."""
    
    id: str = Field(..., description="Group ID")
    tenant_id: str = Field(..., description="Tenant ID this group belongs to")
    name: str = Field(..., description="Group name")
    description: str | None = Field(default=None, description="Group description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="User ID who created this group")
    updated_by: str | None = Field(None, description="User ID who last updated this group")


class CustomGroupPermissionResponse(BaseModel):
    """Response model for a custom group permission."""
    id: str = Field(..., description="Permission ID")
    principal_id: str = Field(..., description="Principal ID (user or group)")
    action: str = Field(..., description="Permission action (READ, WRITE, ADMIN)")
    created_at: datetime = Field(..., description="Creation timestamp")


class CustomGroupPermissionsResponse(BaseModel):
    """Response containing all permissions for a custom group."""
    custom_group_id: str = Field(..., description="The custom group ID")
    tenant_id: str = Field(..., description="The tenant ID")
    permissions: list[CustomGroupPermissionResponse] = Field(..., description="List of permissions")
