"""Request schemas for autonomous agents."""
from typing import Optional
from pydantic import BaseModel, Field

from unifiedui.core.database.enums import AutonomousAgentTypeEnum


class CreateAutonomousAgentRequest(BaseModel):
    """Request model for creating an autonomous agent."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Autonomous agent name")
    description: Optional[str] = Field(None, max_length=2000, description="Autonomous agent description")
    type: AutonomousAgentTypeEnum = Field(..., description="Type of autonomous agent (e.g., N8N)")
    config: dict = Field(..., description="Autonomous agent configuration (required, type-specific)")
    is_active: bool = Field(False, description="Whether the autonomous agent is active")
    allow_api_keys: bool = Field(False, description="Whether API key authentication is allowed for this agent")


class UpdateAutonomousAgentRequest(BaseModel):
    """Request model for updating an autonomous agent."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Autonomous agent name")
    description: Optional[str] = Field(None, max_length=2000, description="Autonomous agent description")
    config: Optional[dict] = Field(None, description="Autonomous agent configuration")
    is_active: Optional[bool] = Field(None, description="Whether the autonomous agent is active")
    allow_api_keys: Optional[bool] = Field(None, description="Whether API key authentication is allowed for this agent")
    # Note: type, primary_key_vault_uri, secondary_key_vault_uri, last_full_import are NOT updatable via PATCH
