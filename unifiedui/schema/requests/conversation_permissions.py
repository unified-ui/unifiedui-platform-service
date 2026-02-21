"""Request schemas for conversation permissions."""

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class SetConversationPermissionRequest(BaseModel):
    """Request model for setting conversation permission."""

    principal_id: str = Field(..., description="ID of the principal (user, group, or custom group)")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    role: PermissionActionEnum = Field(..., description="Role level (READ, WRITE, ADMIN)")
