"""Response schemas for conversations."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ConversationQuickListItemResponse(BaseModel):
    """Minimal response model for conversation quick-list view."""
    
    id: str = Field(..., description="Conversation ID")
    name: str = Field(..., description="Conversation name")
    application_id: str = Field(..., description="Application ID this conversation belongs to")
    
    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Response model for a conversation."""
    
    id: str = Field(..., description="Conversation ID")
    tenant_id: str = Field(..., description="Tenant ID")
    application_id: str = Field(..., description="Application ID this conversation belongs to")
    ext_conversation_id: Optional[str] = Field(None, description="External conversation ID (e.g., from Microsoft Foundry)")
    name: str = Field(..., description="Conversation name")
    description: Optional[str] = Field(None, description="Conversation description")
    is_active: bool = Field(..., description="Whether the conversation is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    my_permission: Optional[str] = Field(None, description="User's permission level on this resource")
    
    model_config = ConfigDict(from_attributes=True)
