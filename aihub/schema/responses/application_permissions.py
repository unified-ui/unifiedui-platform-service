"""Response schemas for application permissions."""
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum


class ApplicationPermissionResponse(BaseModel):
    """Response model for an application permission."""
    
    id: str = Field(..., description="Permission ID")
    application_id: str = Field(..., description="Application ID")
    tenant_id: str = Field(..., description="Tenant ID")
    principal_id: str = Field(..., description="Principal ID")
    principal_type: PrincipalTypeEnum = Field(..., description="Type of principal")
    action: PermissionActionEnum = Field(..., description="Permission action")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class PrincipalPermissionsResponse(BaseModel):
    """Response model for a principal's permissions on an application."""
    application_id: str = Field(..., description="Application ID")
    tenant_id: str = Field(..., description="Tenant ID")
    principal_id: str = Field(..., description="Principal ID")
    principal_type: str = Field(..., description="Principal type (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)")
    permissions: list[str] = Field(..., description="List of permissions")


class ApplicationPrincipalsResponse(BaseModel):
    """Response containing all principals and their permissions for an application."""
    application_id: str = Field(..., description="The application ID")
    tenant_id: str = Field(..., description="The tenant ID")
    principals: list[PrincipalPermissionsResponse] = Field(..., description="List of principals with their permissions")
