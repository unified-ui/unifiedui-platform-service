"""Response schemas for organization operations."""

from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    """Response schema for an organization."""

    id: str = Field(..., description="Unique identifier for the organization")
    name: str = Field(..., description="Name of the organization")
    slug: str = Field(..., description="URL-friendly slug")
    description: str | None = Field(None, description="Optional description")
    identity_provider: str = Field(..., description="Identity provider name")
    identity_tenant_id: str = Field(..., description="IDP tenant identifier")
    subscription_tier: str = Field(..., description="Subscription tier")
    max_tenants: int = Field(..., description="Maximum number of tenants")
    max_users: int = Field(..., description="Maximum number of users")
    is_active: bool = Field(..., description="Whether the organization is active")
    created_at: datetime = Field(..., description="Timestamp when created")
    updated_at: datetime = Field(..., description="Timestamp when last updated")
    created_by: str | None = Field(None, description="User ID who created this")
    updated_by: str | None = Field(None, description="User ID who last updated this")


class OrganizationMemberRoleResponse(BaseModel):
    """Response for an organization member role entry."""

    id: str = Field(..., description="Unique identifier for the membership entry")
    principal_id: str = Field(..., description="ID of the principal")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER or IDENTITY_GROUP)")
    role: str = Field(..., description="Organization role")
    created_at: datetime = Field(..., description="Timestamp when assigned")


class OrganizationMemberResponse(BaseModel):
    """Response for a single principal with their organization roles."""

    principal_id: str = Field(..., description="The principal ID")
    principal_type: str = Field(..., description="Type of principal")
    display_name: str | None = Field(None, description="Display name of the principal")
    principal_name: str | None = Field(None, description="Principal name (email for users)")
    mail: str | None = Field(None, description="Email address if available")
    roles: list[OrganizationMemberRoleResponse] = Field(..., description="List of organization roles")


class OrganizationMembersResponse(BaseModel):
    """Response containing all members of an organization."""

    organization_id: str = Field(..., description="The organization ID")
    members: list[OrganizationMemberResponse] = Field(..., description="List of members with their roles")


class OrganizationContextResponse(BaseModel):
    """Organization context included in /me response."""

    id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    slug: str = Field(..., description="Organization slug")
    roles: list[str] = Field(..., description="User's roles in the organization")


class TenantWithOrganizationResponse(BaseModel):
    """Extended tenant response including organization context."""

    id: str = Field(..., description="Unique identifier for the tenant")
    name: str = Field(..., description="Name of the tenant")
    description: str | None = Field(None, description="Optional description")
    organization_id: str | None = Field(None, description="ID of the parent organization")
    environment_type: str = Field(..., description="Environment type (SANDBOX or PRODUCTION)")
    previous_stage_id: str | None = Field(None, description="ID of previous stage tenant")
    is_default: bool = Field(..., description="Whether this is the default tenant")
    can_be_deleted: bool = Field(..., description="Whether this tenant can be deleted")
    created_at: datetime = Field(..., description="Timestamp when created")
    updated_at: datetime = Field(..., description="Timestamp when last updated")
    created_by: str | None = Field(None, description="User ID who created this")
    updated_by: str | None = Field(None, description="User ID who last updated this")
