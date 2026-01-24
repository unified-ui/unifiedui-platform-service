"""Request schemas for tool permissions."""
from pydantic import BaseModel, Field

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class SetToolPermissionRequest(BaseModel):
    """Request model for setting a permission on a tool."""
    
    principal_id: str = Field(..., min_length=1, description="Principal ID (user, group, or custom group)")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    role: PermissionActionEnum = Field(..., description="Permission level (READ, WRITE, ADMIN)")
