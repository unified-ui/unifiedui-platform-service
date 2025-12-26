"""Response schemas for development platform permissions."""
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class DevelopmentPlatformPermissionResponse(BaseModel):
    """Response model for a development platform permission."""
    
    id: str = Field(..., description="Permission ID")
    development_platform_id: str = Field(..., description="Development platform ID")
    tenant_id: str = Field(..., description="Tenant ID")
    principal_id: str = Field(..., description="Principal ID")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    role: PermissionActionEnum = Field(..., description="Role assigned to the principal")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    model_config = ConfigDict(from_attributes=True)


class PrincipalPermissionsResponse(BaseModel):
    """Response model for a principal's permissions on a development platform."""
    development_platform_id: str = Field(..., description="Development platform ID")
    tenant_id: str = Field(..., description="Tenant ID")
    principal_id: str = Field(..., description="Principal ID")
    principal_type: str = Field(..., description="Principal type (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    roles: list[str] = Field(..., description="List of roles")


class DevelopmentPlatformPrincipalsResponse(BaseModel):
    """Response containing all principals and their roles for a development platform."""
    development_platform_id: str = Field(..., description="The development platform ID")
    tenant_id: str = Field(..., description="The tenant ID")
    principals: list[PrincipalPermissionsResponse] = Field(..., description="List of principals with their roles")
