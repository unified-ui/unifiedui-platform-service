"""Response schemas for applications."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from aihub.core.database.enums import ApplicationTypeEnum
from aihub.schema.responses.tags import TagSummary


class ApplicationResponse(BaseModel):
    """Response model for an application."""
    
    id: str = Field(..., description="Application ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Application name")
    description: Optional[str] = Field(None, description="Application description")
    type: ApplicationTypeEnum = Field(..., description="Application type")
    config: dict = Field(default_factory=dict, description="Application configuration")
    is_active: bool = Field(..., description="Whether the application is active")
    tags: List[TagSummary] = Field(default_factory=list, description="Tags on the application")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    model_config = ConfigDict(from_attributes=True)
