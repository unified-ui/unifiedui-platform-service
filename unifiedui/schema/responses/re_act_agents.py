"""Response schemas for ReACT agent versions and config settings."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReActAgentVersionResponse(BaseModel):
    """Response model for a ReACT agent version."""

    id: str = Field(..., description="Version record ID")
    chat_agent_id: str = Field(..., description="Chat agent ID")
    version: int = Field(..., description="Version number")
    ai_model_ids: list[str] = Field(default_factory=list, description="List of AI model IDs")
    system_prompt: str | None = Field(None, description="System prompt")
    tool_ids: list[str] = Field(default_factory=list, description="List of tool IDs")
    security_prompt: str | None = Field(None, description="Security prompt")
    tool_use_prompt: str | None = Field(None, description="Tool use instructions prompt")
    response_prompt: str | None = Field(None, description="Response formatting prompt")
    greeting_messages: list[str] = Field(default_factory=list, description="Greeting messages")
    config: dict = Field(default_factory=dict, description="Agent configuration")
    created_at: datetime = Field(..., description="Version creation timestamp")
    updated_at: datetime = Field(..., description="Version update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")

    model_config = ConfigDict(from_attributes=True)


class ReActAgentAIModelResponse(BaseModel):
    """Resolved AI model with credentials for the ReACT agent service."""

    id: str = Field(..., description="AI model ID")
    provider: str = Field(..., description="AI model provider (e.g. AZURE_OPENAI, OPENAI)")
    config: dict = Field(default_factory=dict, description="Model config (model_name, endpoint, etc.)")
    credential_secret: dict | None = Field(None, description="Decrypted credential secret")
    priority: int = Field(0, description="Model priority")


class ReActAgentConfigSettingsResponse(BaseModel):
    """Response model for ReACT agent config settings (for agent service)."""

    chat_agent_id: str = Field(..., description="Chat agent ID")
    version: int = Field(..., description="Version number of the config")
    ai_model_ids: list[str] = Field(default_factory=list, description="List of AI model IDs")
    ai_models: list[ReActAgentAIModelResponse] = Field(
        default_factory=list, description="Resolved AI model configurations with credentials"
    )
    system_prompt: str | None = Field(None, description="System prompt")
    tool_ids: list[str] = Field(default_factory=list, description="List of tool IDs")
    tools: list[dict] = Field(default_factory=list, description="Resolved tool configurations")
    security_prompt: str | None = Field(None, description="Security prompt")
    tool_use_prompt: str | None = Field(None, description="Tool use instructions")
    response_prompt: str | None = Field(None, description="Response formatting prompt")
    greeting_messages: list[str] = Field(default_factory=list, description="Greeting messages")
    config: dict = Field(default_factory=dict, description="Additional configuration")

    model_config = ConfigDict(from_attributes=True)
