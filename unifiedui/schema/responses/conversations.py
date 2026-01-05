"""Response schemas for conversations."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ConversationResponse(BaseModel):
    """Response model for a conversation."""
    
    id: str = Field(..., description="Conversation ID")
    tenant_id: str = Field(..., description="Tenant ID")
    application_id: str = Field(..., description="Application ID this conversation belongs to")
    name: str = Field(..., description="Conversation name")
    description: Optional[str] = Field(None, description="Conversation description")
    is_active: bool = Field(..., description="Whether the conversation is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    model_config = ConfigDict(from_attributes=True)
