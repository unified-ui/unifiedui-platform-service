"""Request schemas for autonomous agents."""
from typing import Optional
from pydantic import BaseModel, Field


class CreateAutonomousAgentRequest(BaseModel):
    """Request model for creating an autonomous agent."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Autonomous agent name")
    description: Optional[str] = Field(None, max_length=2000, description="Autonomous agent description")
    config: Optional[dict] = Field(default_factory=dict, description="Autonomous agent configuration")


class UpdateAutonomousAgentRequest(BaseModel):
    """Request model for updating an autonomous agent."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Autonomous agent name")
    description: Optional[str] = Field(None, max_length=2000, description="Autonomous agent description")
    config: Optional[dict] = Field(None, description="Autonomous agent configuration")
