"""Response schemas for external apps."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.schema.responses.tags import TagSummary


class ExternalAppResponse(BaseModel):
    """Response model for an external app."""

    id: str = Field(..., description="External app ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="External app name")
    description: str | None = Field(None, description="External app description")
    config: dict[str, Any] = Field(..., description="External app configuration (mode-specific schema)")
    image_url: str | None = Field(None, description="External app image URL")
    image_file_id: str | None = Field(None, description="File ID of uploaded app image")
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the external app")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")

    model_config = ConfigDict(from_attributes=True)
