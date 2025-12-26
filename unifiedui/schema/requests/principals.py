"""Request schemas for principal operations."""
from pydantic import BaseModel, Field
from typing import Literal


class RefreshPrincipalRequest(BaseModel):
    """Request to refresh a principal from the identity provider."""
    tenant_id: str = Field(..., description="The tenant ID where the principal should be stored")
    type: Literal["IDENTITY_USER", "IDENTITY_GROUP"] = Field(
        ..., 
        description="The type of principal to refresh (IDENTITY_USER or IDENTITY_GROUP)"
    )
