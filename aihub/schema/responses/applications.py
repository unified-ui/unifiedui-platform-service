"""Response schemas for applications."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ApplicationResponse(BaseModel):
    """Response model for an application."""
    
    id: str = Field(..., description="Application ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Application name")
    description: Optional[str] = Field(None, description="Application description")
    config: dict = Field(default_factory=dict, description="Application configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    class Config:
        from_attributes = True
