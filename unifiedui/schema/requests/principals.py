"""Request schemas for principal operations."""

from typing import Literal

from pydantic import BaseModel, Field


class RefreshPrincipalRequest(BaseModel):
    """Request to refresh a principal from the identity provider."""

    tenant_id: str = Field(..., description="The tenant ID where the principal should be stored")
    type: Literal["IDENTITY_USER", "IDENTITY_GROUP"] = Field(
        ..., description="The type of principal to refresh (IDENTITY_USER or IDENTITY_GROUP)"
    )


class TenantRefreshPrincipalRequest(BaseModel):
    """Request to refresh a principal from identity provider (tenant-scoped endpoint)."""

    principal_type: Literal["IDENTITY_USER", "IDENTITY_GROUP"] = Field(
        ..., description="The type of principal to refresh (IDENTITY_USER or IDENTITY_GROUP)"
    )


class UpdatePrincipalStatusRequest(BaseModel):
    """Request to update a principal's is_active status."""

    is_active: bool = Field(..., description="Whether the principal should be active")
