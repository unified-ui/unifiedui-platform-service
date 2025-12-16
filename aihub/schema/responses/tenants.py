from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

# filepath: /Users/enricogoerlitz/Developer/repos/aihub/aihub/schema/responses/tenants.py


class TenantResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the tenant")
    name: str = Field(..., description="Name of the tenant")
    description: str | None = Field(None, description="Optional description of the tenant")
    meta: dict | None = Field(None, description="Optional metadata for the tenant")
    created_at: str = Field(..., description="Timestamp when the tenant was created")
    updated_at: str = Field(..., description="Timestamp when the tenant was last updated")


class TenantsListResponse(BaseModel):
    """Response schema for listing tenants."""
    tenants: List[TenantResponse] = Field(..., description="List of tenants")
    total: int = Field(..., description="Total number of tenants")
    skip: int = Field(0, description="Number of items skipped")
    limit: int = Field(100, description="Maximum number of items returned")
