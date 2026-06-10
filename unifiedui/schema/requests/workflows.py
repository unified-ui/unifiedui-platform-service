"""Request schemas for workflows."""

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import WorkflowTypeEnum


class CreateWorkflowRequest(BaseModel):
    """Request model for creating a workflow."""

    name: str = Field(..., min_length=1, max_length=255, description="Workflow name")
    description: str | None = Field(None, max_length=2000, description="Workflow description")
    type: WorkflowTypeEnum = Field(..., description="Type of workflow (e.g., N8N)")
    config: dict = Field(..., description="Workflow configuration (required, type-specific)")
    allow_api_keys: bool = Field(False, description="Whether API key authentication is allowed for this workflow")


class UpdateWorkflowRequest(BaseModel):
    """Request model for updating a workflow."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Workflow name")
    description: str | None = Field(None, max_length=2000, description="Workflow description")
    config: dict | None = Field(None, description="Workflow configuration")
    allow_api_keys: bool | None = Field(None, description="Whether API key authentication is allowed for this workflow")
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
