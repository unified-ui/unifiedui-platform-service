from typing import TypeVar

from pydantic import BaseModel, Field

from unifiedui.schema.responses.organizations import OrganizationContextResponse


class IdentityGroupResponse(BaseModel):
    """Identity group response model."""

    id: str
    display_name: str
    principal_name: str | None = None
    principal_type: str | None = None  # IDENTITY_GROUP or CUSTOM_GROUP


class IdentityUserResponse(BaseModel):
    """Identity user response model."""

    id: str
    identity_provider: str
    identity_tenant_id: str | None = None
    display_name: str
    principal_name: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    mail: str | None = None
    organization: OrganizationContextResponse | None = None
    tenants: list[dict] | None = None
    groups: list[IdentityGroupResponse] | None = None


T = TypeVar("T")


class PaginatedIdentityResponse[T](BaseModel):
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
