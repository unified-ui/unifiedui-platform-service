"""Response schemas for development platforms."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from aihub.schema.responses.tags import TagSummary


class DevelopmentPlatformResponse(BaseModel):
    """Response model for a development platform."""
    
    id: str = Field(..., description="Development platform ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Development platform name")
    description: Optional[str] = Field(None, description="Development platform description")
    type: Optional[str] = Field(None, description="Type of development platform")
    iframe_url: str = Field(..., description="URL for the iframe embedding")
    config: dict = Field(default_factory=dict, description="Development platform configuration")
    is_active: bool = Field(..., description="Whether the development platform is active")
    tags: List[TagSummary] = Field(default_factory=list, description="Tags on the development platform")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    model_config = ConfigDict(from_attributes=True)
