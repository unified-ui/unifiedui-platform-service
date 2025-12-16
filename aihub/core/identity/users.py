from aihub.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from aihub.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from aihub.utils.api_query import APIFilterQuery


class IdentityUser:
    def __init__(self, token: str, use_cache: bool = True):
        self.identity = IdentityTokenFactory.create(token)
        self.idp = IdentityProviderFactory.create(self.identity)
        self._use_cache = use_cache
        self._groups = None
        self._custom_groups = None
        self._cache_client = None
        self._database_client = None
    
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

    def get_me(self) -> IdentityUserResponse:
        return IdentityUserResponse(
            id=self.identity.get_id(),
            identity_provider=self.identity.get_identity_provider(),
            identity_tenant_id=self.identity.get_identity_tenant_id(),
            display_name=self.identity.get_display_name(),
            mail=self.identity.get_mail(),
            firstname=self.identity.get_firstname(),
            lastname=self.identity.get_lastname(),
            tenants=[],
            groups=self.groups,
            custom_groups=self.custom_groups
        )
