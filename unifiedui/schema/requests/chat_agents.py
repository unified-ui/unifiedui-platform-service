"""Request schemas for chat agents."""

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import ChatAgentTypeEnum


class CreateChatAgentRequest(BaseModel):
    """Request model for creating a chat agent."""

    name: str = Field(..., min_length=1, max_length=255, description="Chat agent name")
    description: str | None = Field(None, max_length=2000, description="Chat agent description")
    type: ChatAgentTypeEnum = Field(..., description="Chat agent type (N8N, MICROSOFT_FOUNDRY, REST_API)")
    config: dict | None = Field(default_factory=dict, description="Chat agent configuration")
    is_active: bool = Field(False, description="Whether the chat agent is active")
    embed_allowed_origins: str | None = Field(
        None, max_length=2000, description="Semicolon-separated list of allowed origins for embed iframe"
    )


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
