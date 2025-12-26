"""Request schemas for credentials."""
from typing import Optional
from pydantic import BaseModel, Field


class CreateCredentialRequest(BaseModel):
    """Request model for creating a credential."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Credential name")
    description: Optional[str] = Field(None, max_length=2000, description="Credential description")
    credential_type: str = Field(..., description="Type of credential (API_KEY, PASSWORD, TOKEN, etc.)")
    secret_value: str = Field(..., min_length=1, description="Secret value to store in vault")
    source: Optional[str] = Field(None, description="Source or origin of the credential")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    is_active: bool = Field(False, description="Whether the credential is active")


class UpdateCredentialRequest(BaseModel):
    """Request model for updating a credential."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Credential name")
    description: Optional[str] = Field(None, max_length=2000, description="Credential description")
    credential_type: Optional[str] = Field(None, description="Type of credential")
    secret_value: Optional[str] = Field(None, min_length=1, description="New secret value")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    is_active: Optional[bool] = Field(None, description="Whether the credential is active")
