"""Request schemas for applications."""
from typing import Optional
from pydantic import BaseModel, Field

from unifiedui.core.database.enums import ApplicationTypeEnum


class CreateApplicationRequest(BaseModel):
    """Request model for creating an application."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Application name")
    description: Optional[str] = Field(None, max_length=2000, description="Application description")
    type: ApplicationTypeEnum = Field(..., description="Application type (N8N, MICROSOFT_FOUNDRY, REST_API)")
    config: Optional[dict] = Field(default_factory=dict, description="Application configuration")
    is_active: bool = Field(False, description="Whether the application is active")


class UpdateApplicationRequest(BaseModel):
    """Request model for updating an application."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Application name")
    description: Optional[str] = Field(None, max_length=2000, description="Application description")
    type: Optional[ApplicationTypeEnum] = Field(None, description="Application type (N8N, MICROSOFT_FOUNDRY, REST_API)")
    config: Optional[dict] = Field(None, description="Application configuration")
    is_active: Optional[bool] = Field(None, description="Whether the application is active")
