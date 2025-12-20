"""Business logic handlers for conversation operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import select

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import Conversation, ConversationMember
from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from aihub.caching.client import CacheClient

if TYPE_CHECKING:
    from aihub.core.identity.users import ContextIdentityUser

from aihub.schema.requests.conversations import CreateConversationRequest, UpdateConversationRequest
from aihub.schema.requests.conversation_permissions import SetConversationPermissionRequest
from aihub.schema.responses.conversations import ConversationResponse
from aihub.schema.responses.conversation_permissions import (
    ConversationPermissionResponse,
    ConversationPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.conversations import ConversationNotFoundError
from aihub.logger import get_logger

logger = get_logger(__name__)


class ConversationHandler:
    """Handler class for conversation business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None
    ):
        """
        Initialize the conversation handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_conversations(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None,
        use_cache: bool = True
    ) -> List[ConversationResponse]:
        """
        Get a list of conversations for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by conversation name
            use_cache: Whether to use caching
            
        Returns:
            List of conversation responses
        """
        from aihub.core.database.enums import TenantPermissionEnum
        
        logger.info("Listing conversations", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        # Check if user is admin (has GLOBAL_ADMIN or CONVERSATIONS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next(
            (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
            None
        )
        
        is_admin = False
        if matching_tenant:
            user_permissions = matching_tenant["permissions"]
            admin_permissions = [
                TenantPermissionEnum.GLOBAL_ADMIN.value,
                TenantPermissionEnum.CONVERSATIONS_ADMIN.value
            ]
            is_admin = any(perm in user_permissions for perm in admin_permissions)
        
        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]
        
        # Build cache key
        filter_key = name_filter or "all"
        cache_key = f"conversations:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:filter:{filter_key}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached conversation list")
                    return [ConversationResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached conversation list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(Conversation.tenant_id == tenant_id)
            
            # Filter by permissions if not admin
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)
                
                # Subquery for conversations where user is a member
                member_subquery = (
                    select(ConversationMember.conversation_id)
                    .where(
                        ConversationMember.tenant_id == tenant_id,
                        ConversationMember.principal_id.in_(principal_ids)
                    )
                    .distinct()
                )
                
                query = query.where(Conversation.id.in_(member_subquery))
            
            if name_filter:
                query = query.where(Conversation.name.ilike(f"%{name_filter}%"))
            
            query = query.offset(skip).limit(limit)
            conversations = session.execute(query).scalars().all()
            
            logger.info("Retrieved conversations", extra={"count": len(conversations)})
            result = [self._model_to_response(conv) for conv in conversations]
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug(f"Cached conversation list")
                except Exception as e:
                    logger.warning(f"Failed to cache conversation list: {e}")
            
            return result

    def get_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
        use_cache: bool = True
    ) -> ConversationResponse:
        """
        Get a specific conversation by ID.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            use_cache: Whether to use caching
            
        Returns:
            Conversation response
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Fetching conversation", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        # Build cache key
        cache_key = f"conversations:detail:tenant:{tenant_id}:conv:{conversation_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached conversation")
                    return ConversationResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached conversation: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            result = self._model_to_response(conversation)
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug(f"Cached conversation detail")
                except Exception as e:
                    logger.warning(f"Failed to cache conversation: {e}")
            
            return result

    def create_conversation(
        self,
        tenant_id: str,
        request: CreateConversationRequest,
        user_id: str
    ) -> ConversationResponse:
        """
        Create a new conversation.
        
        Args:
            tenant_id: The ID of the tenant
            request: Conversation creation data
            user_id: The ID of the user creating the conversation
            
        Returns:
            Created conversation response
        """
        logger.info("Creating conversation", extra={"tenant_id": tenant_id, "name": request.name})
        
        conversation_id = str(uuid.uuid4())
        
        with self.db_client.get_session() as session:
            # Create conversation
            conversation = Conversation(
                id=conversation_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(conversation)
            
            # Add creator as admin member
            member_id = str(uuid.uuid4())
            member = ConversationMember(
                id=member_id,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.ADMIN.value,
                name=f"Member: {user_id}",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(member)
            
            session.commit()
            session.refresh(conversation)
            
            logger.info("Conversation created", extra={"conversation_id": conversation_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            
            return self._model_to_response(conversation)

    def update_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
        request: UpdateConversationRequest,
        user_id: str
    ) -> ConversationResponse:
        """
        Update an existing conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            request: Conversation update data
            user_id: The ID of the user updating the conversation
            
        Returns:
            Updated conversation response
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Updating conversation", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            # Update fields if provided
            if request.name is not None:
                conversation.name = request.name
            if request.description is not None:
                conversation.description = request.description
            
            conversation.updated_by = user_id
            
            session.commit()
            session.refresh(conversation)
            
            logger.info("Conversation updated", extra={"conversation_id": conversation_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, conversation_id)
            
            return self._model_to_response(conversation)

    def delete_conversation(
        self,
        tenant_id: str,
        conversation_id: str
    ) -> None:
        """
        Delete a conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Deleting conversation", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        with self.db_client.get_session() as session:
            query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            session.delete(conversation)
            session.commit()
            
            logger.info("Conversation deleted", extra={"conversation_id": conversation_id})
            
            # Invalidate cache
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, conversation_id)
            self._invalidate_permissions_cache(tenant_id, conversation_id)

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate list cache for a tenant."""
        if self.cache_client:
            pattern = f"conversations:list:tenant:{tenant_id}:*"
            self.cache_client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, conversation_id: str) -> None:
        """Invalidate detail cache for a conversation."""
        if self.cache_client:
            cache_key = f"conversations:detail:tenant:{tenant_id}:conv:{conversation_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, conversation_id: str) -> None:
        """Invalidate permissions cache for a conversation."""
        if self.cache_client:
            pattern = f"conversations:permissions:tenant:{tenant_id}:conv:{conversation_id}:*"
            self.cache_client.delete_pattern(pattern)

    # ========== Permission Management Methods ==========

    def list_conversation_permissions(
        self,
        tenant_id: str,
        conversation_id: str,
        use_cache: bool = True
    ) -> ConversationPrincipalsResponse:
        """
        List all permissions for a conversation, grouped by principal.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            use_cache: Whether to use caching
            
        Returns:
            Grouped principals with their permissions
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info("Listing conversation permissions", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
        
        # Build cache key
        cache_key = f"conversations:permissions:tenant:{tenant_id}:conv:{conversation_id}:list"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached permissions list")
                    return ConversationPrincipalsResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached permissions: {e}")
        
        with self.db_client.get_session() as session:
            # Verify conversation exists
            conv_query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(conv_query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            # Get all members and their roles
            members_query = (
                select(ConversationMember)
                .where(ConversationMember.conversation_id == conversation_id)
            )
            members = session.execute(members_query).scalars().all()
            
            # Group roles by principal
            principals_dict = {}
            for member in members:
                key = (member.principal_id, member.principal_type)
                if key not in principals_dict:
                    principals_dict[key] = {
                        "principal_id": member.principal_id,
                        "principal_type": member.principal_type,
                        "permissions": []
                    }
                
                # Get role from member
                principals_dict[key]["permissions"].append(member.role)
            
            principals = [
                PrincipalPermissionsResponse(
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    **data
                )
                for data in principals_dict.values()
            ]
            
            result = ConversationPrincipalsResponse(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                principals=principals
            )
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug(f"Cached permissions list")
                except Exception as e:
                    logger.warning(f"Failed to cache permissions: {e}")
            
            return result

    def get_conversation_permission(
        self,
        tenant_id: str,
        conversation_id: str,
        principal_id: str
    ) -> PrincipalPermissionsResponse:
        """
        Get all permissions for a specific principal on a conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            principal_id: The ID of the principal
            
        Returns:
            Principal with all their permissions
            
        Raises:
            ConversationNotFoundError: If conversation or permission not found
        """
        logger.info(
            "Getting conversation permission",
            extra={"tenant_id": tenant_id, "conversation_id": conversation_id, "principal_id": principal_id}
        )
        
        with self.db_client.get_session() as session:
            # Verify conversation exists
            conv_query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(conv_query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            # Get members for this principal
            member_query = (
                select(ConversationMember)
                .where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.principal_id == principal_id
                )
            )
            members = session.execute(member_query).scalars().all()
            
            if not members:
                raise ConversationNotFoundError(f"No permissions found for principal {principal_id}")
            
            # Collect all roles and get principal_type from first member
            permissions = []
            principal_type = members[0].principal_type
            for member in members:
                if member.role not in permissions:
                    permissions.append(member.role)
            
            return PrincipalPermissionsResponse(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                permissions=permissions
            )

    def set_conversation_permission(
        self,
        tenant_id: str,
        conversation_id: str,
        request: SetConversationPermissionRequest,
        user_id: str
    ) -> ConversationPermissionResponse:
        """
        Set or update a permission for a principal on a conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            request: Permission data
            user_id: The ID of the user setting the permission
            
        Returns:
            Created or updated permission
            
        Raises:
            ConversationNotFoundError: If conversation not found
        """
        logger.info(
            "Setting conversation permission",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "principal_id": request.principal_id
            }
        )
        
        with self.db_client.get_session() as session:
            # Verify conversation exists
            conv_query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(conv_query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            # Find or create member with this role
            member_query = (
                select(ConversationMember)
                .where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.principal_id == request.principal_id,
                    ConversationMember.principal_type == request.principal_type.value,
                    ConversationMember.role == request.permission.value
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                # Create new member with role
                member_id = str(uuid.uuid4())
                member = ConversationMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    principal_id=request.principal_id,
                    principal_type=request.principal_type.value,
                    role=request.permission.value,
                    name=f"Member: {request.principal_id}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(member)
                session.commit()
                session.refresh(member)
                
                logger.info("Member with role created", extra={"member_id": member_id})
                
                result = ConversationPermissionResponse(
                    id=member.id,
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    principal_id=request.principal_id,
                    principal_type=request.principal_type,
                    action=request.permission,
                    created_at=member.created_at,
                    updated_at=member.updated_at
                )
            else:
                # Member with role already exists
                logger.info("Member with role already exists", extra={"member_id": member.id})
                result = ConversationPermissionResponse(
                    id=member.id,
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    principal_id=request.principal_id,
                    principal_type=request.principal_type,
                    action=request.permission,
                    created_at=member.created_at,
                    updated_at=member.updated_at
                )
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, conversation_id)
            
            return result

    def delete_conversation_permission(
        self,
        tenant_id: str,
        conversation_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
    ) -> None:
        """
        Delete a specific permission for a principal on a conversation.
        
        Args:
            tenant_id: The ID of the tenant
            conversation_id: The ID of the conversation
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to delete
            
        Raises:
            ConversationNotFoundError: If conversation or permission not found
        """
        logger.info(
            "Deleting conversation permission",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "principal_id": principal_id,
                "permission": permission
            }
        )
        
        with self.db_client.get_session() as session:
            # Verify conversation exists
            conv_query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
            conversation = session.execute(conv_query).scalar_one_or_none()
            
            if not conversation:
                raise ConversationNotFoundError(conversation_id)
            
            # Find member with this role
            member_query = (
                select(ConversationMember)
                .where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.principal_id == principal_id,
                    ConversationMember.principal_type == principal_type,
                    ConversationMember.role == permission
                )
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                raise ConversationNotFoundError(f"Member with role {permission} not found for principal {principal_id}")
            
            session.delete(member)
            session.commit()
            
            logger.info("Member with role deleted")
            
            # Invalidate cache
            self._invalidate_permissions_cache(tenant_id, conversation_id)

    @staticmethod
    def _model_to_response(conversation: Conversation) -> ConversationResponse:
        """Convert Conversation model to ConversationResponse."""
        return ConversationResponse(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            name=conversation.name,
            description=conversation.description,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            created_by=conversation.created_by,
            updated_by=conversation.updated_by
        )
