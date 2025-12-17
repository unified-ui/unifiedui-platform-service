"""Business logic handlers for custom group operations using SQLAlchemy."""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import CustomGroup, CustomGroupMember, CustomGroupMemberPermission
from aihub.caching.client import CacheClient
from aihub.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    UpdateCustomGroupRequest,
    SetPrincipalPermissionRequest,
    DeletePrincipalPermissionRequest
)
from aihub.schema.responses.custom_groups import (
    CustomGroupResponse,
    CustomGroupPrincipalsResponse,
    PrincipalsResponse
)
from aihub.exc.custom_groups import CustomGroupNotFoundError
from aihub.logger import get_logger

logger = get_logger(__name__)


class CustomGroupHandler:
    """Handler class for custom group business logic using SQLAlchemy."""
    
    def __init__(self, db_client: SQLAlchemyClient, cache_client: Optional[CacheClient] = None):
        """
        Initialize the custom group handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client
    
    def list_custom_groups(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None
    ) -> List[CustomGroupResponse]:
        """
        Get a list of custom groups in a tenant.
        
        Args:
            tenant_id: The ID of the tenant
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by group name (case-insensitive partial match)
            
        Returns:
            List of custom group responses
        """
        logger.info("Listing custom groups", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        with self.db_client.get_session() as session:
            query = select(CustomGroup).where(CustomGroup.tenant_id == tenant_id)
            
            if name_filter:
                query = query.where(CustomGroup.name.ilike(f"%{name_filter}%"))
            
            query = query.offset(skip).limit(limit)
            groups = session.execute(query).scalars().all()
            
            logger.info("Retrieved custom groups", extra={"count": len(groups)})
            return [self._model_to_response(group) for group in groups]
    
    def get_custom_group(self, tenant_id: str, custom_group_id: str) -> CustomGroupResponse:
        """
        Get a specific custom group by ID.
        
        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            
        Returns:
            Custom group response
            
        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info("Fetching custom group", extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id})
        
        with self.db_client.get_session() as session:
            query = select(CustomGroup).where(
                CustomGroup.id == custom_group_id,
                CustomGroup.tenant_id == tenant_id
            )
            group = session.execute(query).scalar_one_or_none()
            
            if not group:
                logger.warning("Custom group not found", extra={"custom_group_id": custom_group_id})
                raise CustomGroupNotFoundError(custom_group_id)
            
            logger.info("Custom group retrieved", extra={"custom_group_id": custom_group_id})
            return self._model_to_response(group)
    
    def create_custom_group(
        self,
        tenant_id: str,
        request: CreateCustomGroupRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """
        Create a new custom group and assign the creator as ADMIN.
        
        Args:
            tenant_id: The ID of the tenant
            request: Custom group creation data
            user_id: ID of the user creating the group (principal_id)
            
        Returns:
            Created custom group response
        """
        logger.info("Creating custom group", extra={"tenant_id": tenant_id, "group_name": request.name, "user_id": user_id})
        
        group_id = str(uuid.uuid4())
        
        with self.db_client.get_session() as session:
            # Create custom group
            group = CustomGroup(
                id=group_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(group)
            session.flush()
            
            # Create group member for the creator
            member_id = str(uuid.uuid4())
            group_member = CustomGroupMember(
                id=member_id,
                tenant_id=tenant_id,
                custom_group_id=group_id,
                principal_id=user_id,
                principal_type="IDENTITY_USER",
                name=f"Member: {user_id}",
                description=f"Custom group member for user {user_id} on group {request.name}",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(group_member)
            session.flush()
            
            # Create ADMIN permission for the member
            permission_id = str(uuid.uuid4())
            group_permission = CustomGroupMemberPermission(
                id=permission_id,
                custom_group_member_id=member_id,
                permission="ADMIN",
                name=f"ADMIN permission",
                description=f"Administrator permission for user {user_id} on group {request.name}",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(group_permission)
            
            session.commit()
            session.refresh(group)
            
            # Invalidate cache
            if self.cache_client:
                try:
                    cache_key = f"custom_groups:user:{user_id}:*"
                    self.cache_client.client.delete(cache_key)
                    logger.debug(f"Invalidated custom group cache for user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            logger.info("Custom group created", extra={"custom_group_id": group_id})
            return self._model_to_response(group)
    
    def update_custom_group(
        self,
        tenant_id: str,
        custom_group_id: str,
        request: UpdateCustomGroupRequest,
        user_id: str
    ) -> CustomGroupResponse:
        """
        Update an existing custom group.
        
        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group to update
            request: Custom group update data
            user_id: ID of the user updating the group
            
        Returns:
            Updated custom group response
            
        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info("Updating custom group", extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "user_id": user_id})
        
        with self.db_client.get_session() as session:
            query = select(CustomGroup).where(
                CustomGroup.id == custom_group_id,
                CustomGroup.tenant_id == tenant_id
            )
            group = session.execute(query).scalar_one_or_none()
            
            if not group:
                logger.warning("Custom group not found", extra={"custom_group_id": custom_group_id})
                raise CustomGroupNotFoundError(custom_group_id)
            
            if request.name is not None:
                group.name = request.name
            if request.description is not None:
                group.description = request.description
            
            group.updated_by = user_id
            group.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(group)
            
            logger.info("Custom group updated", extra={"custom_group_id": custom_group_id})
            return self._model_to_response(group)
    
    def delete_custom_group(self, tenant_id: str, custom_group_id: str) -> None:
        """
        Delete a custom group by ID.
        
        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group to delete
            
        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info("Deleting custom group", extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id})
        
        with self.db_client.get_session() as session:
            query = select(CustomGroup).where(
                CustomGroup.id == custom_group_id,
                CustomGroup.tenant_id == tenant_id
            )
            group = session.execute(query).scalar_one_or_none()
            
            if not group:
                logger.warning("Custom group not found", extra={"custom_group_id": custom_group_id})
                raise CustomGroupNotFoundError(custom_group_id)
            
            session.delete(group)
            session.commit()
            
            logger.info("Custom group deleted", extra={"custom_group_id": custom_group_id})
    
    def list_custom_group_principals(
        self,
        tenant_id: str,
        custom_group_id: str
    ) -> dict:
        """
        Get all principals and their permissions for a specific custom group.
        
        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            
        Returns:
            Dict with custom_group_id and list of principals with their permissions
            
        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info("Listing all principals for custom group", extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id})
        
        with self.db_client.get_session() as session:
            # Verify group exists
            group = session.get(CustomGroup, custom_group_id)
            if not group or group.tenant_id != tenant_id:
                raise CustomGroupNotFoundError(custom_group_id)
            
            # Get all members and their permissions
            query = (
                select(CustomGroupMember, CustomGroupMemberPermission)
                .join(CustomGroupMemberPermission, CustomGroupMember.id == CustomGroupMemberPermission.custom_group_member_id)
                .where(CustomGroupMember.custom_group_id == custom_group_id)
                .order_by(CustomGroupMember.principal_id, CustomGroupMemberPermission.permission)
            )
            
            results = session.execute(query).all()
            
            # Group by principal
            principals_dict = {}
            for member, permission in results:
                if member.principal_id not in principals_dict:
                    principals_dict[member.principal_id] = {
                        "principal_id": member.principal_id,
                        "principal_type": member.principal_type,
                        "permissions": []
                    }
                principals_dict[member.principal_id]["permissions"].append(permission.permission)
            
            principals = list(principals_dict.values())
            
            logger.info("Retrieved custom group principals", extra={"custom_group_id": custom_group_id, "principal_count": len(principals)})
            
            return {
                "custom_group_id": custom_group_id,
                "tenant_id": tenant_id,
                "principals": principals
            }
    
    def get_principal_permissions(
        self,
        tenant_id: str,
        custom_group_id: str,
        principal_id: str
    ) -> dict:
        """
        Get all permissions for a specific principal on a custom group.
        
        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            principal_id: The ID of the principal
            
        Returns:
            Dict with custom_group_id, principal_id, and permissions list
            
        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Getting principal permissions",
            extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "principal_id": principal_id}
        )
        
        with self.db_client.get_session() as session:
            # Verify group exists
            group = session.get(CustomGroup, custom_group_id)
            if not group or group.tenant_id != tenant_id:
                raise CustomGroupNotFoundError(custom_group_id)
            
            # Get member and permissions
            query = (
                select(CustomGroupMember, CustomGroupMemberPermission)
                .join(CustomGroupMemberPermission, CustomGroupMember.id == CustomGroupMemberPermission.custom_group_member_id)
                .where(
                    CustomGroupMember.custom_group_id == custom_group_id,
                    CustomGroupMember.principal_id == principal_id
                )
            )
            
            results = session.execute(query).all()
            
            if not results:
                # Principal has no permissions on this group
                return {
                    "custom_group_id": custom_group_id,
                    "tenant_id": tenant_id,
                    "principal_id": principal_id,
                    "principal_type": None,
                    "permissions": []
                }
            
            member = results[0][0]
            permissions = [perm.permission for _, perm in results]
            
            return {
                "custom_group_id": custom_group_id,
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": member.principal_type,
                "permissions": permissions
            }
    
    def set_principal_permission(
        self,
        tenant_id: str,
        custom_group_id: str,
        principal_id: str,
        principal_type: str,
        permission: str,
        user_id: str
    ) -> dict:
        """
        Add or update a permission for a principal on a custom group.
        
        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            permission: The permission to assign
            user_id: The ID of the user making the change
            
        Returns:
            Dict with custom_group_id, principal_id, and updated permissions list
            
        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Setting principal permission",
            extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "principal_id": principal_id, "permission": permission}
        )
        
        with self.db_client.get_session() as session:
            # Verify group exists
            group = session.get(CustomGroup, custom_group_id)
            if not group or group.tenant_id != tenant_id:
                raise CustomGroupNotFoundError(custom_group_id)
            
            # Find or create member
            query = select(CustomGroupMember).where(
                CustomGroupMember.custom_group_id == custom_group_id,
                CustomGroupMember.principal_id == principal_id,
                CustomGroupMember.principal_type == principal_type
            )
            member = session.execute(query).scalar_one_or_none()
            
            if not member:
                # Create new member
                member_id = str(uuid.uuid4())
                member = CustomGroupMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    custom_group_id=custom_group_id,
                    principal_id=principal_id,
                    principal_type=principal_type,
                    name=f"Member: {principal_id}",
                    description=f"Custom group member for principal {principal_id}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(member)
                session.flush()
            
            # Check if permission already exists
            query = select(CustomGroupMemberPermission).where(
                CustomGroupMemberPermission.custom_group_member_id == member.id,
                CustomGroupMemberPermission.permission == permission
            )
            existing_permission = session.execute(query).scalar_one_or_none()
            
            if not existing_permission:
                # Create new permission
                permission_id = str(uuid.uuid4())
                new_permission = CustomGroupMemberPermission(
                    id=permission_id,
                    custom_group_member_id=member.id,
                    permission=permission,
                    name=f"{permission} permission",
                    description=f"Permission granted by {user_id}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(new_permission)
            
            session.commit()
            
            logger.info(f"Set {permission} permission for {principal_id} on custom group {custom_group_id}")
            
            return self.get_principal_permissions(tenant_id, custom_group_id, principal_id)
    
    def delete_principal_permission(
        self,
        tenant_id: str,
        custom_group_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
    ) -> dict:
        """
        Remove a specific permission from a principal on a custom group.
        
        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to remove
            
        Returns:
            Dict with custom_group_id, principal_id, and remaining permissions list
            
        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Deleting principal permission",
            extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "principal_id": principal_id, "permission": permission}
        )
        
        with self.db_client.get_session() as session:
            # Verify group exists
            group = session.get(CustomGroup, custom_group_id)
            if not group or group.tenant_id != tenant_id:
                raise CustomGroupNotFoundError(custom_group_id)
            
            # Find member
            query = select(CustomGroupMember).where(
                CustomGroupMember.custom_group_id == custom_group_id,
                CustomGroupMember.principal_id == principal_id,
                CustomGroupMember.principal_type == principal_type
            )
            member = session.execute(query).scalar_one_or_none()
            
            if member:
                # Find and delete permission
                query = select(CustomGroupMemberPermission).where(
                    CustomGroupMemberPermission.custom_group_member_id == member.id,
                    CustomGroupMemberPermission.permission == permission
                )
                permission_obj = session.execute(query).scalar_one_or_none()
                
                if permission_obj:
                    session.delete(permission_obj)
                    
                    # Check if member has any remaining permissions
                    query = select(CustomGroupMemberPermission).where(
                        CustomGroupMemberPermission.custom_group_member_id == member.id
                    )
                    remaining_permissions = session.execute(query).scalars().all()
                    
                    # If no permissions left, delete the member
                    if not remaining_permissions:
                        session.delete(member)
                    
                    session.commit()
                    logger.info(f"Deleted {permission} permission for {principal_id} on custom group {custom_group_id}")
            
            return self.get_principal_permissions(tenant_id, custom_group_id, principal_id)
    
    @staticmethod
    def _model_to_response(group: CustomGroup) -> CustomGroupResponse:
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
