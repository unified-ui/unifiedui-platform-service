"""Response schemas for tools."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from unifiedui.core.database.enums import ToolTypeEnum
from unifiedui.schema.responses.tags import TagSummary


class ToolResponse(BaseModel):
    """Response model for a tool."""
    
    id: str = Field(..., description="Tool ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    type: ToolTypeEnum = Field(..., description="Tool type")
    config: dict = Field(default_factory=dict, description="Tool configuration")
    credential_id: Optional[str] = Field(None, description="Linked credential ID")
    is_active: bool = Field(..., description="Whether the tool is active")
    tags: List[TagSummary] = Field(default_factory=list, description="Tags on the tool")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    model_config = ConfigDict(from_attributes=True)
