from functools import wraps
from typing import Callable, Any

from fastapi import Request, HTTPException, status

from aihub.core.identity.user import IdentityUser


def authenticate(func: Callable) -> Callable:
    """
    Decorator to authenticate users via Bearer token from Authorization header.
    Creates a User object and injects it into the decorated function.
    Optionally uses cache based on X-Use-Cache header.
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extract request from args or kwargs
        request: Request | None = kwargs.get("request")
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
            user = IdentityUser(token=token, use_cache=use_cache)
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
        request.state.use_cache = use_cache
        
        return await func(*args, **kwargs)

    return wrapper


def check_permissions(func: Callable) -> Callable:
    """
    Decorator to check if the authenticated user has the required permissions.  
    Raises HTTP 403 if permissions are not met.
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extract request from args or kwargs
        request: Request | None = kwargs.get("request")
        if request is None:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
        
        if request is None or not hasattr(request.state, "user"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user: IdentityUser = request.state.user
        return await func(*args, **kwargs)
    
    return wrapper
