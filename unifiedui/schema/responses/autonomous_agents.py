"""Response schemas for autonomous agents."""
from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict

from unifiedui.schema.responses.tags import TagSummary
from unifiedui.core.database.enums import AutonomousAgentTypeEnum


class AutonomousAgentResponse(BaseModel):
    """Response model for an autonomous agent."""
    
    id: str = Field(..., description="Autonomous agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Autonomous agent name")
    description: Optional[str] = Field(None, description="Autonomous agent description")
    type: AutonomousAgentTypeEnum = Field(..., description="Type of autonomous agent")
    config: dict = Field(default_factory=dict, description="Autonomous agent configuration")
    is_active: bool = Field(..., description="Whether the autonomous agent is active")
    last_full_import: Optional[datetime] = Field(None, description="Timestamp of last full import (system managed)")
    tags: List[TagSummary] = Field(default_factory=list, description="Tags on the autonomous agent")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
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
    description: Optional[str] = Field(None, description="Credential description")
    type: str = Field(..., description="Credential type")
    is_active: bool = Field(..., description="Whether the credential is active")
    secret: Union[str, dict] = Field(..., description="Secret value")
    
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
    settings: Union[N8NAutonomousAgentConfigSettingsResponse, dict] = Field(..., description="Agent settings with resolved credentials")
    
    model_config = ConfigDict(from_attributes=True)
