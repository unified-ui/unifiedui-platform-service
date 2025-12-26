from typing import TYPE_CHECKING, Optional
from sqlalchemy import select

from unifiedui.handlers.tenants import TenantHandler
from unifiedui.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.schema.responses.tenants import TenantResponse
from unifiedui.utils.api_query import APIFilterQuery
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.caching.client import CacheClient
from unifiedui.handlers.dependencies import get_db_client
from unifiedui.core.database.models import Principal
from unifiedui.core.database.enums import PrincipalTypeEnum
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class ContextIdentityUser:
    def __init__(
        self,
        token: str,
        database_client: Optional[SQLAlchemyClient] = None,
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
        Custom groups are stored as principals with type CUSTOM_GROUP.
        
        Note: This returns custom groups where the user is directly a member.
        The membership is tracked through other mechanisms (e.g., a separate membership table
        or through the principals table relationships).
        """
        # in-memory cache
        if self._custom_groups is not None:
            return self._custom_groups
        
        self._custom_groups = []
        
        user_id = self.identity.get_id()
        cache_key = f"identity:custom_groups:user:{user_id}"
        
        # Check Redis cache
        if self._use_cache and self._cache:
            try:
                cached_data = self._cache.client.get(cache_key)
                if cached_data is not None:
                    self._custom_groups = [IdentityGroupResponse(**item) for item in cached_data]
                    logger.debug(f"Returning cached custom groups for user {user_id}")
                    return self._custom_groups
            except Exception as e:
                logger.warning(f"Failed to get cached custom groups: {e}")
        
        # TODO: Custom group membership needs to be implemented
        # For now, return empty list as custom groups are managed differently
        # Custom groups are stored in the principals table with type CUSTOM_GROUP
        # but we need a separate mechanism to track which users belong to which custom groups
        
        logger.debug(f"Custom groups lookup not yet implemented for user {user_id}")
        self._custom_groups = []
        
        logger.debug(f"Fetched {len(self._custom_groups)} custom groups from database")
        
        # Cache the custom groups
        if self._cache:
            try:
                groups_data = [g.model_dump() for g in self._custom_groups]
                self._cache.client.set(cache_key, groups_data, ttl=300)  # Cache for 5 minutes
                logger.debug(f"Cached custom groups for user {user_id} (TTL: 300s)")
            except Exception as e:
                logger.warning(f"Failed to cache custom groups: {e}")
        
        return self._custom_groups

    @property
    def tenants(self) -> list[dict]:
        """
        Get all tenants the user has access to with their roles.
        Returns list of dicts with 'tenant' and 'roles' keys.
        Roles are deduplicated across IDENTITY_USER, IDENTITY_GROUP, and CUSTOM_GROUP.
        """
        # in-memory cache
        if self._tenants is not None:
            return self._tenants
        
        self._tenants = []
        
        if not self._database_client:
            return self._tenants
        
        # Get user ID and group IDs
        user_id = self.identity.get_id()
        identity_group_ids = [group.id for group in self.groups]
        custom_group_ids = [group.id for group in self.custom_groups]
        
        # Use TenantHandler to get tenants with roles (caching is handled in the handler)
        db_client = self._database_client
        if not db_client:
            from unifiedui.handlers.dependencies import get_db_client
            db_client = get_db_client()
        handler = TenantHandler(db_client, self._cache)
        
        self._tenants = handler.get_user_tenants_with_permissions(
            user_id=user_id,
            identity_group_ids=identity_group_ids,
            custom_group_ids=custom_group_ids,
            use_cache=self._use_cache
        )
        
        logger.debug(f"Fetched {len(self._tenants)} tenants with permissions for user {user_id}")
        
        return self._tenants

    def get_me(self) -> IdentityUserResponse:
        # Tenants are already dicts with 'tenant' and 'permissions' keys
        tenants_with_permissions = self.tenants
        
        return IdentityUserResponse(
            id=self.identity.get_id(),
            identity_provider=self.identity.get_identity_provider(),
            identity_tenant_id=self.identity.get_identity_tenant_id(),
            display_name=self.identity.get_display_name(),
            mail=self.identity.get_mail(),
            firstname=self.identity.get_firstname(),
            lastname=self.identity.get_lastname(),
            tenants=tenants_with_permissions,
            groups=self.groups,
            custom_groups=self.custom_groups
        )
