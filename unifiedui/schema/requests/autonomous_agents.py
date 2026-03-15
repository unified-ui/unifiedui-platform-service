"""Request schemas for autonomous agents."""

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import AutonomousAgentTypeEnum


class CreateAutonomousAgentRequest(BaseModel):
    """Request model for creating an autonomous agent."""

    name: str = Field(..., min_length=1, max_length=255, description="Autonomous agent name")
    description: str | None = Field(None, max_length=2000, description="Autonomous agent description")
    type: AutonomousAgentTypeEnum = Field(..., description="Type of autonomous agent (e.g., N8N)")
    config: dict = Field(..., description="Autonomous agent configuration (required, type-specific)")
    is_active: bool = Field(False, description="Whether the autonomous agent is active")
    allow_api_keys: bool = Field(False, description="Whether API key authentication is allowed for this agent")


class UpdateAutonomousAgentRequest(BaseModel):
    """Request model for updating an autonomous agent."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Autonomous agent name")
    description: str | None = Field(None, max_length=2000, description="Autonomous agent description")
    config: dict | None = Field(None, description="Autonomous agent configuration")
    is_active: bool | None = Field(None, description="Whether the autonomous agent is active")
    allow_api_keys: bool | None = Field(None, description="Whether API key authentication is allowed for this agent")
    # Note: type, primary_key_vault_uri, secondary_key_vault_uri, last_full_import are NOT updatable via PATCH


class WorkflowFileItem(BaseModel):
    """A file attachment for a workflow request."""

    name: str = Field(..., description="Original filename")
    mime_type: str = Field(..., alias="mimeType", description="MIME type of the file")
    data: str = Field(..., description="Base64-encoded file content")

    model_config = ConfigDict(populate_by_name=True)


class StartWorkflowRequest(BaseModel):
    """Request model for triggering a workflow via webhook."""

    body: dict | None = Field(None, description="Optional JSON body to send with the webhook request")
    files: list[WorkflowFileItem] | None = Field(None, description="Optional file attachments as base64")
    query_params: dict[str, str] | None = Field(
        None,
        alias="queryParams",
        description="Optional query parameters to append to the webhook URL",
    )

    model_config = ConfigDict(populate_by_name=True)
