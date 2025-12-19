"""Request schemas for applications."""
from typing import Optional
from pydantic import BaseModel, Field


class CreateApplicationRequest(BaseModel):
    """Request model for creating an application."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Application name")
    description: Optional[str] = Field(None, max_length=2000, description="Application description")
    config: Optional[dict] = Field(default_factory=dict, description="Application configuration")


class UpdateApplicationRequest(BaseModel):
    """Request model for updating an application."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Application name")
    description: Optional[str] = Field(None, max_length=2000, description="Application description")
    config: Optional[dict] = Field(None, description="Application configuration")
