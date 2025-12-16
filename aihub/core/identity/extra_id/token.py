from core.identity.base import BaseIdentityTokenSerializer


class ExtraIDIdentityTokenSerializer(BaseIdentityTokenSerializer):

    def __init__(self, token):
        super().__init__(token)

    def get_token(self) -> str:
        return self.token

    def get_deserialized_token(self) -> dict:
        return self.deserialized_token

    def get_id(self) -> str:
        # Placeholder implementation
        return self.deserialized_token.get("id")

    def get_tenant_id(self) -> str:
        # Placeholder implementation
        return self.deserialized_token.get("tid")

    def get_display_name(self) -> str:
        # Placeholder implementation
        return self.deserialized_token.get("display_name")
    def get_firstname(self) -> str:
        # Placeholder implementation
        return self.deserialized_token.get("firstname")

    def get_lastname(self) -> str:
        # Placeholder implementation
        return self.deserialized_token.get("lastname")
