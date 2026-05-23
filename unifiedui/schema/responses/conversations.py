"""Response schemas for conversations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationQuickListItemResponse(BaseModel):
    """Minimal response model for conversation quick-list view."""

    id: str = Field(..., description="Conversation ID")
    name: str = Field(..., description="Conversation name")
    chat_agent_id: str = Field(..., description="Chat agent ID this conversation belongs to")

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Response model for a conversation."""

    id: str = Field(..., description="Conversation ID")
    tenant_id: str = Field(..., description="Tenant ID")
    chat_agent_id: str = Field(..., description="Chat agent ID this conversation belongs to")
    ext_conversation_id: str | None = Field(None, description="External conversation ID (e.g., from Microsoft Foundry)")
    name: str = Field(..., description="Conversation name")
    description: str | None = Field(None, description="Conversation description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")

    model_config = ConfigDict(from_attributes=True)
