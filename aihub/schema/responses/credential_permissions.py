"""Response schemas for credential permissions."""
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class CredentialPermissionResponse(BaseModel):
    """Response model for a credential permission."""
    
    id: str = Field(..., description="Permission ID")
    credential_id: str = Field(..., description="Credential ID")
    tenant_id: str = Field(..., description="Tenant ID")
    principal_id: str = Field(..., description="Principal ID")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    action: PermissionActionEnum = Field(..., description="Permission action")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class CredentialPermissionsListResponse(BaseModel):
    """Response model for list of credential permissions."""
    
    permissions: List[CredentialPermissionResponse] = Field(..., description="List of permissions")
    total: int = Field(..., description="Total number of permissions")
