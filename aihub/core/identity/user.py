from aihub.core.identity.factory import IdentityTokenFactory
from aihub.core.identity.base import BaseGroup


class IdentityUser:
    def __init__(self, token: str, use_cache: bool = True):
        self.identity = IdentityTokenFactory.create(token)
        self._use_cache = use_cache
        self._groups = None
        self._custom_groups = None
        self._cache_client = None
        self._database_client = None
        self._identity_provider_client = None
    
    @property
    def groups(self) -> list[BaseGroup]:
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
        self._groups = self._identity_provider_client.get_user_groups(self.identity.get_id())

        # cache the groups
        self._cache_client.set_user_groups(self.identity.get_id(), self._groups)

        return self._groups

    @property
    def custom_groups(self) -> list[BaseGroup]:
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

    def to_dict(self) -> dict:
        return {
            "id": self.identity.get_id(),
            "tenant_id": self.identity.get_tenant_id(),
            "display_name": self.identity.get_display_name(),
            "firstname": self.identity.get_firstname(),
            "lastname": self.identity.get_lastname()
            # "groups": [group.name for group in self.groups],
            # "custom_groups": [group.name for group in self.custom_groups],
        }
