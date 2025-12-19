from functools import wraps
from typing import Callable, Any, Union

from fastapi import Request, HTTPException, status
from sqlalchemy import select

from aihub.core.identity.users import ContextIdentityUser
from aihub.handlers.dependencies import get_db_client
from aihub.core.database.enums import TenantPermissionEnum, PermissionActionEnum
from aihub.core.database.models import (
    ApplicationMember,
    ApplicationMemberPermission,
    CredentialMember,
    CredentialMemberPermission,
    AutonomousAgentMember,
    AutonomousAgentMemberPermission,
    CustomGroupMember,
    CustomGroupMemberPermission,
    ConversationMember,
    ConversationMemberPermission
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
    required_permissions: Union[list[Union[TenantPermissionEnum, PermissionActionEnum]], None] = None
) -> Callable:
    """
    Decorator factory to check if the authenticated user has the required permissions.
    
    Args:
        entity: The entity type to check permissions for 
               Options: "tenant", "application", "credential", "autonomous_agent", "custom_group", "conversation"
        required_permissions: List of required permission enums
                            - For tenant: [TenantPermissionEnum.GLOBAL_ADMIN, TenantPermissionEnum.READER, etc.]
                            - For resources: [PermissionActionEnum.READ, PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN]
                            If None or empty, no permission check is performed
    
    Raises:
        HTTPException: 401 if user not authenticated, 403 if permissions not met
    
    Example:
        @check_permissions(entity="tenant", required_permissions=[TenantPermissionEnum.GLOBAL_ADMIN])
        async def update_tenant(...):
            ...
        
        @check_permissions(entity="application", required_permissions=[PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN])
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
                # matching_tenant["permissions"] is already a list of permission strings
                user_permissions = matching_tenant["permissions"]
                required_perms_str = [perm.value if hasattr(perm, 'value') else perm for perm in required_permissions]
                has_permission = any(perm in user_permissions for perm in required_perms_str)
                
                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: User does not have required permissions. Required: {required_perms_str}, Has: {user_permissions}"
                    )
            
            else:
                # Handle resource entities (application, credential, autonomous_agent, custom_group, conversation)
                # All entities now use member + member_permissions structure
                
                # Map entity type to member model and ID parameter name
                entity_config = {
                    "application": (ApplicationMember, ApplicationMemberPermission, "application_id"),
                    "credential": (CredentialMember, CredentialMemberPermission, "credential_id"),
                    "autonomous_agent": (AutonomousAgentMember, AutonomousAgentMemberPermission, "autonomous_agent_id"),
                    "custom_group": (CustomGroupMember, CustomGroupMemberPermission, "custom_group_id"),
                    "conversation": (ConversationMember, ConversationMemberPermission, "conversation_id")
                }
                
                if entity not in entity_config:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Unsupported entity type: {entity}"
                    )
                
                member_model, permission_model, entity_id_param = entity_config[entity]
                
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
                
                # Check tenant-level permissions first
                user_tenants = user.tenants
                matching_tenant = next(
                    (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
                    None
                )
                
                if matching_tenant:
                    # matching_tenant["permissions"] is already a list of permission strings
                    user_tenant_permissions = matching_tenant["permissions"]
                    
                    # GLOBAL_ADMIN grants access to all resources
                    if TenantPermissionEnum.GLOBAL_ADMIN.value in user_tenant_permissions:
                        return await func(*args, **kwargs)
                    
                    # Entity-specific admin permissions
                    entity_admin_map = {
                        "application": TenantPermissionEnum.APPLICATIONS_ADMIN.value,
                        "credential": TenantPermissionEnum.CREDENTIALS_ADMIN.value,
                        "autonomous_agent": TenantPermissionEnum.AUTONOMOUS_AGENTS_ADMIN.value,
                        "custom_group": TenantPermissionEnum.CUSTOM_GROUPS_ADMIN.value,
                        "conversation": TenantPermissionEnum.CONVERSATIONS_ADMIN.value,
                    }
                    
                    entity_admin = entity_admin_map.get(entity)
                    if entity_admin and entity_admin in user_tenant_permissions:
                        return await func(*args, **kwargs)
                
                # Get user's principal IDs (cache property access)
                user_id = user.identity.get_id()
                user_groups = user.groups  # Cache property
                user_custom_groups = user.custom_groups  # Cache property
                identity_group_ids = [group.id for group in user_groups]
                custom_group_ids = [group.id for group in user_custom_groups]
                all_principal_ids = [user_id] + identity_group_ids + custom_group_ids
                
                # Query member permissions for this entity - ONE query with JOIN
                db_client = get_db_client()
                required_perms_str = [perm.value if hasattr(perm, 'value') else perm for perm in required_permissions]
                
                with db_client.get_session() as session:
                    # Single query: JOIN member with permissions and check everything at once
                    query = (
                        select(permission_model)
                        .join(member_model, getattr(permission_model, f"{entity}_member_id") == member_model.id)
                        .where(
                            getattr(member_model, entity_id_param) == entity_id,
                            member_model.tenant_id == tenant_id,
                            member_model.principal_id.in_(all_principal_ids),
                            permission_model.permission.in_(required_perms_str)
                        )
                    )
                    
                    result = session.execute(query).scalars().first()
                    
                    if not result:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied: User does not have required permissions on this {entity} (ID: {entity_id}). Required: {required_perms_str}"
                        )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
