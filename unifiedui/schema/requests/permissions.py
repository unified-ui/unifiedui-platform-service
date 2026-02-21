"""Permission request schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class PermissionAssignmentRequest(BaseModel):
    """Request to assign permission to a user or group."""

    type: Literal["user", "identity_group", "custom_group"] = Field(
        ..., description="Type of entity to assign permission to"
    )
    id: str = Field(..., description="ID of the user or group")
    actions: list[str] = Field(..., description="List of actions to grant (e.g., ['read', 'write', 'admin'])")


class SetPermissionsRequest(BaseModel):
    """Request to set permissions for a resource."""

    assignments: list[PermissionAssignmentRequest] = Field(..., description="List of permission assignments")


class DeletePermissionRequest(BaseModel):
    """Request to delete specific permissions."""

    type: Literal["user", "identity_group", "custom_group"] = Field(..., description="Type of entity")
    id: str = Field(..., description="ID of the user or group")
