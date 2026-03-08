"""Response schemas for ReACT agents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import ChatAgentTypeEnum
from unifiedui.schema.responses.tags import TagSummary


class ReActAgentVersionResponse(BaseModel):
    """Response model for a ReACT agent version."""

    id: str = Field(..., description="Version record ID")
    re_act_agent_id: str = Field(..., description="ReACT agent ID")
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


class ReActAgentResponse(BaseModel):
    """Response model for a ReACT agent with its latest version config."""

    id: str = Field(..., description="ReACT agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="ReACT agent name")
    description: str | None = Field(None, description="ReACT agent description")
    is_active: bool = Field(..., description="Whether the agent is active")
    published_chat_agent_id: str | None = Field(None, description="ID of published chat agent")
    current_version: int | None = Field(None, description="Current (latest) version number")
    ai_model_ids: list[str] = Field(default_factory=list, description="List of AI model IDs (from latest version)")
    system_prompt: str | None = Field(None, description="System prompt (from latest version)")
    tool_ids: list[str] = Field(default_factory=list, description="List of tool IDs (from latest version)")
    security_prompt: str | None = Field(None, description="Security prompt (from latest version)")
    tool_use_prompt: str | None = Field(None, description="Tool use instructions (from latest version)")
    response_prompt: str | None = Field(None, description="Response formatting (from latest version)")
    greeting_messages: list[str] = Field(default_factory=list, description="Greeting messages (from latest version)")
    config: dict = Field(default_factory=dict, description="Agent configuration (from latest version)")
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the agent")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")

    model_config = ConfigDict(from_attributes=True)


class PublishReActAgentResponse(BaseModel):
    """Response model for publishing a ReACT agent."""

    chat_agent_id: str = Field(..., description="ID of the created/updated chat agent")
    re_act_agent_id: str = Field(..., description="ID of the source ReACT agent")
    chat_agent_name: str = Field(..., description="Name of the chat agent")
    chat_agent_type: ChatAgentTypeEnum = Field(..., description="Chat agent type")
    is_active: bool = Field(..., description="Whether the chat agent is active")

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

    react_agent_id: str = Field(..., description="ReACT agent ID")
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
