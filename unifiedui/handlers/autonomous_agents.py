"""Business logic handlers for autonomous agent operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import AutonomousAgent, AutonomousAgentMember, AutonomousAgentTag, Tag
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.caching.client import CacheClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

from unifiedui.schema.requests.autonomous_agents import CreateAutonomousAgentRequest, UpdateAutonomousAgentRequest
from unifiedui.schema.requests.autonomous_agent_permissions import SetAutonomousAgentPermissionRequest
from unifiedui.schema.responses.autonomous_agents import AutonomousAgentResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.autonomous_agent_permissions import (
    AutonomousAgentPermissionResponse,
    AutonomousAgentPrincipalsResponse,
    PrincipalPermissionsResponse
)
from unifiedui.exc.autonomous_agents import AutonomousAgentNotFoundError, AutonomousAgentPermissionNotFoundError
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class AutonomousAgentHandler:
    """Handler class for autonomous agent business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None
    ):
        """
        Initialize the autonomous agent handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_autonomous_agents(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None,
        is_active: Optional[int] = None,
        tag_ids: Optional[List[int]] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        use_cache: bool = True
    ) -> List[AutonomousAgentResponse]:
        """
        Get a list of autonomous agents for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by autonomous agent name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (agents must have ALL specified tags)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching
            
        Returns:
            List of autonomous agent responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum
        
        logger.info("Listing autonomous agents", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        # Check if user is admin (has GLOBAL_ADMIN or AUTONOMOUS_AGENTS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next(
            (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
            None
        )
        
        is_admin = False
        if matching_tenant:
            tenant_permissions = matching_tenant.get("permissions", [])
            is_admin = any(
                p in tenant_permissions 
                for p in [TenantRolesEnum.GLOBAL_ADMIN.value, TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN.value]
            )
        
        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            # groups now contains both IDENTITY_GROUP and CUSTOM_GROUP with principal_type attribute
            identity_group_ids = [
                g.id for g in user.groups 
                if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
            ]
            custom_group_ids = [
                g.id for g in user.groups 
                if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value
            ]
        
        # Build cache key (without filters - caching only for unfiltered results)
        cache_key = f"autonomous_agents:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}"
        
        # Check if any filters are applied
        has_filters = name_filter is not None or is_active is not None or tag_ids is not None or order_by is not None
        
        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached autonomous agents for tenant {tenant_id}, user {user_id}")
                    return [AutonomousAgentResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached autonomous agents: {e}")
        
        with self.db_client.get_session() as session:
            # If user is admin, return all autonomous agents
            if is_admin:
                query = select(AutonomousAgent).options(
                    selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag)
                ).where(AutonomousAgent.tenant_id == tenant_id)
                if name_filter:
                    query = query.where(AutonomousAgent.name.ilike(f"%{name_filter}%"))
                # Filter by is_active status
                if is_active is not None:
                    query = query.where(AutonomousAgent.is_active == bool(is_active))
                # Filter by tags (agents must have ALL specified tags)
                if tag_ids:
                    for tag_id in tag_ids:
                        tag_subquery = (
                            select(AutonomousAgentTag.autonomous_agent_id)
                            .where(
                                AutonomousAgentTag.tenant_id == tenant_id,
                                AutonomousAgentTag.tag_id == tag_id
                            )
                        )
                        query = query.where(AutonomousAgent.id.in_(tag_subquery))
                # Apply ordering if specified
                if order_by and hasattr(AutonomousAgent, order_by):
                    column = getattr(AutonomousAgent, order_by)
                    if order_direction == "desc":
                        query = query.order_by(column.desc())
                    else:
                        query = query.order_by(column.asc())
                query = query.offset(skip).limit(limit)
                autonomous_agents = session.execute(query).scalars().all()
            else:
                # Filter by permissions: user must have at least READ permission
                query = (
                    select(AutonomousAgent)
                    .options(
                        selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag)
                    )
                    .join(AutonomousAgentMember, AutonomousAgent.id == AutonomousAgentMember.autonomous_agent_id)
                    .where(AutonomousAgent.tenant_id == tenant_id)
                )
                
                # Add permission filters
                permission_filters = []
                
                # User permission
                permission_filters.append(
                    (AutonomousAgentMember.principal_id == user_id)
                )
                
                # Identity group permissions
                if identity_group_ids:
                    permission_filters.append(
                        (AutonomousAgentMember.principal_id.in_(identity_group_ids))
                    )
                
                # Custom group permissions
                if custom_group_ids:
                    permission_filters.append(
                        (AutonomousAgentMember.principal_id.in_(custom_group_ids))
                    )
                
                query = query.where(or_(*permission_filters))
                
                if name_filter:
                    query = query.where(AutonomousAgent.name.ilike(f"%{name_filter}%"))
                
                # Filter by is_active status
                if is_active is not None:
                    query = query.where(AutonomousAgent.is_active == bool(is_active))
                
                # Filter by tags (agents must have ALL specified tags)
                if tag_ids:
                    for tag_id in tag_ids:
                        tag_subquery = (
                            select(AutonomousAgentTag.autonomous_agent_id)
                            .where(
                                AutonomousAgentTag.tenant_id == tenant_id,
                                AutonomousAgentTag.tag_id == tag_id
                            )
                        )
                        query = query.where(AutonomousAgent.id.in_(tag_subquery))
                
                # Apply ordering if specified
                if order_by and hasattr(AutonomousAgent, order_by):
                    column = getattr(AutonomousAgent, order_by)
                    if order_direction == "desc":
                        query = query.order_by(column.desc())
                    else:
                        query = query.order_by(column.asc())
                
                query = query.distinct().offset(skip).limit(limit)
                autonomous_agents = session.execute(query).scalars().all()
            
            # Convert to response models
            responses = [self._model_to_response(agent) for agent in autonomous_agents]
            
            # Cache the results (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    cache_data = [r.model_dump() for r in responses]
                    self.cache_client.client.set(cache_key, cache_data, ttl=300)
                    logger.debug(f"Cached autonomous agents list for tenant {tenant_id}, user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to cache autonomous agents: {e}")
            
            return responses

    def get_autonomous_agent(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        use_cache: bool = True
    ) -> AutonomousAgentResponse:
        """
        Get a specific autonomous agent by ID.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            use_cache: Whether to use caching
            
        Returns:
            Autonomous agent response
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Fetching autonomous agent", extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id})
        
        # Build cache key
        cache_key = f"autonomous_agents:detail:tenant:{tenant_id}:agent:{autonomous_agent_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached autonomous agent {autonomous_agent_id}")
                    return AutonomousAgentResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached autonomous agent: {e}")
        
        with self.db_client.get_session() as session:
            query = select(AutonomousAgent).options(
                selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag)
            ).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            response = self._model_to_response(autonomous_agent)
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, response.model_dump(), ttl=300)
                    logger.debug(f"Cached autonomous agent {autonomous_agent_id}")
                except Exception as e:
                    logger.warning(f"Failed to cache autonomous agent: {e}")
            
            return response

    def create_autonomous_agent(
        self,
        tenant_id: str,
        request: CreateAutonomousAgentRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> AutonomousAgentResponse:
        """
        Create a new autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            request: Autonomous agent creation data
            user_id: ID of the user creating the autonomous agent
            user: The authenticated user context (for IDP access)
            
        Returns:
            Created autonomous agent response
        """
        logger.info("Creating autonomous agent", extra={"tenant_id": tenant_id, "agent_name": request.name, "user_id": user_id})
        
        autonomous_agent_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())
        permission_id = str(uuid.uuid4())
        
        with self.db_client.get_session() as session:
            # Create autonomous agent
            autonomous_agent = AutonomousAgent(
                id=autonomous_agent_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                config=request.config or {},
                created_by=user_id,
                updated_by=user_id
            )
            session.add(autonomous_agent)
            
            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                user=user
            )
            
            # Add creator as ADMIN member
            member = AutonomousAgentMember(
                id=member_id,
                tenant_id=tenant_id,
                autonomous_agent_id=autonomous_agent_id,
                principal_id=user_id,
                role=PermissionActionEnum.ADMIN,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(member)
            
            session.commit()
            session.refresh(autonomous_agent)
            
            response = self._model_to_response(autonomous_agent)
            
            # Invalidate list cache
            self._invalidate_list_cache(tenant_id)
            
            logger.info(f"Created autonomous agent {autonomous_agent_id}")
            return response

    def update_autonomous_agent(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        request: UpdateAutonomousAgentRequest,
        user_id: str
    ) -> AutonomousAgentResponse:
        """
        Update an existing autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            request: Autonomous agent update data
            user_id: ID of the user updating the autonomous agent
            
        Returns:
            Updated autonomous agent response
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Updating autonomous agent", extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id, "user_id": user_id})
        
        with self.db_client.get_session() as session:
            query = select(AutonomousAgent).options(
                selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag)
            ).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            # Update fields if provided
            if request.name is not None:
                autonomous_agent.name = request.name
            if request.description is not None:
                autonomous_agent.description = request.description
            if request.config is not None:
                autonomous_agent.config = request.config
            
            autonomous_agent.updated_by = user_id
            
            session.commit()
            
            # Re-fetch with tags to ensure they are loaded
            query = select(AutonomousAgent).options(
                selectinload(AutonomousAgent.tags).selectinload(AutonomousAgentTag.tag)
            ).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            response = self._model_to_response(autonomous_agent)
            
            # Invalidate caches
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, autonomous_agent_id)
            
            logger.info(f"Updated autonomous agent {autonomous_agent_id}")
            return response

    def delete_autonomous_agent(
        self,
        tenant_id: str,
        autonomous_agent_id: str
    ) -> None:
        """
        Delete an autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Deleting autonomous agent", extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id})
        
        with self.db_client.get_session() as session:
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            session.delete(autonomous_agent)
            session.commit()
            
            # Invalidate caches
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, autonomous_agent_id)
            self._invalidate_permissions_cache(tenant_id, autonomous_agent_id)
            
            logger.info(f"Deleted autonomous agent {autonomous_agent_id}")

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate all list caches for a tenant."""
        if self.cache_client:
            self.cache_client.client.delete_pattern(f"autonomous_agents:list:tenant:{tenant_id}:*")

    def _invalidate_detail_cache(self, tenant_id: str, autonomous_agent_id: str) -> None:
        """Invalidate detail cache for a specific autonomous agent."""
        if self.cache_client:
            self.cache_client.client.delete(f"autonomous_agents:detail:tenant:{tenant_id}:agent:{autonomous_agent_id}")

    def _invalidate_permissions_cache(self, tenant_id: str, autonomous_agent_id: str) -> None:
        """Invalidate permissions cache for a specific autonomous agent."""
        if self.cache_client:
            self.cache_client.client.delete(f"autonomous_agents:permissions:tenant:{tenant_id}:agent:{autonomous_agent_id}")

    # ========== Permission Management Methods ==========

    def list_autonomous_agent_permissions(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        use_cache: bool = True
    ) -> AutonomousAgentPrincipalsResponse:
        """
        Get all permissions for an autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            use_cache: Whether to use caching
            
        Returns:
            List of principals with their permissions
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Listing autonomous agent permissions", extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id})
        
        # Build cache key
        cache_key = f"autonomous_agents:permissions:tenant:{tenant_id}:agent:{autonomous_agent_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached permissions for autonomous agent {autonomous_agent_id}")
                    return AutonomousAgentPrincipalsResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached permissions: {e}")
        
        with self.db_client.get_session() as session:
            # Verify autonomous agent exists
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            # Get all members and their roles
            query = (
                select(AutonomousAgentMember)
                .where(AutonomousAgentMember.autonomous_agent_id == autonomous_agent_id)
            )
            members = session.execute(query).scalars().all()
            
            # Group roles by principal
            principals_dict = {}
            for member in members:
                key = (member.principal_id, member.principal.principal_type)
                if key not in principals_dict:
                    principals_dict[key] = {
                        "autonomous_agent_id": autonomous_agent_id,
                        "tenant_id": tenant_id,
                        "principal_id": member.principal_id,
                        "principal_type": member.principal.principal_type,
                        "roles": []
                    }
                principals_dict[key]["roles"].append(member.role)
            
            # Convert to response models
            principals = [PrincipalPermissionsResponse(**data) for data in principals_dict.values()]
            
            response = AutonomousAgentPrincipalsResponse(
                autonomous_agent_id=autonomous_agent_id,
                tenant_id=tenant_id,
                principals=principals
            )
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, response.model_dump(), ttl=300)
                    logger.debug(f"Cached permissions for autonomous agent {autonomous_agent_id}")
                except Exception as e:
                    logger.warning(f"Failed to cache permissions: {e}")
            
            return response

    def get_autonomous_agent_permission(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        principal_id: str
    ) -> PrincipalPermissionsResponse:
        """
        Get permissions for a specific principal on an autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            principal_id: The ID of the principal
            
        Returns:
            Principal's permissions
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Getting autonomous agent permission for principal", extra={
            "tenant_id": tenant_id,
            "autonomous_agent_id": autonomous_agent_id,
            "principal_id": principal_id
        })
        
        with self.db_client.get_session() as session:
            # Verify autonomous agent exists
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            # Get members and roles for the principal
            query = (
                select(AutonomousAgentMember)
                .where(
                    AutonomousAgentMember.autonomous_agent_id == autonomous_agent_id,
                    AutonomousAgentMember.principal_id == principal_id
                )
            )
            members = session.execute(query).scalars().all()
            
            if not members:
                return PrincipalPermissionsResponse(
                    autonomous_agent_id=autonomous_agent_id,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    principal_type="",
                    roles=[]
                )
            
            # Get principal type from first member
            principal_type = members[0].principal.principal_type
            roles = [member.role for member in members]
            
            return PrincipalPermissionsResponse(
                autonomous_agent_id=autonomous_agent_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                roles=roles
            )

    def set_autonomous_agent_permission(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        request: SetAutonomousAgentPermissionRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> AutonomousAgentPermissionResponse:
        """
        Set or update a permission for a principal on an autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            request: Permission setting data
            user_id: ID of the user setting the permission
            
        Returns:
            Created or updated permission response
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Setting autonomous agent permission", extra={
            "tenant_id": tenant_id,
            "autonomous_agent_id": autonomous_agent_id,
            "principal_id": request.principal_id,
            "agent_role": request.role,
            "user_id": user_id
        })
        
        with self.db_client.get_session() as session:
            # Verify autonomous agent exists
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                user=user
            )
            
            # Check if member exists
            query = select(AutonomousAgentMember).where(
                AutonomousAgentMember.autonomous_agent_id == autonomous_agent_id,
                AutonomousAgentMember.principal_id == request.principal_id
            )
            member = session.execute(query).scalar_one_or_none()
            
            # Create or update member
            if not member:
                member_id = str(uuid.uuid4())
                member = AutonomousAgentMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    autonomous_agent_id=autonomous_agent_id,
                    principal_id=request.principal_id,
                    role=request.role,
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(member)
                session.flush()  # Get the member ID
            else:
                # Update existing member's role
                member.role = request.role
                member.updated_by = user_id
                session.flush()
            
            session.commit()
            session.refresh(member)
            
            # Build response
            response = AutonomousAgentPermissionResponse(
                id=member.id,
                autonomous_agent_id=autonomous_agent_id,
                tenant_id=tenant_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type,
                role=request.role,
                created_at=member.created_at,
                updated_at=member.updated_at
            )
            
            # Invalidate caches
            self._invalidate_permissions_cache(tenant_id, autonomous_agent_id)
            self._invalidate_list_cache(tenant_id)
            
            # Invalidate user cache so list operations reflect new permissions
            if self.cache_client:
                try:
                    if request.principal_type.value == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(request.principal_id)
                        logger.debug(f"Cleared cache for user {request.principal_id} after permission change")
                    # Also clear cache for the user making the change
                    self.cache_client.clear_cache_for_user(user_id)
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")
            
            logger.info(f"Set permission for principal {request.principal_id} on autonomous agent {autonomous_agent_id}")
            return response

    def delete_autonomous_agent_permission(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        principal_id: str,
        principal_type: str,
        role: str
    ) -> None:
        """
        Delete a permission for a principal on an autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            principal_id: The ID of the principal
            principal_type: The type of principal
            role: The role to delete
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Deleting autonomous agent permission", extra={
            "tenant_id": tenant_id,
            "autonomous_agent_id": autonomous_agent_id,
            "principal_id": principal_id,
            "agent_role": role
        })
        
        with self.db_client.get_session() as session:
            # Verify autonomous agent exists
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            # Get member with specific role
            query = select(AutonomousAgentMember).where(
                AutonomousAgentMember.autonomous_agent_id == autonomous_agent_id,
                AutonomousAgentMember.principal_id == principal_id,
                AutonomousAgentMember.role == role
            )
            member = session.execute(query).scalar_one_or_none()
            
            if not member:
                raise AutonomousAgentPermissionNotFoundError(principal_id)
            
            # Delete the member
            session.delete(member)
            session.commit()
            
            # Invalidate caches
            self._invalidate_permissions_cache(tenant_id, autonomous_agent_id)
            self._invalidate_list_cache(tenant_id)
            
            # Invalidate user cache so list operations reflect new permissions
            if self.cache_client:
                try:
                    if principal_type == "IDENTITY_USER":
                        self.cache_client.clear_cache_for_user(principal_id)
                        logger.debug(f"Cleared cache for user {principal_id} after permission deletion")
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")
            
            logger.info(f"Deleted role {role} for principal {principal_id} on autonomous agent {autonomous_agent_id}")

    @staticmethod
    def _group_permissions_by_principal(results) -> list[dict]:
        """Helper to group permissions by principal."""
        principals_dict = {}
        for member, permission in results:
            key = (member.principal_id, member.principal.principal_type)
            if key not in principals_dict:
                principals_dict[key] = {
                    "principal_id": member.principal_id,
                    "principal_type": member.principal.principal_type,
                    "roles": []
                }
            principals_dict[key]["roles"].append(permission.permission)
        return list(principals_dict.values())

    @staticmethod
    def _model_to_response(agent: AutonomousAgent) -> AutonomousAgentResponse:
        """Convert AutonomousAgent model to AutonomousAgentResponse."""
        # Extract tags from the agent's tags relationship
        tags = []
        if hasattr(agent, 'tags') and agent.tags:
            for agent_tag in agent.tags:
                if agent_tag.tag:
                    tags.append(TagSummary(
                        id=agent_tag.tag.id,
                        name=agent_tag.tag.name
                    ))
        
        return AutonomousAgentResponse(
            id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            description=agent.description,
            is_active=agent.is_active,
            config=agent.config,
            tags=tags,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            created_by=agent.created_by,
            updated_by=agent.updated_by
        )

    @staticmethod
    def _validate_principal_type(principal_type: str) -> bool:
        """Validate that principal_type is valid."""
        return principal_type in [
            PrincipalTypeEnum.IDENTITY_USER.value,
            PrincipalTypeEnum.IDENTITY_GROUP.value,
            PrincipalTypeEnum.CUSTOM_GROUP.value
        ]
