"""Response schemas for principal operations."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class PrincipalResponse(BaseModel):
    """Response model for a principal."""
    model_config = ConfigDict(from_attributes=True)
    
    tenant_id: str = Field(..., description="The tenant ID")
    principal_id: str = Field(..., description="The principal ID")
    principal_type: str = Field(..., description="The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    mail: Optional[str] = Field(None, description="The email address (for users)")
    display_name: str = Field(..., description="The display name")
    principal_name: str = Field(..., description="The principal name (UPN for users, name for groups)")
    description: Optional[str] = Field(None, description="Optional description")
    created_at: datetime = Field(..., description="When the principal was created")
    updated_at: datetime = Field(..., description="When the principal was last updated")
