"""Request schemas for autonomous agent permissions."""
from pydantic import BaseModel, Field

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class SetAutonomousAgentPermissionRequest(BaseModel):
    """Request model for setting autonomous agent permission."""
    
    principal_id: str = Field(..., description="ID of the principal (user, group, or custom group)")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    role: PermissionActionEnum = Field(..., description="Role level (READ, WRITE, ADMIN)")
