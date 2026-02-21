"""Response schemas for ReACT agents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.schema.responses.tags import TagSummary


class ReActAgentResponse(BaseModel):
    """Response model for a ReACT agent."""

    id: str = Field(..., description="ReACT agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="ReACT agent name")
    description: str | None = Field(None, description="ReACT agent description")
    ai_model_ids: list[str] = Field(default_factory=list, description="List of AI model IDs")
    system_prompt: str | None = Field(None, description="System prompt")
    tool_ids: list[str] = Field(default_factory=list, description="List of tool IDs")
    security_prompt: str | None = Field(None, description="Security prompt")
    tool_use_prompt: str | None = Field(None, description="Tool use instructions prompt")
    response_prompt: str | None = Field(None, description="Response formatting prompt")
    greeting_messages: list[str] = Field(default_factory=list, description="Greeting messages")
    config: dict = Field(default_factory=dict, description="Agent configuration")
    is_active: bool = Field(..., description="Whether the agent is active")
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the agent")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")

    model_config = ConfigDict(from_attributes=True)
