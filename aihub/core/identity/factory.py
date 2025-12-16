from core.identity.base import BaseIdentityTokenSerializer
from core.identity.extra_id.token import ExtraIDIdentityTokenSerializer


class IdentityTokenFactory:

    @staticmethod
    def create(token: str) -> BaseIdentityTokenSerializer:
        desierialized_token = {
            "iss": "https://microsoft.com/",
            "id": "user_id_example",
            "tid": "tenant_id_example",
            "display_name": "John Doe",
            "firstname": "John",
            "lastname": "Doe"
        }

        iss = desierialized_token.get("iss")
        match iss:
            case "https://microsoft.com/":
                return ExtraIDIdentityTokenSerializer(token, desierialized_token)
            case _:
                raise ValueError(f"Unsupported token issuer: {iss}")
