"""Request schemas for chat widget permissions."""
from pydantic import BaseModel, Field

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class SetChatWidgetPermissionRequest(BaseModel):
    """Request model for setting chat widget permission."""
    
    principal_id: str = Field(..., description="ID of the principal (user, group, or custom group)")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    role: PermissionActionEnum = Field(..., description="Role level (READ, WRITE, ADMIN)")
