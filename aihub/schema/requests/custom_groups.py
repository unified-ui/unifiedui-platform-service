"""Request schemas for custom groups."""
from pydantic import BaseModel, Field


class CreateCustomGroupRequest(BaseModel):
    """Request model for creating a custom group."""
    
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


class UpdateCustomGroupRequest(BaseModel):
    """Request model for updating a custom group."""
    
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Group name"
    )
    
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Group description"
    )


class SetPrincipalPermissionRequest(BaseModel):
    """Request model for setting a principal permission on a custom group."""
    
    principal_id: str = Field(..., description="Principal ID")
    principal_type: str = Field(..., description="Principal type (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    permission: str = Field(..., description="Permission to grant (READ, WRITE, ADMIN)")


class DeletePrincipalPermissionRequest(BaseModel):
    """Request model for deleting a principal permission from a custom group."""
    
    principal_id: str = Field(..., description="Principal ID")
    principal_type: str = Field(..., description="Principal type (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    permission: str = Field(..., description="Permission to remove (READ, WRITE, ADMIN)")


class SetCustomGroupPermissionRequest(BaseModel):
    """Request model for setting a permission on a custom group."""
    principal_id: str = Field(..., description="ID of the principal (user or group)")
    action: str = Field(..., description="Permission action (READ, WRITE, ADMIN)")


class DeleteCustomGroupPermissionRequest(BaseModel):
    """Request model for deleting a permission from a custom group."""
    principal_id: str = Field(..., description="ID of the principal (user or group)")
    action: str = Field(..., description="Permission action (READ, WRITE, ADMIN)")
