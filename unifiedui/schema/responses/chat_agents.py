"""Response schemas for chat agents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import ChatAgentTypeEnum
from unifiedui.schema.responses.tags import TagSummary


class ChatAgentResponse(BaseModel):
    """Response model for a chat agent."""

    id: str = Field(..., description="Chat agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Chat agent name")
    description: str | None = Field(None, description="Chat agent description")
    type: ChatAgentTypeEnum = Field(..., description="Chat agent type")
    config: dict = Field(default_factory=dict, description="Chat agent configuration")
    is_active: bool = Field(..., description="Whether the chat agent is active")
    embed_allowed_origins: str | None = Field(
        None, description="Semicolon-separated list of allowed origins for embed iframe"
    )
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the chat agent")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")

    model_config = ConfigDict(from_attributes=True)


# ========== Config Response Schemas for Agent Service ==========


class CredentialSecretResponse(BaseModel):
    """Response model for a credential with its secret value (internal use only)."""

    id: str = Field(..., description="Credential ID")
    credentials_uri: str = Field(..., description="Credential vault URI")
    name: str = Field(..., description="Credential name")
    description: str | None = Field(None, description="Credential description")
    type: str = Field(..., description="Credential type (API_KEY, BASIC_AUTH)")
    is_active: bool = Field(..., description="Whether the credential is active")
    secret: str | dict = Field(..., description="Secret value (string for API_KEY, dict for BASIC_AUTH)")

    model_config = ConfigDict(from_attributes=True)


class UserInfoResponse(BaseModel):
    """Response model for user information in chat agent config."""

    id: str = Field(..., description="User ID")
    display_name: str | None = Field(None, description="User display name")
    principal_name: str | None = Field(None, description="User principal name (email)")
    mail: str | None = Field(None, description="User email")

    model_config = ConfigDict(from_attributes=True)


class N8NConfigSettingsResponse(BaseModel):
    """Response model for N8N chat agent config settings."""

    api_version: str = Field(..., description="API version")
    workflow_type: str = Field(..., description="Workflow type")
    use_unified_chat_history: bool = Field(..., description="Whether to use unified chat history")
    chat_history_count: int = Field(..., description="Number of chat history messages")
    chat_url: str = Field(..., description="N8N webhook URL for chat")
    workflow_id: str = Field(..., description="N8N workflow ID extracted from workflow_endpoint")
    n8n_host: str = Field(..., description="N8N host URL extracted from workflow_endpoint")
    api_credentials: CredentialSecretResponse = Field(..., description="API key credentials with secret")
    chat_credentials: CredentialSecretResponse = Field(..., description="Chat auth credentials with secret")

    model_config = ConfigDict(from_attributes=True)


class MicrosoftFoundryConfigSettingsResponse(BaseModel):
    """Response model for Microsoft Foundry chat agent config settings."""

    api_version: str = Field(..., description="API version (e.g., '2025-11-15-preview')")
    agent_type: str = Field(..., description="Agent type (AGENT or MULTI_AGENT)")
    project_endpoint: str = Field(..., description="Foundry project endpoint URL")
    agent_name: str = Field(..., description="Name of the agent in Foundry")

    model_config = ConfigDict(from_attributes=True)


class ChatAgentConfigResponse(BaseModel):
    """
    Response model for chat agent configuration (for agent service).
    Returns full config with credential secrets and user data.
    """

    docversion: str = Field(default="v1", description="Document version")
    type: ChatAgentTypeEnum = Field(..., description="Chat agent type")
    tenant_id: str = Field(..., description="Tenant ID")
    chat_agent_id: str = Field(..., description="Chat agent ID")
    settings: N8NConfigSettingsResponse | MicrosoftFoundryConfigSettingsResponse | dict = Field(
        ..., description="Chat agent settings with resolved credentials"
    )
    user: UserInfoResponse = Field(..., description="User information")

    model_config = ConfigDict(from_attributes=True)
