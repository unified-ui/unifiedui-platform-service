from functools import wraps
from typing import Callable, Any

from fastapi import Request, HTTPException, status
from sqlalchemy import select

from aihub.core.identity.users import ContextIdentityUser
from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.config import DatabaseConfig
from aihub.core.database.models import (
    ApplicationPermission,
    CredentialPermission,
    AutonomousAgentPermission,
    CustomGroupPermission,
    ConversationPermission
)


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
        
        # Get database and cache clients for user
        from aihub.docdatabase.dependencies import get_db_client
        from aihub.caching.dependencies import get_cache_client
        db_client = get_db_client()
        cache_client = get_cache_client()
        
        # Create User object
        try:
            user = ContextIdentityUser(
                token=token,
                database_client=db_client,
                cache_client=cache_client,
                use_cache=use_cache
            )
            if not user.identity.get_id():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: unable to retrieve user identity id.",
                    headers={"WWW-Authenticate": "Bearer"}
                )
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
        
        # Check tenant access if tenant_id is in path parameters
        tenant_id = request.path_params.get("tenant_id")
        if tenant_id:
            user_tenants = user.tenants
            if not any(t["tenant"]["id"] == tenant_id for t in user_tenants):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: User does not have access to tenant {tenant_id}"
                )
        
        return await func(*args, **kwargs)

    return wrapper


def check_permissions(
    entity: str = "tenant",
    required_permissions: list[str] | None = None
) -> Callable:
    """
    Decorator factory to check if the authenticated user has the required permissions.
    
    Args:
        entity: The entity type to check permissions for 
               Options: "tenant", "application", "credential", "autonomous_agent", "custom_group", "conversation"
        required_permissions: List of required permission strings
                            - For tenant: ["GLOBAL_ADMIN", "READER", "CUSTOM_GROUPS_ADMIN", etc.]
                            - For resources: ["READ", "WRITE", "ADMIN"]
                            If None or empty, no permission check is performed
    
    Raises:
        HTTPException: 401 if user not authenticated, 403 if permissions not met
    
    Example:
        @check_permissions(entity="tenant", required_permissions=["GLOBAL_ADMIN"])
        async def update_tenant(...):
            ...
        
        @check_permissions(entity="application", required_permissions=["WRITE", "ADMIN"])
        async def update_application(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
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
            
            user: ContextIdentityUser = request.state.user
            
            # If no permissions required, allow access
            if not required_permissions:
                return await func(*args, **kwargs)
            
            # Check permissions based on entity type
            if entity == "tenant":
                tenant_id = request.path_params.get("tenant_id")
                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="tenant_id not found in path parameters"
                    )
                
                # Get user's tenants and find the matching tenant
                user_tenants = user.tenants
                matching_tenant = next(
                    (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
                    None
                )
                
                if not matching_tenant:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: User does not have access to tenant {tenant_id}"
                    )
                
                # Check if user has any of the required permissions
                user_permissions = [p["permission"] for p in matching_tenant["permissions"]]
                has_permission = any(perm in user_permissions for perm in required_permissions)
                
                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: User does not have required permissions. Required: {required_permissions}, Has: {user_permissions}"
                    )
            
            else:
                # Handle resource entities (application, credential, autonomous_agent, custom_group, conversation)
                # Map entity type to permission model and ID parameter name
                entity_config = {
                    "application": (ApplicationPermission, "application_id"),
                    "credential": (CredentialPermission, "credential_id"),
                    "autonomous_agent": (AutonomousAgentPermission, "autonomous_agent_id"),
                    "custom_group": (CustomGroupPermission, "custom_group_id"),
                    "conversation": (ConversationPermission, "conversation_id")
                }
                
                if entity not in entity_config:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Unsupported entity type: {entity}"
                    )
                
                permission_model, entity_id_param = entity_config[entity]
                
                # Get entity_id from path parameters
                entity_id = request.path_params.get(entity_id_param)
                if not entity_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{entity_id_param} not found in path parameters"
                    )
                
                # Get tenant_id from path parameters (all resources are tenant-scoped)
                tenant_id = request.path_params.get("tenant_id")
                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="tenant_id not found in path parameters"
                    )
                
                # Get user's principal IDs
                user_id = user.identity.get_id()
                identity_group_ids = [group.id for group in user.groups]
                custom_group_ids = [group.id for group in user.custom_groups]
                all_principal_ids = [user_id] + identity_group_ids + custom_group_ids
                
                # Query permissions for this entity
                db_config = DatabaseConfig.from_env()
                db_client = SQLAlchemyClient(config=db_config)
                
                with db_client.get_session() as session:
                    query = (
                        select(permission_model)
                        .where(
                            getattr(permission_model, entity_id_param) == entity_id,
                            permission_model.tenant_id == tenant_id,
                            permission_model.principal_id.in_(all_principal_ids),
                            permission_model.action.in_(required_permissions)
                        )
                    )
                    
                    result = session.execute(query).scalars().first()
                    
                    if not result:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied: User does not have required permissions on {entity}. Required: {required_permissions}"
                        )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
