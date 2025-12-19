"""Request schemas for conversation permissions."""
from pydantic import BaseModel, Field

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class SetConversationPermissionRequest(BaseModel):
    """Request model for setting conversation permission."""
    
    principal_id: str = Field(..., description="ID of the principal (user, group, or custom group)")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    permission: PermissionActionEnum = Field(..., description="Permission level (READ, WRITE, ADMIN)")
