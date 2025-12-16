"""Request schemas for tenant operations."""
from pydantic import BaseModel, Field
from typing import Optional


class CreateTenantRequest(BaseModel):
    """Schema for creating a new tenant."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the tenant")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description of the tenant")
    meta: Optional[dict] = Field(None, description="Optional metadata for the tenant")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Acme Corp",
                    "description": "Main tenant for Acme Corporation",
                    "meta": {
                        "industry": "Technology",
                        "size": "Enterprise"
                    }
                }
            ]
        }
    }


class UpdateTenantRequest(BaseModel):
    """Schema for updating an existing tenant."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Name of the tenant")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description of the tenant")
    meta: Optional[dict] = Field(None, description="Optional metadata for the tenant")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated description for the tenant",
                    "meta": {
                        "status": "active",
                        "updated_by": "admin"
                    }
                }
            ]
        }
    }
