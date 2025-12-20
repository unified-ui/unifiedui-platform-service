import jwt
import time

from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from aihub.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from aihub.core.identity.enums import IdenityProviderEnum
from aihub.core.identity.extra_id.provider import ExtraIDIdentityProvider
from aihub.core.identity.extra_id.token import ExtraIDIdentityTokenSerializer
from aihub.core.identity.mock.token import MockIdentityToken
from aihub.core.identity.mock.provider import MockIdentityProvider


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

        iss: str = deserialized_token.get("iss", "")
        
        # Support for mock identity provider (testing)
        if iss.startswith("https://mock.identity.provider/"):
            # Create instance without calling __init__ to avoid recreating the token
            mock_token = MockIdentityToken.__new__(MockIdentityToken)
            # Initialize base class attributes
            BaseIdentityToken.__init__(mock_token, token, deserialized_token)
            # Set identity provider
            mock_token._identity_provider = IdenityProviderEnum.MOCK.value
            return mock_token
        
        if iss.startswith("https://sts.windows.net/"):
            return ExtraIDIdentityTokenSerializer(token, deserialized_token)
        
        raise ValueError(f"Unsupported token issuer: {iss}")


class IdentityProviderFactory:

    @staticmethod
    def create(identity_token: BaseIdentityToken) -> BaseIdentityProvider:
        match identity_token.get_identity_provider():
            case IdenityProviderEnum.MOCK.value:
                return MockIdentityProvider(identity_token=identity_token)
            case IdenityProviderEnum.EXTRA_ID.value:
                return ExtraIDIdentityProvider(identity_token=identity_token)
        
        raise ValueError(f"Unsupported identity provider for: {identity_token.get_identity_provider()}")