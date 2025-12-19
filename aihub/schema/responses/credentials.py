"""Response schemas for credentials."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CredentialResponse(BaseModel):
    """Response model for a credential (without secret value)."""
    
    id: str = Field(..., description="Credential ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Credential name")
    description: Optional[str] = Field(None, description="Credential description")
    type: str = Field(..., description="Type of credential")
    source: str = Field(..., description="Source system (e.g., vault)")
    credential_uri: str = Field(..., description="Vault URI reference (not the secret itself)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    class Config:
        from_attributes = True

