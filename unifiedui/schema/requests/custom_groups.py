"""Request schemas for custom groups."""
from pydantic import BaseModel, Field, field_validator

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


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


class SetPrincipalRoleRequest(BaseModel):
    """Request model for setting a principal role on a custom group."""
    
    principal_id: str = Field(..., description="Principal ID")
    principal_type: str = Field(..., description="Principal type (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    role: str = Field(..., description="Role to grant (READ, WRITE, ADMIN)")

    @field_validator('principal_type')
    @classmethod
    def validate_principal_type(cls, v: str) -> str:
        """Validate that principal_type is a valid PrincipalTypeEnum value."""
        valid_types = [t.value for t in PrincipalTypeEnum]
        if v not in valid_types:
            raise ValueError(f"Invalid principal_type. Must be one of: {', '.join(valid_types)}")
        return v

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid PermissionActionEnum value."""
        valid_roles = [r.value for r in PermissionActionEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v


class DeletePrincipalRoleRequest(BaseModel):
    """Request model for deleting a principal role from a custom group."""
    
    principal_id: str = Field(..., description="Principal ID")
    principal_type: str = Field(..., description="Principal type (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    role: str = Field(..., description="Role to remove (READ, WRITE, ADMIN)")

    @field_validator('principal_type')
    @classmethod
    def validate_principal_type(cls, v: str) -> str:
        """Validate that principal_type is a valid PrincipalTypeEnum value."""
        valid_types = [t.value for t in PrincipalTypeEnum]
        if v not in valid_types:
            raise ValueError(f"Invalid principal_type. Must be one of: {', '.join(valid_types)}")
        return v

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid PermissionActionEnum value."""
        valid_roles = [r.value for r in PermissionActionEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v


class SetCustomGroupRoleRequest(BaseModel):
    """Request model for setting a role on a custom group."""
    principal_id: str = Field(..., description="ID of the principal (user or group)")
    role: str = Field(..., description="Role action (READ, WRITE, ADMIN)")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid PermissionActionEnum value."""
        valid_roles = [r.value for r in PermissionActionEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v


class DeleteCustomGroupRoleRequest(BaseModel):
    """Request model for deleting a role from a custom group."""
    principal_id: str = Field(..., description="ID of the principal (user or group)")
    role: str = Field(..., description="Role action (READ, WRITE, ADMIN)")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is a valid PermissionActionEnum value."""
        valid_roles = [r.value for r in PermissionActionEnum]
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v
