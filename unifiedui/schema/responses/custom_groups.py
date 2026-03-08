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
