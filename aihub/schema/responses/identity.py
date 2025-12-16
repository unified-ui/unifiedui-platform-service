from pydantic import BaseModel, Field
from typing import Generic, TypeVar


class IdentityGroupResponse(BaseModel):
    """Identity group response model."""
    id: str
    display_name: str


class IdentityUserResponse(BaseModel):
    """Identity user response model."""
    id: str
    display_name: str
    firstname: str | None = None
    lastname: str | None = None
    mail: str | None = None
    groups: list[IdentityGroupResponse] | None = None
    custom_groups: list[IdentityGroupResponse] | None = None


T = TypeVar('T')


class PaginatedIdentityResponse(BaseModel, Generic[T]):
    """Paginated response model for identity resources."""
    value: list[T] = Field(description="List of items")
    next_link: str | None = Field(default=None, description="Link to the next page of results")


class IdentityUsersResponse(BaseModel):
    """Paginated response for users."""
    value: list[IdentityUserResponse] = Field(description="List of users")
    next_link: str | None = Field(default=None, description="Link to the next page of results")


class IdentityGroupsResponse(BaseModel):
    """Paginated response for groups."""
    value: list[IdentityGroupResponse] = Field(description="List of groups")
    next_link: str | None = Field(default=None, description="Link to the next page of results")
