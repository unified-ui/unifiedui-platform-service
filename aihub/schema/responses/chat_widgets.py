"""Response schemas for chat widgets."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from aihub.core.database.enums import ChatWidgetTypeEnum


class ChatWidgetResponse(BaseModel):
    """Response model for a chat widget."""
    
    id: str = Field(..., description="Chat widget ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Chat widget name")
    description: Optional[str] = Field(None, description="Chat widget description")
    type: Optional[ChatWidgetTypeEnum] = Field(None, description="Chat widget type (IFRAME or FORM)")
    config: dict = Field(default_factory=dict, description="Chat widget configuration")
    is_active: bool = Field(..., description="Whether the chat widget is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    model_config = ConfigDict(from_attributes=True)
