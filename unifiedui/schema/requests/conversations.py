"""Request schemas for conversations."""

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    """Request model for creating a conversation."""

    chat_agent_id: str = Field(..., description="Chat agent ID this conversation belongs to")
    name: str = Field(..., min_length=1, max_length=255, description="Conversation name")
    description: str | None = Field(None, max_length=2000, description="Conversation description")
    is_active: bool = Field(False, description="Whether the conversation is active")


class UpdateConversationRequest(BaseModel):
    """Request model for updating a conversation."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Conversation name")
    description: str | None = Field(None, max_length=2000, description="Conversation description")
    is_active: bool | None = Field(None, description="Whether the conversation is active")
