"""Response schemas for custom groups."""
from datetime import datetime
from pydantic import BaseModel, Field


class CustomGroupResponse(BaseModel):
    """Response model for a custom group."""
    
    id: str = Field(..., description="Group ID")
    tenant_id: str = Field(..., description="Tenant ID this group belongs to")
    name: str = Field(..., description="Group name")
    description: str | None = Field(default=None, description="Group description")
    member_ids: list[str] = Field(default_factory=list, description="List of member user IDs")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    created_by: str = Field(..., description="User ID who created this group")
    updated_by: str = Field(..., description="User ID who last updated this group")
