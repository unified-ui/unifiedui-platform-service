"""Request schemas for chat agent permissions."""

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class SetChatAgentPermissionRequest(BaseModel):
    """Request model for setting chat agent permission."""

    principal_id: str = Field(..., description="ID of the principal (user, group, or custom group)")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    role: PermissionActionEnum = Field(..., description="Role level (READ, WRITE, ADMIN)")
