from abc import ABC, abstractmethod
from functools import wraps, func
from typing import Callable, Any

from fastapi import Request, HTTPException, status

class BaseIdentityTokenSerializer(ABC):
    def __init__(self, token: str, deserialized_token: dict):
        self.token = token
        self.deserialized_token = deserialized_token

    @abstractmethod
    def get_id(self) -> str:
        pass

    @abstractmethod
    def get_tenant_id(self) -> str:
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        pass

    @abstractmethod
    def get_firstname(self) -> str:
        pass

    @abstractmethod
    def get_lastname(self) -> str:
        pass


class ExtraIDIdentityTokenSerializer(BaseIdentityTokenSerializer):

    def __init__(self, token):
        super().__init__(token)

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
            case "https://extraid.com/":
                return ExtraIDIdentityTokenSerializer(token, desierialized_token)
            case _:
                raise ValueError(f"Unsupported token issuer: {iss}")


class BaseGroup:
    id: str
    name: str


class User:
    def __init__(self, token: str, use_cache: bool = True):
        self.identity = IdentityTokenFactory.create(token)
        self._use_cache = use_cache
        self.groups = None
        self.custom_groups = None
        self._cache_client = None
        self._database_client = None
        self._identity_provider_client = None
    
    @property
    def groups(self) -> list[BaseGroup]:
        # in-memory cache
        if self.groups is not None:
            return self.groups
        
        self.groups = []
        if self._use_cache and self._cache_client:
            # redis cache
            cache_groups = self._cache_client.get_user_groups(self.identity.get_id())
            if cache_groups is not None:
                self.groups = cache_groups
                return self.groups

        # database
        self.groups = self._database_client.get_user_groups(self.identity.get_id())
        return self.groups

    @property
    def custom_groups(self) -> list[BaseGroup]:
        # in-memory cache
        if self.custom_groups is not None:
            return self.custom_groups
        
        self.custom_groups = []
        if self._use_cache and self._cache_client:
            # redis cache
            cache_custom_groups = self._cache_client.get_user_custom_groups(self.identity.get_id())
            if cache_custom_groups is not None:
                self.custom_groups = cache_custom_groups
                return self.custom_groups

        # database
        self.custom_groups = self._database_client.get_user_custom_groups(self.identity.get_id())
        return self.custom_groups

def authenticate(func: Callable) -> Callable:
    """
    Decorator to authenticate users via Bearer token from Authorization header.
    Creates a User object and injects it into the decorated function.
    Optionally uses cache based on X-Use-Cache header.
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extract request from args or kwargs
        request: Request | None = kwargs.get('request')
        if request is None:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
        
        if request is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request object not found"
            )
        
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Extract Bearer token
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization scheme. Expected 'Bearer'",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is empty",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Extract cache preference from header (default: True)
        use_cache_header = request.headers.get("X-Use-Cache", "true")
        use_cache = use_cache_header.lower() in ("true", "1", "yes")
        
        # Create User object
        try:
            user = User(token=token, use_cache=use_cache)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Authentication error: {str(e)}"
            )
        
        # Attach user to request state (FastAPI best practice)
        request.state.user = user
        
        # Also inject user into function kwargs for convenience
        kwargs['user'] = user
        
        return await func(*args, **kwargs)

    return wrapper
