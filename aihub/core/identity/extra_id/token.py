from aihub.core.identity.base import BaseIdentityToken, IdenityProviderEnum


class ExtraIDIdentityTokenSerializer(BaseIdentityToken):

    def __init__(self, token: str, deserialized_token: dict):
        self._identity_provider = IdenityProviderEnum.EXTRA_ID.value
        super().__init__(token, deserialized_token)

    def get_token(self) -> str:
        return self.token

    def get_deserialized_token(self) -> dict:
        return self.deserialized_token

    def get_id(self) -> str:
        return self.deserialized_token.get("oid")

    def get_tenant_id(self) -> str:
        return self.deserialized_token.get("tid", "")

    def get_display_name(self) -> str:
        return self.deserialized_token.get("name", "")

    def get_firstname(self) -> str:
        given_name = self.deserialized_token.get("given_name", "")
        if given_name:
            return given_name
        
        name = self.deserialized_token.get("name", "")
        if name and " " in name:
            return name.split(" ", 1)[0]
        
        return ""

    def get_lastname(self) -> str:
        family_name = self.deserialized_token.get("family_name", "")
        if family_name:
            return family_name
        
        name = self.deserialized_token.get("name", "")
        if name and " " in name:
            return name.split(" ", 1)[1]
        
        return ""

    def get_mail(self):
        return self.deserialized_token.get("mail", "")

    def get_identity_provider(self) -> str:
        return self._identity_provider
