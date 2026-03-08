"""Request schemas for chat widgets."""

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import ChatWidgetTypeEnum


class CreateChatWidgetRequest(BaseModel):
    """Request model for creating a chat widget."""

    name: str = Field(..., min_length=1, max_length=255, description="Chat widget name")
    description: str | None = Field(None, max_length=2000, description="Chat widget description")
    type: ChatWidgetTypeEnum | None = Field(None, description="Chat widget type (IFRAME or FORM)")
    config: dict = Field(..., description="Chat widget configuration (required)")
    is_active: bool = Field(False, description="Whether the chat widget is active")


class UpdateChatWidgetRequest(BaseModel):
    """Request model for updating a chat widget."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Chat widget name")
    description: str | None = Field(None, max_length=2000, description="Chat widget description")
    type: ChatWidgetTypeEnum | None = Field(None, description="Chat widget type (IFRAME or FORM)")
    config: dict | None = Field(None, description="Chat widget configuration")
    is_active: bool | None = Field(None, description="Whether the chat widget is active")
