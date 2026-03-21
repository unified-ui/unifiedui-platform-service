"""Response schemas for credentials."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.schema.responses.tags import TagSummary


class CredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    """Response model for a credential (without secret value)."""

    id: str = Field(..., description="Credential ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Credential name")
    description: str | None = Field(None, description="Credential description")
    type: str = Field(..., description="Type of credential")
    source: str = Field(..., description="Source system (e.g., vault)")
    credential_uri: str = Field(..., description="Vault URI reference (not the secret itself)")
    is_active: bool = Field(..., description="Whether the credential is active")
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the credential")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")
    my_permission: str | None = Field(None, description="User's permission level on this resource")


class CredentialSecretResponse(BaseModel):
    """Response model for credential secret value."""

    credential_id: str = Field(..., description="Credential ID")
    secret_value: str = Field(..., description="The actual secret value from vault")


class TestCredentialConnectionResponse(BaseModel):
    """Response model for credential connection test result."""

    success: bool = Field(..., description="Whether the connection test succeeded")
    message: str = Field(..., description="Result message")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
