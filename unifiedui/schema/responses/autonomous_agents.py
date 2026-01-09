"""Response schemas for autonomous agents."""
from datetime import datetime
from typing import Optional, List
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
