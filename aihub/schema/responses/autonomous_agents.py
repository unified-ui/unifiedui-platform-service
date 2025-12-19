"""Response schemas for autonomous agents."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AutonomousAgentResponse(BaseModel):
    """Response model for an autonomous agent."""
    
    id: str = Field(..., description="Autonomous agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Autonomous agent name")
    description: Optional[str] = Field(None, description="Autonomous agent description")
    config: dict = Field(default_factory=dict, description="Autonomous agent configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
    
    class Config:
        from_attributes = True
