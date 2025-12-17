from typing import TYPE_CHECKING, Optional

from aihub.core.handlers.tenants import TenantHandler
from aihub.core.docdatabase.models.permissions import AssignedTo
from aihub.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from aihub.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from aihub.schema.responses.tenants import TenantResponse
from aihub.utils.api_query import APIFilterQuery
from aihub.docdatabase.client import DatabaseClient
from aihub.caching.client import CacheClient
from aihub.logger import get_logger

logger = get_logger(__name__)


class IdentityUser:
    def __init__(
        self,
        token: str,
        database_client: Optional["DatabaseClient"] = None,
        cache_client: Optional[CacheClient] = None,
        use_cache: bool = True
    ):
        self.identity = IdentityTokenFactory.create(token)
        self.idp = IdentityProviderFactory.create(self.identity)
        self._use_cache = use_cache
        self._groups = None
        self._custom_groups = None
        self._tenants = None
        self._cache = cache_client
        self._database_client = database_client
    
    @property
    def groups(self) -> list[IdentityGroupResponse]:
        """Get user groups with Redis caching (TTL: 60s)."""
        # in-memory cache
        if self._groups is not None:
            return self._groups
        
        self._groups = []
        user_id = self.identity.get_id()
        cache_key = f"identity:groups:user:{user_id}"
        
        # Check Redis cache
        if self._use_cache and self._cache:
            try:
                cached_data = self._cache.client.get(cache_key)
                if cached_data is not None:
                    self._groups = [IdentityGroupResponse(**item) for item in cached_data]
                    logger.debug(f"Returning cached groups for user {user_id}")
                    return self._groups
            except Exception as e:
                logger.warning(f"Failed to get cached groups: {e}")

        # fetch from identity provider
        query = APIFilterQuery(top=999)
        self._groups = self.idp.get_current_user_security_groups(query=query)
        logger.debug(f"Fetched {len(self._groups)} groups from identity provider")

        # cache the groups with 60s TTL
        if self._cache:
            try:
                groups_data = [g.model_dump() for g in self._groups]
                self._cache.client.set(cache_key, groups_data, ttl=60)
                logger.debug(f"Cached groups for user {user_id} (TTL: 60s)")
            except Exception as e:
                logger.warning(f"Failed to cache groups: {e}")

        return self._groups

    @property
    def custom_groups(self) -> list[IdentityGroupResponse]:
        """
        Get all custom groups the user is a member of.
        Returns groups where user_id is in member_ids.
        """
        # in-memory cache
        if self._custom_groups is not None:
            return self._custom_groups
        
        self._custom_groups = []
        
        if not self._database_client:
            return self._custom_groups
        
        user_id = self.identity.get_id()
        
        # Query custom groups where user is a member
        groups = self._database_client.custom_groups.get_list(
            filters={"member_ids": user_id},
            limit=1000
        )
        
        # Convert to IdentityGroupResponse format
        self._custom_groups = [
            IdentityGroupResponse(
                id=g.id,
                display_name=g.name
            )
            for g in groups
        ]
        
        logger.debug(f"Fetched {len(self._custom_groups)} custom groups from database")
        
        return self._custom_groups

    @property
    def tenants(self) -> list[TenantResponse]:
        """
        Get all tenants the user has access to.
        Returns tenants where user has any permission.
        """
        # in-memory cache
        if self._tenants is not None:
            return self._tenants
        
        self._tenants = []
        
        if not self._database_client:
            return self._tenants
        
        user_id = self.identity.get_id()
        cache_key = f"identity:tenants:user:{user_id}"
        
        # Check Redis cache / TODO: in tenant handler!!!
        if self._use_cache and self._cache:
            try:
                cached_data = self._cache.client.get(cache_key)
                if cached_data is not None:
                    self._tenants = [TenantResponse(**item) for item in cached_data]
                    logger.debug(f"Returning cached tenants for user {user_id}")
                    return self._tenants
            except Exception as e:
                logger.warning(f"Failed to get cached tenants: {e}")
        
        # Build assigned_to list
        assigned_to_list = [AssignedTo(type="user", id=user_id)]
        
        # Add identity groups
        for group in self.groups:
            assigned_to_list.append(AssignedTo(type="identity_group", id=group.id))
        
        # Add custom groups
        for group in self.custom_groups:
            assigned_to_list.append(AssignedTo(type="custom_group", id=group.id))
        
        # Get all distinct tenant_ids from permissions where user has access to "tenants" resources
        tenant_ids = set()
        
        # Build $or query for MongoDB (nested objects don't work with $in)
        or_conditions = []
        for at in assigned_to_list:
            or_conditions.append({
                "assigned_to.type": at.type,
                "assigned_to.id": at.id
            })
        
        # Query permissions for tenants resources
        permissions = self._database_client.permissions.get_list(
            filters={
                "resource_type": "tenants",
                "$or": or_conditions
            },
            limit=1000
        )
        
        # Extract resource_ids (these are the tenant IDs user has access to)
        for perm in permissions:
            tenant_ids.add(perm.resource_id)
        
        # Fetch actual tenant objects
        if tenant_ids:
            tenants = self._database_client.tenants.get_list(
                filters={"id": {"$in": list(tenant_ids)}},
                limit=len(tenant_ids)
            )
            
            # Convert to TenantResponse
            self._tenants = [
                TenantHandler._model_to_response(t)
                for t in tenants
            ]
        
        logger.debug(f"Fetched {len(self._tenants)} tenants from database")
        
        # Cache the tenants / TODO: in tenant handler!!!
        if self._cache:
            try:
                tenants_data = [t.model_dump() for t in self._tenants]
                self._cache._client._cache.set(cache_key, tenants_data)
                logger.debug(f"Cached tenants for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to cache tenants: {e}")
        
        return self._tenants

    def get_me(self) -> IdentityUserResponse:
        # Convert TenantResponse objects to dicts
        tenants_dict = [t.model_dump() for t in self.tenants]
        
        return IdentityUserResponse(
            id=self.identity.get_id(),
            identity_provider=self.identity.get_identity_provider(),
            identity_tenant_id=self.identity.get_identity_tenant_id(),
            display_name=self.identity.get_display_name(),
            mail=self.identity.get_mail(),
            firstname=self.identity.get_firstname(),
            lastname=self.identity.get_lastname(),
            tenants=tenants_dict,
            groups=self.groups,
            custom_groups=self.custom_groups
        )
