"""Response schemas for chat widgets."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import ChatWidgetTypeEnum
from unifiedui.schema.responses.tags import TagSummary


class ChatWidgetResponse(BaseModel):
    """Response model for a chat widget."""

    id: str = Field(..., description="Chat widget ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Chat widget name")
    description: str | None = Field(None, description="Chat widget description")
    type: ChatWidgetTypeEnum | None = Field(None, description="Chat widget type (IFRAME or FORM)")
    config: dict = Field(default_factory=dict, description="Chat widget configuration")
    is_active: bool = Field(..., description="Whether the chat widget is active")
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the chat widget")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")

    model_config = ConfigDict(from_attributes=True)
