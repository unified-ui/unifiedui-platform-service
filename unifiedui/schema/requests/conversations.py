"""Request schemas for conversations."""
from typing import Optional
from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    """Request model for creating a conversation."""
    
    application_id: str = Field(..., description="Application ID this conversation belongs to")
    name: str = Field(..., min_length=1, max_length=255, description="Conversation name")
    description: Optional[str] = Field(None, max_length=2000, description="Conversation description")
    is_active: bool = Field(False, description="Whether the conversation is active")


class UpdateConversationRequest(BaseModel):
    """Request model for updating a conversation."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Conversation name")
    description: Optional[str] = Field(None, max_length=2000, description="Conversation description")
    is_active: Optional[bool] = Field(None, description="Whether the conversation is active")
