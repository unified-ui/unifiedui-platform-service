from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import select, or_, and_

from unifiedui.handlers.tenants import TenantHandler
from unifiedui.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.schema.responses.tenants import TenantResponse
from unifiedui.utils.api_query import APIFilterQuery
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.caching.client import CacheClient
from unifiedui.handlers.dependencies import get_db_client
from unifiedui.core.database.models import Principal, CustomGroupMember
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
        self._identity_groups = None
        self._idp_group_ids = None
        self._tenants = None
        self._cache = cache_client
        self._database_client = database_client

    def _get_idp_group_ids(self) -> List[str]:
        """Get identity group IDs from the identity provider."""
        if self._idp_group_ids is not None:
            return self._idp_group_ids
        
        user_id = self.identity.get_id()
        cache_key = f"identity:idp_group_ids:user:{user_id}"
        
        # Check Redis cache
        if self._use_cache and self._cache:
            try:
                cached_data = self._cache.client.get(cache_key)
                if cached_data is not None:
                    self._idp_group_ids = cached_data
                    logger.debug(f"Returning cached IDP group IDs for user {user_id}")
                    return self._idp_group_ids
            except Exception as e:
                logger.warning(f"Failed to get cached IDP group IDs: {e}")
        
        # Fetch from identity provider
        query = APIFilterQuery(top=999)
        idp_groups = self.idp.get_current_user_security_groups(query=query)
        self._idp_group_ids = [g.id for g in idp_groups]
        logger.debug(f"Fetched {len(self._idp_group_ids)} IDP group IDs from identity provider")
        
        # Cache the group IDs with 60s TTL
        if self._cache:
            try:
                self._cache.client.set(cache_key, self._idp_group_ids, ttl=60)
                logger.debug(f"Cached IDP group IDs for user {user_id} (TTL: 60s)")
            except Exception as e:
                logger.warning(f"Failed to cache IDP group IDs: {e}")
        
        return self._idp_group_ids
    
    @property
    def groups(self) -> List[IdentityGroupResponse]:
        """
        Get user groups (IDENTITY_GROUP and CUSTOM_GROUP) from the principals table.
        
        For IDENTITY_GROUP: Fetches groups where the principal_id matches the user's IDP group IDs.
        For CUSTOM_GROUP: Fetches groups where the user is a member via CustomGroupMember table.
        """
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
        
        if not self._database_client:
            logger.warning("No database client available, returning empty groups list")
            return self._groups
        
        # Get IDP group IDs from identity provider
        idp_group_ids = self._get_idp_group_ids()
        
        with self._database_client.get_session() as session:
            # 1. Fetch IDENTITY_GROUPs where user is a member (from IDP)
            if idp_group_ids:
                identity_group_query = (
                    select(Principal)
                    .where(
                        Principal.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value,
                        Principal.principal_id.in_(idp_group_ids)
                    )
                )
                identity_groups = session.execute(identity_group_query).scalars().all()
                
                for p in identity_groups:
                    self._groups.append(
                        IdentityGroupResponse(
                            id=p.principal_id,
                            display_name=p.display_name,
                            principal_name=p.principal_name,
                            principal_type=p.principal_type
                        )
                    )
            
            # 2. Fetch CUSTOM_GROUPs where user is a member via CustomGroupMember
            custom_group_query = (
                select(Principal)
                .join(
                    CustomGroupMember,
                    and_(
                        CustomGroupMember.tenant_id == Principal.tenant_id,
                        CustomGroupMember.custom_group_id == Principal.principal_id
                    )
                )
                .where(
                    Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
                    CustomGroupMember.principal_id == user_id
                )
            )
            custom_groups = session.execute(custom_group_query).scalars().all()
            
            for p in custom_groups:
                self._groups.append(
                    IdentityGroupResponse(
                        id=p.principal_id,
                        display_name=p.display_name,
                        principal_name=p.principal_name,
                        principal_type=p.principal_type
                    )
                )
        
        logger.debug(f"Fetched {len(self._groups)} groups from principals table (identity: {len(idp_group_ids) if idp_group_ids else 0}, custom: {len(custom_groups) if 'custom_groups' in dir() else 0})")
        
        # Cache the groups with 300s TTL
        if self._cache:
            try:
                groups_data = [g.model_dump() for g in self._groups]
                self._cache.client.set(cache_key, groups_data, ttl=300)
                logger.debug(f"Cached groups for user {user_id} (TTL: 300s)")
            except Exception as e:
                logger.warning(f"Failed to cache groups: {e}")
        
        return self._groups

    @property
    def custom_groups(self) -> List[IdentityGroupResponse]:
        """
        Get custom groups the user is a member of (CUSTOM_GROUP only).
        This is a filtered view of the groups property.
        """
        if self._custom_groups is not None:
            return self._custom_groups
        self._custom_groups = [g for g in self.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]
        return self._custom_groups

    @property
    def identity_groups(self) -> List[IdentityGroupResponse]:
        """
        Get identity groups the user is a member of (IDENTITY_GROUP only).
        This is a filtered view of the groups property.
        """
        if self._identity_groups is not None:
            return self._identity_groups
        self._identity_groups = [g for g in self.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value]
        return self._identity_groups

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
        # Get IDP group IDs from identity provider (not from groups property to avoid circular dependency)
        idp_group_ids = self._get_idp_group_ids()
        # Get custom group IDs from groups property (filter by CUSTOM_GROUP type)
        custom_group_ids = [g.id for g in self.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]
        
        # Use TenantHandler to get tenants with roles (caching is handled in the handler)
        db_client = self._database_client
        if not db_client:
            from unifiedui.handlers.dependencies import get_db_client
            db_client = get_db_client()
        handler = TenantHandler(db_client, self._cache)
        
        self._tenants = handler.get_user_tenants_with_permissions(
            user_id=user_id,
            identity_group_ids=idp_group_ids,
            custom_group_ids=custom_group_ids,
            use_cache=self._use_cache
        )
        
        logger.debug(f"Fetched {len(self._tenants)} tenants with permissions for user {user_id}")
        
        return self._tenants

    def get_me(self) -> IdentityUserResponse:
        """Get the current user's identity information."""
        # Tenants are already dicts with 'tenant' and 'permissions' keys
        tenants_with_permissions = self.tenants
        
        # Get principal_name from identity provider
        principal_name = self.idp.get_principal_name(
            self.identity.get_id(),
            PrincipalTypeEnum.IDENTITY_USER.value
        )
        
        return IdentityUserResponse(
            id=self.identity.get_id(),
            identity_provider=self.identity.get_identity_provider(),
            identity_tenant_id=self.identity.get_identity_tenant_id(),
            display_name=self.identity.get_display_name(),
            principal_name=principal_name,
            mail=self.identity.get_mail(),
            firstname=self.identity.get_firstname(),
            lastname=self.identity.get_lastname(),
            tenants=tenants_with_permissions,
            groups=self.groups
        )
