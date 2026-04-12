"""Request schemas for credentials."""

from pydantic import BaseModel, Field


class CreateCredentialRequest(BaseModel):
    """Request model for creating a credential."""

    name: str = Field(..., min_length=1, max_length=255, description="Credential name")
    description: str | None = Field(None, max_length=2000, description="Credential description")
    credential_type: str = Field(..., description="Type of credential (API_KEY, PASSWORD, TOKEN, etc.)")
    secret_value: str = Field(..., min_length=1, description="Secret value to store in vault")
    source: str | None = Field(None, description="Source or origin of the credential")
    metadata: dict | None = Field(None, description="Additional metadata")
    is_active: bool = Field(False, description="Whether the credential is active")


class UpdateCredentialRequest(BaseModel):
    """Request model for updating a credential."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Credential name")
    description: str | None = Field(None, max_length=2000, description="Credential description")
    credential_type: str | None = Field(None, description="Type of credential")
    secret_value: str | None = Field(None, min_length=1, description="New secret value")
    metadata: dict | None = Field(None, description="Additional metadata")
    is_active: bool | None = Field(None, description="Whether the credential is active")


class TestCredentialConnectionRequest(BaseModel):
    """Request model for testing a credential connection."""

    credential_type: str = Field(..., description="Type of credential (currently only ENTRA_ID_APP_REGISTRATION)")
    tenant_id: str = Field(..., min_length=1, description="Azure Entra ID tenant ID")
    client_id: str = Field(..., min_length=1, description="Azure Entra ID client/application ID")
    client_secret: str = Field(..., min_length=1, description="Azure Entra ID client secret")
    scopes: list[str] | None = Field(None, description="Optional OAuth 2.0 scopes for token acquisition")
