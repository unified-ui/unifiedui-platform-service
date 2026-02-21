"""Request schemas for ReACT agents."""

from pydantic import BaseModel, Field


class CreateReActAgentRequest(BaseModel):
    """Request model for creating a ReACT agent."""

    name: str = Field(..., min_length=1, max_length=255, description="ReACT agent name")
    description: str | None = Field(None, max_length=2000, description="ReACT agent description")
    ai_model_ids: list[str] = Field(default_factory=list, description="List of AI model IDs to use")
    system_prompt: str | None = Field(None, max_length=8000, description="System prompt for the agent")
    tool_ids: list[str] = Field(default_factory=list, description="List of tool IDs to attach")
    security_prompt: str | None = Field(None, max_length=8000, description="Security prompt")
    tool_use_prompt: str | None = Field(None, max_length=8000, description="Tool use instructions prompt")
    response_prompt: str | None = Field(None, max_length=8000, description="Response formatting prompt")
    greeting_messages: list[str] = Field(default_factory=list, description="Greeting messages for the agent")
    config: dict | None = Field(default_factory=dict, description="Agent configuration")
    is_active: bool = Field(False, description="Whether the agent is active")


class UpdateReActAgentRequest(BaseModel):
    """Request model for updating a ReACT agent."""

    name: str | None = Field(None, min_length=1, max_length=255, description="ReACT agent name")
    description: str | None = Field(None, max_length=2000, description="ReACT agent description")
    ai_model_ids: list[str] | None = Field(None, description="List of AI model IDs to use")
    system_prompt: str | None = Field(None, max_length=8000, description="System prompt for the agent")
    tool_ids: list[str] | None = Field(None, description="List of tool IDs to attach")
    security_prompt: str | None = Field(None, max_length=8000, description="Security prompt")
    tool_use_prompt: str | None = Field(None, max_length=8000, description="Tool use instructions prompt")
    response_prompt: str | None = Field(None, max_length=8000, description="Response formatting prompt")
    greeting_messages: list[str] | None = Field(None, description="Greeting messages for the agent")
    config: dict | None = Field(None, description="Agent configuration")
    is_active: bool | None = Field(None, description="Whether the agent is active")
