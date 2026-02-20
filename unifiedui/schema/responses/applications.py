"""Response schemas for applications."""
from datetime import datetime
from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, ConfigDict

from unifiedui.core.database.enums import ApplicationTypeEnum
from unifiedui.schema.responses.tags import TagSummary


class ApplicationResponse(BaseModel):
    """Response model for an application."""
    
    id: str = Field(..., description="Application ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Application name")
    description: Optional[str] = Field(None, description="Application description")
    type: ApplicationTypeEnum = Field(..., description="Application type")
    config: dict = Field(default_factory=dict, description="Application configuration")
    is_active: bool = Field(..., description="Whether the application is active")
    embed_allowed_origins: Optional[str] = Field(None, description="Semicolon-separated list of allowed origins for embed iframe")
    tags: List[TagSummary] = Field(default_factory=list, description="Tags on the application")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    my_permission: Optional[str] = Field(None, description="User's permission level on this resource")
    
    model_config = ConfigDict(from_attributes=True)


# ========== Config Response Schemas for Agent Service ==========

class CredentialSecretResponse(BaseModel):
    """Response model for a credential with its secret value (internal use only)."""
    
    id: str = Field(..., description="Credential ID")
    credentials_uri: str = Field(..., description="Credential vault URI")
    name: str = Field(..., description="Credential name")
    description: Optional[str] = Field(None, description="Credential description")
    type: str = Field(..., description="Credential type (API_KEY, BASIC_AUTH)")
    is_active: bool = Field(..., description="Whether the credential is active")
    secret: Union[str, dict] = Field(..., description="Secret value (string for API_KEY, dict for BASIC_AUTH)")
    
    model_config = ConfigDict(from_attributes=True)


class UserInfoResponse(BaseModel):
    """Response model for user information in application config."""
    
    id: str = Field(..., description="User ID")
    display_name: Optional[str] = Field(None, description="User display name")
    principal_name: Optional[str] = Field(None, description="User principal name (email)")
    mail: Optional[str] = Field(None, description="User email")
    
    model_config = ConfigDict(from_attributes=True)


class N8NConfigSettingsResponse(BaseModel):
    """Response model for N8N application config settings."""
    
    api_version: str = Field(..., description="API version")
    workflow_type: str = Field(..., description="Workflow type")
    use_unified_chat_history: bool = Field(..., description="Whether to use unified chat history")
    chat_history_count: int = Field(..., description="Number of chat history messages")
    chat_url: str = Field(..., description="N8N webhook URL for chat")
    workflow_id: str = Field(..., description="N8N workflow ID extracted from workflow_endpoint")
    n8n_host: str = Field(..., description="N8N host URL extracted from workflow_endpoint")
    api_credentials: CredentialSecretResponse = Field(..., description="API key credentials with secret")
    chat_credentials: CredentialSecretResponse = Field(..., description="Chat auth credentials with secret")
    
    model_config = ConfigDict(from_attributes=True)


class MicrosoftFoundryConfigSettingsResponse(BaseModel):
    """Response model for Microsoft Foundry application config settings."""
    
    api_version: str = Field(..., description="API version (e.g., '2025-11-15-preview')")
    agent_type: str = Field(..., description="Agent type (AGENT or MULTI_AGENT)")
    project_endpoint: str = Field(..., description="Foundry project endpoint URL")
    agent_name: str = Field(..., description="Name of the agent in Foundry")
    
    model_config = ConfigDict(from_attributes=True)


class ApplicationConfigResponse(BaseModel):
    """
    Response model for application configuration (for agent service).
    Returns full config with credential secrets and user data.
    """
    
    docversion: str = Field(default="v1", description="Document version")
    type: ApplicationTypeEnum = Field(..., description="Application type")
    tenant_id: str = Field(..., description="Tenant ID")
    application_id: str = Field(..., description="Application ID")
    settings: Union[N8NConfigSettingsResponse, MicrosoftFoundryConfigSettingsResponse, dict] = Field(..., description="Application settings with resolved credentials")
    user: UserInfoResponse = Field(..., description="User information")
    
    model_config = ConfigDict(from_attributes=True)
