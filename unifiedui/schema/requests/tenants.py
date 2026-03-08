"""Request schemas for tenant operations."""

from pydantic import BaseModel, Field, field_validator

from unifiedui.core.database.enums import PrincipalTypeEnum, TenantRolesEnum


class CreateTenantRequest(BaseModel):
    """Schema for creating a new tenant."""

    name: str = Field(..., min_length=1, max_length=255, description="Name of the tenant")
    description: str | None = Field(None, max_length=2000, description="Optional description of the tenant")

    model_config = {
        "json_schema_extra": {"examples": [{"name": "Acme Corp", "description": "Main tenant for Acme Corporation"}]}
    }


class UpdateTenantRequest(BaseModel):
    """Schema for updating an existing tenant."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Name of the tenant")
    description: str | None = Field(None, max_length=2000, description="Optional description of the tenant")

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "Updated Tenant Name", "description": "Updated description for the tenant"}]
        }
    }


class SetPrincipalRequest(BaseModel):
    """Schema for setting/adding a role for a principal on a tenant."""

    principal_id: str = Field(..., description="ID of the principal (user or group)")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    role: str = Field(..., description="Role to assign (e.g., TENANT_GLOBAL_ADMIN, READER, CHAT_AGENTS_ADMIN, etc.)")

    @field_validator("principal_type")
    @classmethod
    def validate_principal_type(cls, v: str) -> str:
        """Validate that principal_type is a valid PrincipalTypeEnum value."""
        valid_types = [t.value for t in PrincipalTypeEnum]
        if v not in valid_types:
            raise ValueError(f"Invalid principal_type. Must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid TenantPermissionEnum value."""
        valid_roles = [r.value for r in TenantRolesEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"principal_id": "id", "principal_type": "IDENTITY_USER", "role": "TENANT_GLOBAL_ADMIN"},
                {"principal_id": "id", "principal_type": "IDENTITY_GROUP", "role": "READER"},
            ]
        }
    }


class DeletePrincipalRequest(BaseModel):
    """Schema for deleting a role for a principal on a tenant."""

    principal_id: str = Field(..., description="ID of the principal (user or group)")
    principal_type: str = Field(..., description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    role: str = Field(..., description="Role to remove (e.g., TENANT_GLOBAL_ADMIN, READER, CHAT_AGENTS_ADMIN, etc.)")

    @field_validator("principal_type")
    @classmethod
    def validate_principal_type(cls, v: str) -> str:
        """Validate that principal_type is a valid PrincipalTypeEnum value."""
        valid_types = [t.value for t in PrincipalTypeEnum]
        if v not in valid_types:
            raise ValueError(f"Invalid principal_type. Must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid TenantPermissionEnum value."""
        valid_roles = [r.value for r in TenantRolesEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [{"principal_id": "id", "principal_type": "IDENTITY_USER", "role": "TENANT_GLOBAL_ADMIN"}]
        }
    }
