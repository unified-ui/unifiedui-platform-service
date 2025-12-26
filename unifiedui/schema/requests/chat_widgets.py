"""Request schemas for chat widgets."""
from typing import Optional
from pydantic import BaseModel, Field

from unifiedui.core.database.enums import ChatWidgetTypeEnum


class CreateChatWidgetRequest(BaseModel):
    """Request model for creating a chat widget."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Chat widget name")
    description: Optional[str] = Field(None, max_length=2000, description="Chat widget description")
    type: Optional[ChatWidgetTypeEnum] = Field(None, description="Chat widget type (IFRAME or FORM)")
    config: dict = Field(..., description="Chat widget configuration (required)")
    is_active: bool = Field(False, description="Whether the chat widget is active")


class UpdateChatWidgetRequest(BaseModel):
    """Request model for updating a chat widget."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Chat widget name")
    description: Optional[str] = Field(None, max_length=2000, description="Chat widget description")
    type: Optional[ChatWidgetTypeEnum] = Field(None, description="Chat widget type (IFRAME or FORM)")
    config: Optional[dict] = Field(None, description="Chat widget configuration")
    is_active: Optional[bool] = Field(None, description="Whether the chat widget is active")
