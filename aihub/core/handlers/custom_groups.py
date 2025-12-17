"""Custom groups handler for business logic."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import CustomGroup, CustomGroupPermission
from aihub.caching.client import CacheClient
from aihub.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    UpdateCustomGroupRequest,
    SetCustomGroupPermissionRequest,
    DeleteCustomGroupPermissionRequest
)
from aihub.schema.responses.custom_groups import (
    CustomGroupResponse,
    CustomGroupPermissionResponse,
    CustomGroupPermissionsResponse
)
from aihub.exc.tenants import TenantNotFoundError
from aihub.logger import get_logger

logger = get_logger(__name__)


class CustomGroupHandler:
    """Handler for custom group operations."""
    
    def __init__(self, db_client: SQLAlchemyClient, cache_client: Optional[CacheClient] = None):
        self.db = db_client
        self.cache = cache_client
    
    def list_custom_groups(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None
    ) -> list[CustomGroupResponse]:
        """List all custom groups in a tenant."""
        with self.db.get_session() as session:
            query = select(CustomGroup).where(CustomGroup.tenant_id == tenant_id)
            
            if name_filter:
                query = query.where(CustomGroup.name.ilike(f"%{name_filter}%"))
            
            query = query.offset(skip).limit(limit)
            groups = session.execute(query).scalars().all()
            
            return [self._to_response(group) for group in groups]
    
    def get_custom_group(self, tenant_id: str, custom_group_id: str) -> CustomGroupResponse:
        """Get a specific custom group by ID."""
        with self.db.get_session() as session:
            query = select(CustomGroup).where(
                CustomGroup.id == custom_group_id,
                CustomGroup.tenant_id == tenant_id
            )
            group = session.execute(query).scalar_one_or_none()
            
            if not group:
                raise TenantNotFoundError(f"Custom group {custom_group_id} not found")
            
            return self._to_response(group)
    
    def create_custom_group(
        self,
        tenant_id: str,
        group_data: CreateCustomGroupRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """Create a new custom group and assign creator as ADMIN."""
        with self.db.get_session() as session:
            # Create the group
            group = CustomGroup(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                name=group_data.name,
                description=group_data.description,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(group)
            session.flush()
            
            # Add creator as ADMIN
            permission = CustomGroupPermission(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                custom_group_id=group.id,
                principal_id=user_id,
                action="ADMIN",
                name=f"ADMIN permission for {user_id}",
                description="Auto-created for group creator",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(permission)
            
            session.commit()
            session.refresh(group)
            
            logger.info(f"Created custom group {group.id} with creator {user_id} as ADMIN")
            return self._to_response(group)
    
    def update_custom_group(
        self,
        tenant_id: str,
        custom_group_id: str,
        group_data: UpdateCustomGroupRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """Update an existing custom group."""
        with self.db.get_session() as session:
            query = select(CustomGroup).where(
                CustomGroup.id == custom_group_id,
                CustomGroup.tenant_id == tenant_id
            )
            group = session.execute(query).scalar_one_or_none()
            
            if not group:
                raise TenantNotFoundError(f"Custom group {custom_group_id} not found")
            
            if group_data.name is not None:
                group.name = group_data.name
            if group_data.description is not None:
                group.description = group_data.description
            
            group.updated_by = user_id
            group.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(group)
            
            logger.info(f"Updated custom group {custom_group_id}")
            return self._to_response(group)
    
    def delete_custom_group(self, tenant_id: str, custom_group_id: str) -> None:
        """Delete a custom group."""
        with self.db.get_session() as session:
            query = select(CustomGroup).where(
                CustomGroup.id == custom_group_id,
                CustomGroup.tenant_id == tenant_id
            )
            group = session.execute(query).scalar_one_or_none()
            
            if not group:
                raise TenantNotFoundError(f"Custom group {custom_group_id} not found")
            
            session.delete(group)
            session.commit()
            
            logger.info(f"Deleted custom group {custom_group_id}")
    
    def get_custom_group_permissions(
        self,
        tenant_id: str,
        custom_group_id: str
    ) -> CustomGroupPermissionsResponse:
        """Get all permissions for a custom group."""
        with self.db.get_session() as session:
            query = select(CustomGroupPermission).where(
                CustomGroupPermission.custom_group_id == custom_group_id,
                CustomGroupPermission.tenant_id == tenant_id
            )
            permissions = session.execute(query).scalars().all()
            
            return CustomGroupPermissionsResponse(
                custom_group_id=custom_group_id,
                tenant_id=tenant_id,
                permissions=[self._permission_to_response(p) for p in permissions]
            )
    
    def set_custom_group_permission(
        self,
        tenant_id: str,
        custom_group_id: str,
        permission_data: SetCustomGroupPermissionRequest,
        user_id: str
    ) -> CustomGroupPermissionsResponse:
        """Set a permission for a principal on a custom group."""
        with self.db.get_session() as session:
            # Check if permission already exists
            query = select(CustomGroupPermission).where(
                CustomGroupPermission.custom_group_id == custom_group_id,
                CustomGroupPermission.tenant_id == tenant_id,
                CustomGroupPermission.principal_id == permission_data.principal_id,
                CustomGroupPermission.action == permission_data.action
            )
            existing = session.execute(query).scalar_one_or_none()
            
            if not existing:
                # Create new permission
                permission = CustomGroupPermission(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    custom_group_id=custom_group_id,
                    principal_id=permission_data.principal_id,
                    action=permission_data.action,
                    name=f"{permission_data.action} permission for {permission_data.principal_id}",
                    description=f"Permission granted by {user_id}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(permission)
                session.commit()
                
                logger.info(f"Added {permission_data.action} permission for {permission_data.principal_id} on group {custom_group_id}")
            
            return self.get_custom_group_permissions(tenant_id, custom_group_id)
    
    def delete_custom_group_permission(
        self,
        tenant_id: str,
        custom_group_id: str,
        permission_data: DeleteCustomGroupPermissionRequest
    ) -> CustomGroupPermissionsResponse:
        """Delete a permission from a custom group."""
        with self.db.get_session() as session:
            query = select(CustomGroupPermission).where(
                CustomGroupPermission.custom_group_id == custom_group_id,
                CustomGroupPermission.tenant_id == tenant_id,
                CustomGroupPermission.principal_id == permission_data.principal_id,
                CustomGroupPermission.action == permission_data.action
            )
            permission = session.execute(query).scalar_one_or_none()
            
            if permission:
                session.delete(permission)
                session.commit()
                logger.info(f"Deleted {permission_data.action} permission for {permission_data.principal_id} on group {custom_group_id}")
            
            return self.get_custom_group_permissions(tenant_id, custom_group_id)
    
    @staticmethod
    def _to_response(group: CustomGroup) -> CustomGroupResponse:
        """Convert CustomGroup model to response."""
        return CustomGroupResponse(
            id=group.id,
            tenant_id=group.tenant_id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            updated_at=group.updated_at,
            created_by=group.created_by,
            updated_by=group.updated_by
        )
    
    @staticmethod
    def _permission_to_response(permission: CustomGroupPermission) -> CustomGroupPermissionResponse:
        """Convert CustomGroupPermission model to response."""
        return CustomGroupPermissionResponse(
            id=permission.id,
            principal_id=permission.principal_id,
            action=permission.action,
            created_at=permission.created_at
        )
