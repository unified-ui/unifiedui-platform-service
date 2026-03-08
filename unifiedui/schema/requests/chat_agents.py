"""Request schemas for chat agents."""

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import ChatAgentTypeEnum


class CreateChatAgentRequest(BaseModel):
    """Request model for creating a chat agent."""

    name: str = Field(..., min_length=1, max_length=255, description="Chat agent name")
    description: str | None = Field(None, max_length=2000, description="Chat agent description")
    type: ChatAgentTypeEnum = Field(..., description="Chat agent type (N8N, MICROSOFT_FOUNDRY, REST_API, REACT_AGENT)")
    config: dict | None = Field(default_factory=dict, description="Chat agent configuration")
    is_active: bool = Field(False, description="Whether the chat agent is active")
    embed_allowed_origins: str | None = Field(
        None, max_length=2000, description="Semicolon-separated list of allowed origins for embed iframe"
    )
    ai_model_ids: list[str] = Field(default_factory=list, description="AI model IDs (REACT_AGENT only)")
    system_prompt: str | None = Field(None, max_length=8000, description="System prompt (REACT_AGENT only)")
    tool_ids: list[str] = Field(default_factory=list, description="Tool IDs (REACT_AGENT only)")
    security_prompt: str | None = Field(None, max_length=8000, description="Security prompt (REACT_AGENT only)")
    tool_use_prompt: str | None = Field(None, max_length=8000, description="Tool use instructions (REACT_AGENT only)")
    response_prompt: str | None = Field(None, max_length=8000, description="Response formatting (REACT_AGENT only)")
    greeting_messages: list[str] = Field(default_factory=list, description="Greeting messages (REACT_AGENT only)")


class UpdateChatAgentRequest(BaseModel):
    """Request model for updating a chat agent."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Chat agent name")
    description: str | None = Field(None, max_length=2000, description="Chat agent description")
    type: ChatAgentTypeEnum | None = Field(None, description="Chat agent type (N8N, MICROSOFT_FOUNDRY, REST_API)")
    config: dict | None = Field(None, description="Chat agent configuration")
    is_active: bool | None = Field(None, description="Whether the chat agent is active")
    embed_allowed_origins: str | None = Field(
        None, max_length=2000, description="Semicolon-separated list of allowed origins for embed iframe"
    )


class UpdateReActAgentVersionRequest(BaseModel):
    """Request model for creating a new version of a REACT_AGENT chat agent config."""

    ai_model_ids: list[str] | None = Field(None, description="List of AI model IDs to use")
    system_prompt: str | None = Field(None, max_length=8000, description="System prompt for the agent")
    tool_ids: list[str] | None = Field(None, description="List of tool IDs to attach")
    security_prompt: str | None = Field(None, max_length=8000, description="Security prompt")
    tool_use_prompt: str | None = Field(None, max_length=8000, description="Tool use instructions prompt")
    response_prompt: str | None = Field(None, max_length=8000, description="Response formatting prompt")
    greeting_messages: list[str] | None = Field(None, description="Greeting messages for the agent")
    config: dict | None = Field(None, description="Agent configuration")
