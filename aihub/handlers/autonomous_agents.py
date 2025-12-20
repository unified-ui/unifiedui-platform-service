"""Business logic handlers for autonomous agent operations."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import select, or_

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import AutonomousAgent, AutonomousAgentMember
from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from aihub.caching.client import CacheClient

if TYPE_CHECKING:
    from aihub.core.identity.users import ContextIdentityUser

from aihub.schema.requests.autonomous_agents import CreateAutonomousAgentRequest, UpdateAutonomousAgentRequest
from aihub.schema.requests.autonomous_agent_permissions import SetAutonomousAgentPermissionRequest
from aihub.schema.responses.autonomous_agents import AutonomousAgentResponse
from aihub.schema.responses.autonomous_agent_permissions import (
    AutonomousAgentPermissionResponse,
    AutonomousAgentPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.autonomous_agents import AutonomousAgentNotFoundError
from aihub.logger import get_logger

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
            use_cache: Whether to use caching
            
        Returns:
            List of autonomous agent responses
        """
        from aihub.core.database.enums import TenantPermissionEnum
        
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
                for p in [TenantPermissionEnum.GLOBAL_ADMIN.value, TenantPermissionEnum.AUTONOMOUS_AGENTS_ADMIN.value]
            )
        
        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]
        
        # Build cache key
        filter_key = name_filter or "all"
        cache_key = f"autonomous_agents:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:filter:{filter_key}"
        
        # Check cache
        if use_cache and self.cache_client:
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
                query = select(AutonomousAgent).where(AutonomousAgent.tenant_id == tenant_id)
                if name_filter:
                    query = query.where(AutonomousAgent.name.ilike(f"%{name_filter}%"))
                query = query.offset(skip).limit(limit)
                autonomous_agents = session.execute(query).scalars().all()
            else:
                # Filter by permissions: user must have at least READ permission
                query = (
                    select(AutonomousAgent)
                    .join(AutonomousAgentMember, AutonomousAgent.id == AutonomousAgentMember.autonomous_agent_id)
                    .where(AutonomousAgent.tenant_id == tenant_id)
                )
                
                # Add permission filters
                permission_filters = []
                
                # User permission
                permission_filters.append(
                    (AutonomousAgentMember.principal_id == user_id) &
                    (AutonomousAgentMember.principal_type == PrincipalTypeEnum.IDENTITY_USER.value)
                )
                
                # Identity group permissions
                if identity_group_ids:
                    permission_filters.append(
                        (AutonomousAgentMember.principal_id.in_(identity_group_ids)) &
                        (AutonomousAgentMember.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value)
                    )
                
                # Custom group permissions
                if custom_group_ids:
                    permission_filters.append(
                        (AutonomousAgentMember.principal_id.in_(custom_group_ids)) &
                        (AutonomousAgentMember.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value)
                    )
                
                query = query.where(or_(*permission_filters))
                
                if name_filter:
                    query = query.where(AutonomousAgent.name.ilike(f"%{name_filter}%"))
                
                query = query.distinct().offset(skip).limit(limit)
                autonomous_agents = session.execute(query).scalars().all()
            
            # Convert to response models
            responses = [AutonomousAgentResponse.model_validate(agent) for agent in autonomous_agents]
            
            # Cache the results
            if use_cache and self.cache_client:
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
            query = select(AutonomousAgent).where(
                AutonomousAgent.id == autonomous_agent_id,
                AutonomousAgent.tenant_id == tenant_id
            )
            autonomous_agent = session.execute(query).scalar_one_or_none()
            
            if not autonomous_agent:
                raise AutonomousAgentNotFoundError(autonomous_agent_id)
            
            response = AutonomousAgentResponse.model_validate(autonomous_agent)
            
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
        user_id: str
    ) -> AutonomousAgentResponse:
        """
        Create a new autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            request: Autonomous agent creation data
            user_id: ID of the user creating the autonomous agent
            
        Returns:
            Created autonomous agent response
        """
        logger.info("Creating autonomous agent", extra={"tenant_id": tenant_id, "name": request.name, "user_id": user_id})
        
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
            
            # Add creator as ADMIN member
            member = AutonomousAgentMember(
                id=member_id,
                tenant_id=tenant_id,
                autonomous_agent_id=autonomous_agent_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.ADMIN.value,
                name=f"Member-{user_id}",
                created_by=user_id,
                updated_by=user_id
            )
            session.add(member)
            
            session.commit()
            session.refresh(autonomous_agent)
            
            response = AutonomousAgentResponse.model_validate(autonomous_agent)
            
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
            query = select(AutonomousAgent).where(
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
            session.refresh(autonomous_agent)
            
            response = AutonomousAgentResponse.model_validate(autonomous_agent)
            
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
                key = (member.principal_id, member.principal_type)
                if key not in principals_dict:
                    principals_dict[key] = {
                        "autonomous_agent_id": autonomous_agent_id,
                        "tenant_id": tenant_id,
                        "principal_id": member.principal_id,
                        "principal_type": member.principal_type,
                        "permissions": []
                    }
                principals_dict[key]["permissions"].append(member.role)
            
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
                    permissions=[]
                )
            
            # Get principal type from first member
            principal_type = members[0].principal_type
            permissions = [member.role for member in members]
            
            return PrincipalPermissionsResponse(
                autonomous_agent_id=autonomous_agent_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                permissions=permissions
            )

    def set_autonomous_agent_permission(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        request: SetAutonomousAgentPermissionRequest,
        user_id: str
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
            "permission": request.permission,
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
            
            # Check if member exists with this role
            query = select(AutonomousAgentMember).where(
                AutonomousAgentMember.autonomous_agent_id == autonomous_agent_id,
                AutonomousAgentMember.principal_id == request.principal_id,
                AutonomousAgentMember.principal_type == request.principal_type.value,
                AutonomousAgentMember.role == request.permission.value
            )
            member = session.execute(query).scalar_one_or_none()
            
            # Create member if not exists
            if not member:
                member_id = str(uuid.uuid4())
                member = AutonomousAgentMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    autonomous_agent_id=autonomous_agent_id,
                    principal_id=request.principal_id,
                    principal_type=request.principal_type.value,
                    role=request.permission.value,
                    name=f"Member-{request.principal_id}",
                    created_by=user_id,
                    updated_by=user_id
                )
                session.add(member)
                session.flush()  # Get the member ID
            else:
                # Member with role already exists
                logger.debug(f"Member with role already exists for principal {request.principal_id}")
            
            session.commit()
            session.refresh(member)
            
            # Build response
            response = AutonomousAgentPermissionResponse(
                id=member.id,
                autonomous_agent_id=autonomous_agent_id,
                tenant_id=tenant_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type,
                action=request.permission,
                created_at=member.created_at,
                updated_at=member.updated_at
            )
            
            # Invalidate caches
            self._invalidate_permissions_cache(tenant_id, autonomous_agent_id)
            self._invalidate_list_cache(tenant_id)
            
            logger.info(f"Set permission for principal {request.principal_id} on autonomous agent {autonomous_agent_id}")
            return response

    def delete_autonomous_agent_permission(
        self,
        tenant_id: str,
        autonomous_agent_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
    ) -> None:
        """
        Delete a permission for a principal on an autonomous agent.
        
        Args:
            tenant_id: The ID of the tenant
            autonomous_agent_id: The ID of the autonomous agent
            principal_id: The ID of the principal
            principal_type: The type of principal
            permission: The permission to delete
            
        Raises:
            AutonomousAgentNotFoundError: If autonomous agent not found
        """
        logger.info("Deleting autonomous agent permission", extra={
            "tenant_id": tenant_id,
            "autonomous_agent_id": autonomous_agent_id,
            "principal_id": principal_id,
            "permission": permission
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
                AutonomousAgentMember.principal_type == principal_type,
                AutonomousAgentMember.role == permission
            )
            member = session.execute(query).scalar_one_or_none()
            
            if not member:
                logger.debug(f"No member with role {permission} found for principal {principal_id}, nothing to delete")
                return
            
            # Delete the member
            session.delete(member)
            session.commit()
            
            # Invalidate caches
            self._invalidate_permissions_cache(tenant_id, autonomous_agent_id)
            self._invalidate_list_cache(tenant_id)
            
            logger.info(f"Deleted permission {permission} for principal {principal_id} on autonomous agent {autonomous_agent_id}")

    @staticmethod
    def _group_permissions_by_principal(results) -> list[dict]:
        """Helper to group permissions by principal."""
        principals_dict = {}
        for member, permission in results:
            key = (member.principal_id, member.principal_type)
            if key not in principals_dict:
                principals_dict[key] = {
                    "principal_id": member.principal_id,
                    "principal_type": member.principal_type,
                    "permissions": []
                }
            principals_dict[key]["permissions"].append(permission.permission)
        return list(principals_dict.values())

    @staticmethod
    def _validate_principal_type(principal_type: str) -> bool:
        """Validate that principal_type is valid."""
        return principal_type in [
            PrincipalTypeEnum.IDENTITY_USER.value,
            PrincipalTypeEnum.IDENTITY_GROUP.value,
            PrincipalTypeEnum.CUSTOM_GROUP.value
        ]
