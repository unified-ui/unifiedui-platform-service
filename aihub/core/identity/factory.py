import jwt

from jwt.exceptions import InvalidTokenError

from aihub.core.identity.base import BaseIdentityTokenSerializer
from aihub.core.identity.extra_id.token import ExtraIDIdentityTokenSerializer


class IdentityTokenFactory:

    @staticmethod
    def create(token: str) -> BaseIdentityTokenSerializer:
        try:
            deserialized_token: dict = jwt.decode(
                token, 
                options={"verify_signature": False}
            )
        except InvalidTokenError as e:
            raise ValueError(f"Invalid JWT token: {str(e)}")

        iss: str = deserialized_token.get("iss")
        if iss.startswith("https://sts.windows.net/"):
            return ExtraIDIdentityTokenSerializer(token, deserialized_token)
        
        raise ValueError(f"Unsupported token issuer: {iss}")
