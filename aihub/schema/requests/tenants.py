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
    """Schema for setting/adding a permission for a principal on a tenant."""
    principal_type: str = Field(
        ...,
        description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)"
    )
    permission: str = Field(
        ...,
        description="Permission to assign (e.g., GLOBAL_ADMIN, READER, APPLICATIONS_ADMIN, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"principal_type": "IDENTITY_USER", "permission": "GLOBAL_ADMIN"},
                {"principal_type": "IDENTITY_GROUP", "permission": "READER"}
            ]
        }
    }


class DeletePrincipalRequest(BaseModel):
    """Schema for deleting a permission for a principal on a tenant."""
    principal_type: str = Field(
        ...,
        description="Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)"
    )
    permission: str = Field(
        ...,
        description="Permission to remove (e.g., GLOBAL_ADMIN, READER, APPLICATIONS_ADMIN, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"principal_type": "IDENTITY_USER", "permission": "GLOBAL_ADMIN"}
            ]
        }
    }
