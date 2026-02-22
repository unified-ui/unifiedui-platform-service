"""Request schemas for organization operations."""

from pydantic import BaseModel, Field, field_validator

from unifiedui.core.database.enums import (
    EnvironmentTypeEnum,
    OrganizationRoleEnum,
    PrincipalTypeEnum,
)


class CreateOrganizationRequest(BaseModel):
    """Schema for creating a new organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Name of the organization")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-friendly slug for the organization")
    description: str | None = Field(None, max_length=2000, description="Optional description")
    identity_provider: str = Field(..., max_length=50, description="Identity provider name (e.g., entra_id)")
    identity_tenant_id: str = Field(..., max_length=255, description="IDP tenant identifier")
    subscription_tier: str = Field("free", max_length=50, description="Subscription tier")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format (lowercase alphanumeric and hyphens only)."""
        import re

        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v) and len(v) > 1:
            raise ValueError("Slug must contain only lowercase letters, numbers and hyphens")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Acme Corp",
                    "slug": "acme-corp",
                    "description": "Acme Corporation",
                    "identity_provider": "entra_id",
                    "identity_tenant_id": "abc-123",
                }
            ]
        }
    }


class UpdateOrganizationRequest(BaseModel):
    """Schema for updating an existing organization."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Name of the organization")
    description: str | None = Field(None, max_length=2000, description="Optional description")
    subscription_tier: str | None = Field(None, max_length=50, description="Subscription tier")
    is_active: bool | None = Field(None, description="Whether the organization is active")

    model_config = {
        "json_schema_extra": {"examples": [{"name": "Updated Org Name", "description": "Updated description"}]}
    }


class SetOrganizationMemberRequest(BaseModel):
    """Schema for adding/setting a member role in the organization."""

    principal_id: str = Field(..., description="ID of the principal (user or group)")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER or IDENTITY_GROUP)")
    role: str = Field(..., description="Organization role to assign")

    @field_validator("principal_type")
    @classmethod
    def validate_principal_type(cls, v: str) -> str:
        """Validate that principal_type is IDENTITY_USER or IDENTITY_GROUP."""
        valid_types = [PrincipalTypeEnum.IDENTITY_USER.value, PrincipalTypeEnum.IDENTITY_GROUP.value]
        if v not in valid_types:
            raise ValueError(f"Invalid principal_type. Must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid OrganizationRoleEnum value."""
        valid_roles = [r.value for r in OrganizationRoleEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "principal_id": "user-id",
                    "principal_type": "IDENTITY_USER",
                    "role": "ORGANISATION_TENANT_ADMIN",
                }
            ]
        }
    }


class DeleteOrganizationMemberRequest(BaseModel):
    """Schema for removing a member role from the organization."""

    principal_id: str = Field(..., description="ID of the principal (user or group)")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER or IDENTITY_GROUP)")
    role: str = Field(..., description="Organization role to remove")

    @field_validator("principal_type")
    @classmethod
    def validate_principal_type(cls, v: str) -> str:
        """Validate that principal_type is IDENTITY_USER or IDENTITY_GROUP."""
        valid_types = [PrincipalTypeEnum.IDENTITY_USER.value, PrincipalTypeEnum.IDENTITY_GROUP.value]
        if v not in valid_types:
            raise ValueError(f"Invalid principal_type. Must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid OrganizationRoleEnum value."""
        valid_roles = [r.value for r in OrganizationRoleEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "principal_id": "user-id",
                    "principal_type": "IDENTITY_USER",
                    "role": "ORGANISATION_TENANT_ADMIN",
                }
            ]
        }
    }


class CreateTenantInOrganizationRequest(BaseModel):
    """Schema for creating a new tenant within an organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Name of the tenant")
    description: str | None = Field(None, max_length=2000, description="Optional description")
    environment_type: str = Field(
        EnvironmentTypeEnum.SANDBOX.value,
        description="Environment type (SANDBOX or PRODUCTION)",
    )
    previous_stage_id: str | None = Field(None, description="ID of the previous stage tenant for promotion")
    is_default: bool = Field(False, description="Whether this is the default tenant")

    @field_validator("environment_type")
    @classmethod
    def validate_environment_type(cls, v: str) -> str:
        """Validate that environment_type is a valid EnvironmentTypeEnum value."""
        valid_types = [t.value for t in EnvironmentTypeEnum]
        if v not in valid_types:
            raise ValueError(f"Invalid environment_type. Must be one of: {', '.join(valid_types)}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Development",
                    "description": "Development environment",
                    "environment_type": "SANDBOX",
                }
            ]
        }
    }
