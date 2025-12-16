from datetime import datetime
from pydantic import BaseModel, Field

# filepath: /Users/enricogoerlitz/Developer/repos/aihub/aihub/schema/responses/tenants.py


class TenantResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the tenant")
    name: str = Field(..., description="Name of the tenant")
    description: str | None = Field(None, description="Optional description of the tenant")
    meta: dict | None = Field(None, description="Optional metadata for the tenant")
    created_at: datetime = Field(..., description="Timestamp when the tenant was created")
    updated_at: datetime = Field(..., description="Timestamp when the tenant was last updated")
