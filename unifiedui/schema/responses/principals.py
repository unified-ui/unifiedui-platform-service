"""Response schemas for principal operations."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
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
    is_active: bool = Field(True, description="Whether the principal is active in this tenant")
    created_at: datetime = Field(..., description="When the principal was created")
    updated_at: datetime = Field(..., description="When the principal was last updated")


class PrincipalWithRolesResponse(BaseModel):
    """Response model for a principal with roles on a resource.
    
    This is the unified response schema for all resource principal endpoints
    (applications, autonomous_agents, chat_widgets, conversations, credentials, 
    development_platforms, custom_groups).
    """
    model_config = ConfigDict(from_attributes=True)
    
    principal_id: str = Field(..., description="The principal ID")
    principal_type: str = Field(..., description="The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    roles: List[str] = Field(..., description="List of roles assigned to this principal on the resource")
    mail: Optional[str] = Field(None, description="The email address (for users)")
    display_name: Optional[str] = Field(None, description="The display name")
    principal_name: Optional[str] = Field(None, description="The principal name (UPN for users, name for groups)")
    description: Optional[str] = Field(None, description="Optional description")
    is_active: bool = Field(True, description="Whether the principal is active in this tenant")


class ResourcePrincipalsResponse(BaseModel):
    """Unified response for listing all principals with their roles on a resource.
    
    This is the unified response schema for all resource principals list endpoints.
    """
    resource_id: str = Field(..., description="The resource ID")
    resource_type: str = Field(..., description="The resource type (application, autonomous_agent, etc.)")
    tenant_id: str = Field(..., description="The tenant ID")
    principals: List[PrincipalWithRolesResponse] = Field(..., description="List of principals with their roles")
