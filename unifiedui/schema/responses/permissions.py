"""Permission response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class PermissionAssignmentResponse(BaseModel):
    """Response for a permission assignment."""

    type: str = Field(..., description="Type of entity (user, identity_group, custom_group)")
    id: str = Field(..., description="ID of the user or group")
    actions: list[str] = Field(..., description="List of granted actions")


class PermissionResponse(BaseModel):
    """Response for a single permission."""

    id: str = Field(..., description="Permission ID")
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="ID of the resource")
    action: str = Field(..., description="Action allowed")
    assigned_to: PermissionAssignmentResponse = Field(..., description="Assignment target")
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by: str = Field(..., description="Creator user ID")


class ResourcePermissionsResponse(BaseModel):
    """Response for all permissions on a resource."""

    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="ID of the resource")
    permissions: list[PermissionAssignmentResponse] = Field(
        ..., description="List of permission assignments grouped by entity"
    )
