"""Common response schemas shared across multiple entities."""
from pydantic import BaseModel, Field, ConfigDict


class QuickListItemResponse(BaseModel):
    """Minimal response model for quick-list view containing only id and name."""
    
    id: str = Field(..., description="Entity ID")
    name: str = Field(..., description="Entity name")
    
    model_config = ConfigDict(from_attributes=True)
