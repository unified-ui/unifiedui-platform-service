"""Response schemas for external apps."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExternalAppResponse(BaseModel):
    """Response model for an external app."""

    id: str = Field(..., description="External app ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="External app name")
    description: str | None = Field(None, description="External app description")
    url: str = Field(..., description="External app URL for iframe embedding")
    image_url: str | None = Field(None, description="External app image URL")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")

    model_config = ConfigDict(from_attributes=True)
