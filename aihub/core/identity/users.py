from typing import TYPE_CHECKING

from aihub.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from aihub.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from aihub.schema.responses.tenants import TenantResponse
from aihub.utils.api_query import APIFilterQuery

if TYPE_CHECKING:
    from aihub.database.client import DatabaseClient


class IdentityUser:
    def __init__(self, token: str, database_client: "DatabaseClient" = None, use_cache: bool = True):
        self.identity = IdentityTokenFactory.create(token)
        self.idp = IdentityProviderFactory.create(self.identity)
        self._use_cache = use_cache
        self._groups = None
        self._custom_groups = None
        self._tenants = None
        self._cache_client = None
        self._database_client = database_client
    
    @property
    def groups(self) -> list[IdentityGroupResponse]:
        # in-memory cache
        if self._groups is not None:
            return self._groups
        
        self._groups = []
        if self._use_cache and self._cache_client:
            # redis cache
            cache_groups = self._cache_client.get_user_groups(self.identity.get_id())
            if cache_groups is not None:
                self._groups = cache_groups
                return self._groups

        # fetch from identity provider
        query = APIFilterQuery(top=999)
        self._groups = self.idp.get_current_user_security_groups(query=query)
        # self._identity_provider_client.get_user_groups(self.identity.get_id())

        # cache the groups
        if self._cache_client:
            self._cache_client.set_user_groups(self.identity.get_id(), self._groups)

        return self._groups

    @property
    def custom_groups(self) -> list[IdentityGroupResponse]:
        return []
        # in-memory cache
        if self._custom_groups is not None:
            return self._custom_groups
        
        self._custom_groups = []
        if self._use_cache and self._cache_client:
            # redis cache
            cache_custom_groups = self._cache_client.get_user_custom_groups(self.identity.get_id())
            if cache_custom_groups is not None:
                self._custom_groups = cache_custom_groups
                return self._custom_groups

        # database
        self._custom_groups = self._database_client.get_user_custom_groups(self.identity.get_id())

        # cache the custom groups
        self._cache_client.set_user_custom_groups(self.identity.get_id(), self._custom_groups)

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
        
        # Build assigned_to list
        from aihub.core.database.models.permissions import AssignedTo
        
        assigned_to_list = [AssignedTo(type="user", id=self.identity.get_id())]
        
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
            from aihub.core.handlers.tenants import TenantHandler
            handler = TenantHandler(self._database_client)
            self._tenants = [handler._model_to_response(t) for t in tenants]
        
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
