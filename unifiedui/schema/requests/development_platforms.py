"""Request schemas for development platforms."""
from typing import Optional
from pydantic import BaseModel, Field


class CreateDevelopmentPlatformRequest(BaseModel):
    """Request model for creating a development platform."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Development platform name")
    description: Optional[str] = Field(None, max_length=2000, description="Development platform description")
    type: Optional[str] = Field(None, max_length=255, description="Type of development platform (e.g., IDE, notebook, terminal)")
    iframe_url: str = Field(..., min_length=1, max_length=2000, description="URL for the iframe embedding")
    config: Optional[dict] = Field(default_factory=dict, description="Development platform configuration")
    is_active: bool = Field(False, description="Whether the development platform is active")


class UpdateDevelopmentPlatformRequest(BaseModel):
    """Request model for updating a development platform."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Development platform name")
    description: Optional[str] = Field(None, max_length=2000, description="Development platform description")
    type: Optional[str] = Field(None, max_length=255, description="Type of development platform")
    iframe_url: Optional[str] = Field(None, min_length=1, max_length=2000, description="URL for the iframe embedding")
    config: Optional[dict] = Field(None, description="Development platform configuration")
    is_active: Optional[bool] = Field(None, description="Whether the development platform is active")
