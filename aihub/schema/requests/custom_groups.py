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
    
    member_ids: list[str] = Field(
        default_factory=list,
        description="Initial list of user IDs to add as members"
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


class AddMembersRequest(BaseModel):
    """Request model for adding members to a group."""
    
    member_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of user IDs to add to the group"
    )


class RemoveMembersRequest(BaseModel):
    """Request model for removing members from a group."""
    
    member_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of user IDs to remove from the group"
    )
