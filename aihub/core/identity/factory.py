import jwt
import time

from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from aihub.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from aihub.core.identity.enums import IdenityProviderEnum
from aihub.core.identity.extra_id.provider import ExtraIDIdentityProvider
from aihub.core.identity.extra_id.token import ExtraIDIdentityTokenSerializer


class IdentityTokenFactory:

    @staticmethod
    def create(token: str) -> BaseIdentityToken:
        try:
            deserialized_token: dict = jwt.decode(
                token, 
                options={"verify_signature": False}
            )
        except InvalidTokenError as e:
            raise ValueError(f"Invalid JWT token: {str(e)}")
        
        # Check token expiration
        exp = deserialized_token.get("exp")
        if exp:
            current_time = int(time.time())
            if current_time >= exp:
                raise ValueError("Token has expired")

        iss: str = deserialized_token.get("iss")
        if iss.startswith("https://sts.windows.net/"):
            return ExtraIDIdentityTokenSerializer(token, deserialized_token)
        
        raise ValueError(f"Unsupported token issuer: {iss}")


class IdentityProviderFactory:

    @staticmethod
    def create(identity_token: BaseIdentityToken) -> BaseIdentityProvider:
        match identity_token.get_identity_provider():
            case IdenityProviderEnum.EXTRA_ID.value:
                return ExtraIDIdentityProvider(identity_token=identity_token)
        
        raise ValueError(f"Unsupported identity provider for: {identity_token.get_identity_provider()}")