"""Response schemas for credentials."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from unifiedui.schema.responses.tags import TagSummary


class CredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    """Response model for a credential (without secret value)."""
    
    id: str = Field(..., description="Credential ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Credential name")
    description: Optional[str] = Field(None, description="Credential description")
    type: str = Field(..., description="Type of credential")
    source: str = Field(..., description="Source system (e.g., vault)")
    credential_uri: str = Field(..., description="Vault URI reference (not the secret itself)")
    is_active: bool = Field(..., description="Whether the credential is active")
    tags: List[TagSummary] = Field(default_factory=list, description="Tags on the credential")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")


class CredentialSecretResponse(BaseModel):
    """Response model for credential secret value."""
    
    credential_id: str = Field(..., description="Credential ID")
    secret_value: str = Field(..., description="The actual secret value from vault")

