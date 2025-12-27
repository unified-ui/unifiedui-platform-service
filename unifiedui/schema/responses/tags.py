"""Response schemas for tags."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class TagResponse(BaseModel):
    """Response model for a tag."""
    
    id: int = Field(..., description="Tag ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tag name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    model_config = ConfigDict(from_attributes=True)


class TagSummary(BaseModel):
    """Simplified tag info for embedding in resource responses."""
    
    id: int = Field(..., description="Tag ID")
    name: str = Field(..., description="Tag name")
    
    model_config = ConfigDict(from_attributes=True)


class TagListResponse(BaseModel):
    """Response model for a list of tags."""
    
    tags: List[TagSummary] = Field(default_factory=list, description="List of tags (id and name only)")


class ResourceTagsResponse(BaseModel):
    """Response model for tags on a resource."""
    
    tags: List[TagResponse] = Field(default_factory=list, description="List of tags on the resource")
