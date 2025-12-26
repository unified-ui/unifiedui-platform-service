"""Request schemas for tags."""
from typing import List, Optional
from pydantic import BaseModel, Field


class CreateTagRequest(BaseModel):
    """Request model for creating a tag."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Tag name")


class SetResourceTagsRequest(BaseModel):
    """Request model for setting tags on a resource."""
    
    tags: List[str] = Field(
        default_factory=list,
        description="List of tag names to set on the resource"
    )
