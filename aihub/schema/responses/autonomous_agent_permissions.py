"""Response schemas for autonomous agent permissions."""
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class AutonomousAgentPermissionResponse(BaseModel):
    """Response model for an autonomous agent permission."""
    
    id: str = Field(..., description="Permission ID")
    autonomous_agent_id: str = Field(..., description="Autonomous agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    principal_id: str = Field(..., description="Principal ID")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    role: PermissionActionEnum = Field(..., description="Role assigned to the principal")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class PrincipalPermissionsResponse(BaseModel):
    """Response model for a principal's permissions on an autonomous agent."""
    autonomous_agent_id: str = Field(..., description="Autonomous agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    principal_id: str = Field(..., description="Principal ID")
    principal_type: str = Field(..., description="Principal type (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    roles: list[str] = Field(..., description="List of roles")


class AutonomousAgentPrincipalsResponse(BaseModel):
    """Response containing all principals and their roles for an autonomous agent."""
    autonomous_agent_id: str = Field(..., description="The autonomous agent ID")
    tenant_id: str = Field(..., description="The tenant ID")
    principals: list[PrincipalPermissionsResponse] = Field(..., description="List of principals with their roles")
