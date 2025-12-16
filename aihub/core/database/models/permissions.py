"""Permission data models."""
from datetime import datetime
from typing import Literal
from pydantic import Field

from aihub.core.database.models.base import BaseDatabaseModel


class AssignedTo(BaseDatabaseModel):
    """Model for permission assignment target."""
    
    type: Literal["user", "identity_group", "custom_group"] = Field(
        ...,
        description="Type of entity the permission is assigned to"
    )
    id: str = Field(
        ...,
        description="ID of the user or group"
    )


class PermissionModel(BaseDatabaseModel):
    """
    Permission model for resource-level access control.
    
    Permissions follow the pattern: {resource_type}/{resource_id}:{action}
    Examples:
        - tenants/abc123:read
        - tenants/abc123:write
        - tenants/abc123:admin
        - applications/xyz789:read
    """
    
    tenant_id: str = Field(
        ...,
        description="Tenant ID this permission belongs to"
    )
    
    resource_type: str = Field(
        ...,
        description="Type of resource (e.g., 'tenants', 'applications', 'conversations')"
    )
    
    resource_id: str = Field(
        ...,
        description="Specific resource ID"
    )
    
    action: str = Field(
        ...,
        description="Action allowed (e.g., 'read', 'write', 'admin', 'delete', 'invoke')"
    )
    
    scope: Literal["specific"] = Field(
        default="specific",
        description="Permission scope (currently only 'specific' supported)"
    )
    
    assigned_to: AssignedTo = Field(
        ...,
        description="Entity the permission is assigned to"
    )
    
    created_at: datetime = Field(
        ...,
        description="Timestamp when permission was created"
    )
    
    created_by: str = Field(
        ...,
        description="User ID who created this permission"
    )
