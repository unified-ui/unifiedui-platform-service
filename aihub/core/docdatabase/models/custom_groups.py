"""Custom group data models."""
from datetime import datetime
from pydantic import Field

from aihub.core.docdatabase.models.base import BaseDatabaseModel


class CustomGroupModel(BaseDatabaseModel):
    """
    Custom group model for tenant-specific user groups.
    
    Custom groups are managed within the application and are tenant-scoped.
    """
    
    tenant_id: str = Field(
        ...,
        description="Tenant ID this group belongs to"
    )
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Group name"
    )
    
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Group description"
    )
    
    member_ids: list[str] = Field(
        default_factory=list,
        description="List of user IDs that are members of this group"
    )
    
    created_at: datetime = Field(
        ...,
        description="Timestamp when group was created"
    )
    
    updated_at: datetime = Field(
        ...,
        description="Timestamp when group was last updated"
    )
    
    created_by: str = Field(
        ...,
        description="User ID who created this group"
    )
    
    updated_by: str = Field(
        ...,
        description="User ID who last updated this group"
    )
