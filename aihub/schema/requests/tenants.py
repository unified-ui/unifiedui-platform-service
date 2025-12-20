"""Request schemas for tenant operations."""
from pydantic import BaseModel, Field
from typing import Optional


class CreateTenantRequest(BaseModel):
    """Schema for creating a new tenant."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the tenant")
    description: Optional[str] = Field(None, max_length=2000, description="Optional description of the tenant")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Acme Corp",
                    "description": "Main tenant for Acme Corporation"
                }
            ]
        }
    }


class UpdateTenantRequest(BaseModel):
    """Schema for updating an existing tenant."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Name of the tenant")
    description: Optional[str] = Field(None, max_length=2000, description="Optional description of the tenant")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Updated Tenant Name",
                    "description": "Updated description for the tenant"
                }
            ]
        }
    }


class SetPrincipalRequest(BaseModel):
    """Schema for setting/adding a role for a principal on a tenant."""
    principal_id: str = Field(
        ...,
        description="ID of the principal (user or group)"
    )
    principal_type: str = Field(
        ...,
        description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)"
    )
    role: str = Field(
        ...,
        description="Role to assign (e.g., GLOBAL_ADMIN, READER, APPLICATIONS_ADMIN, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"principal_id": "id", "principal_type": "IDENTITY_USER", "role": "GLOBAL_ADMIN"},
                {"principal_id": "id", "principal_type": "IDENTITY_GROUP", "role": "READER"}
            ]
        }
    }


class DeletePrincipalRequest(BaseModel):
    """Schema for deleting a role for a principal on a tenant."""
    principal_id: str = Field(
        ...,
        description="ID of the principal (user or group)"
    )
    principal_type: str = Field(
        ...,
        description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)"
    )
    role: str = Field(
        ...,
        description="Role to remove (e.g., GLOBAL_ADMIN, READER, APPLICATIONS_ADMIN, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"principal_id": "id", "principal_type": "IDENTITY_USER", "role": "GLOBAL_ADMIN"}
            ]
        }
    }
