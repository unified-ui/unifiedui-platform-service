"""Response schemas for autonomous agents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import AutonomousAgentTypeEnum
from unifiedui.schema.responses.tags import TagSummary


class AutonomousAgentResponse(BaseModel):
    """Response model for an autonomous agent."""

    id: str = Field(..., description="Autonomous agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Autonomous agent name")
    description: str | None = Field(None, description="Autonomous agent description")
    type: AutonomousAgentTypeEnum = Field(..., description="Type of autonomous agent")
    config: dict = Field(default_factory=dict, description="Autonomous agent configuration")
    is_active: bool = Field(..., description="Whether the autonomous agent is active")
    allow_api_keys: bool = Field(..., description="Whether API key authentication is allowed for this agent")
    last_full_import: datetime | None = Field(None, description="Timestamp of last full import (system managed)")
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the autonomous agent")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")

    model_config = ConfigDict(from_attributes=True)


class AutonomousAgentKeyResponse(BaseModel):
    """Response model for an autonomous agent API key."""

    key: str = Field(..., description="The API key value")
    key_number: int = Field(..., description="Key number (1 or 2)")

    model_config = ConfigDict(from_attributes=True)


# ========== Config Response Schemas for Agent Service ==========


class CredentialSecretResponse(BaseModel):
    """Response model for a credential with its secret value (internal use only)."""

    id: str = Field(..., description="Credential ID")
    credentials_uri: str = Field(..., description="Credential vault URI")
    name: str = Field(..., description="Credential name")
    description: str | None = Field(None, description="Credential description")
    type: str = Field(..., description="Credential type")
    is_active: bool = Field(..., description="Whether the credential is active")
    secret: str | dict = Field(..., description="Secret value")

    model_config = ConfigDict(from_attributes=True)


class N8NAutonomousAgentConfigSettingsResponse(BaseModel):
    """Response model for N8N autonomous agent config settings."""

    api_version: str = Field(..., description="API version")
    n8n_host: str = Field(..., description="N8N host URL")
    n8n_workflow_endpoint: str = Field(..., description="Full N8N workflow endpoint URL")
    workflow_id: str = Field(..., description="N8N workflow ID")
    api_credentials: CredentialSecretResponse = Field(..., description="API key credentials with secret")

    model_config = ConfigDict(from_attributes=True)


class AutonomousAgentConfigResponse(BaseModel):
    """
    Response model for autonomous agent configuration (for agent service).
    Returns full config with credential secrets.
    No user info is included since autonomous agents run on their own schedule.
    """

    docversion: str = Field(default="v1", description="Document version")
    type: AutonomousAgentTypeEnum = Field(..., description="Autonomous agent type")
    tenant_id: str = Field(..., description="Tenant ID")
    autonomous_agent_id: str = Field(..., description="Autonomous agent ID")
    settings: N8NAutonomousAgentConfigSettingsResponse | dict = Field(
        ..., description="Agent settings with resolved credentials"
    )

    model_config = ConfigDict(from_attributes=True)


# ========== Workflow Run Response Schemas ==========


class WorkflowRunResponse(BaseModel):
    """Response model for a single workflow execution run."""

    id: str = Field(..., description="Execution ID")
    finished: bool = Field(..., description="Whether execution has finished")
    mode: str = Field(..., description="Execution mode (e.g., 'manual', 'trigger')")
    started_at: datetime | None = Field(None, description="Execution start time", alias="startedAt")
    stopped_at: datetime | None = Field(None, description="Execution stop time", alias="stoppedAt")
    status: str = Field(..., description="Execution status (e.g., 'success', 'error', 'running')")
    workflow_name: str | None = Field(None, description="Name of the workflow", alias="workflowName")
    retry_of: str | None = Field(None, description="ID of execution this is a retry of", alias="retryOf")
    retry_success_id: str | None = Field(
        None, description="ID of the successful retry execution", alias="retrySuccessId"
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class WorkflowRunDetailResponse(BaseModel):
    """Response model for a single workflow execution with full data."""

    id: str = Field(..., description="Execution ID")
    finished: bool = Field(..., description="Whether execution has finished")
    mode: str = Field(..., description="Execution mode")
    started_at: datetime | None = Field(None, description="Execution start time", alias="startedAt")
    stopped_at: datetime | None = Field(None, description="Execution stop time", alias="stoppedAt")
    status: str = Field(..., description="Execution status")
    workflow_name: str | None = Field(None, description="Name of the workflow", alias="workflowName")
    retry_of: str | None = Field(None, description="ID of execution this is a retry of", alias="retryOf")
    retry_success_id: str | None = Field(
        None, description="ID of the successful retry execution", alias="retrySuccessId"
    )
    data: dict | None = Field(None, description="Full execution data (input/output)")
    workflow_data: dict | None = Field(None, description="Workflow definition data", alias="workflowData")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class WorkflowRunsListResponse(BaseModel):
    """Response model for a list of workflow execution runs."""

    runs: list[WorkflowRunResponse] = Field(default_factory=list, description="List of workflow runs")
    next_cursor: str | None = Field(None, description="Cursor for next page", alias="nextCursor")


class WorkflowRunRetryResponse(BaseModel):
    """Response model for retrying a workflow execution."""

    id: str | None = Field(None, description="New execution ID")
    retried: bool = Field(False, description="Whether the retry was triggered")
    message: str | None = Field(None, description="Message from the workflow platform")
