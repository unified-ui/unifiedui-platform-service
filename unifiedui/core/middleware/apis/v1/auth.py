from functools import wraps
from typing import Callable, Any, Union

from fastapi import Request, HTTPException, status
from sqlalchemy import select

from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.handlers.dependencies import get_db_client
from unifiedui.core.database.enums import TenantRolesEnum, PermissionActionEnum, UserPermissionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import (
    ApplicationMember,
    CredentialMember,
    AutonomousAgentMember,
    CustomGroupMember,
    ConversationMember,
    DevelopmentPlatformMember,
    ChatWidgetMember,
    Tag
)
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.caching.dependencies import get_cache_client


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
    required_permissions: Union[list[Union[TenantRolesEnum, PermissionActionEnum, UserPermissionEnum]], None] = None
) -> Callable:
    """
    Decorator factory to check if the authenticated user has the required permissions.
    
    Args:
        entity: The entity type to check permissions for 
               Options: "tenant", "application", "credential", "autonomous_agent", "custom_group", "conversation", "tag"
        required_permissions: List of required permission enums
                            - For tenant: [TenantPermissionEnum.GLOBAL_ADMIN, TenantPermissionEnum.READER, etc.]
                            - For resources: [PermissionActionEnum.READ, PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN]
                            - Special: [UserPermissions.IS_CREATOR] - allows access if user is the creator
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
        
        @check_permissions(entity="tag", required_permissions=[TenantRolesEnum.GLOBAL_ADMIN, UserPermissions.IS_CREATOR])
        async def delete_tag(...):
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
                # matching_tenant["roles"] is already a list of permission strings
                user_roles = matching_tenant["roles"]
                required_perms_str = [perm.value if hasattr(perm, 'value') else perm for perm in required_permissions]
                has_permission = any(perm in user_roles for perm in required_perms_str)
                
                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: User does not have required permissions. Required: {required_perms_str}, Has: {user_roles}"
                    )
            
            elif entity == "tag":
                # Special handling for tags - check GLOBAL_ADMIN first, then IS_CREATOR
                tenant_id = request.path_params.get("tenant_id")
                tag_id = request.path_params.get("tag_id")
                
                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="tenant_id not found in path parameters"
                    )
                if not tag_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="tag_id not found in path parameters"
                    )
                
                # Check tenant-level permissions first (GLOBAL_ADMIN)
                user_tenants = user.tenants
                matching_tenant = next(
                    (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
                    None
                )
                
                if matching_tenant:
                    user_tenant_permissions = matching_tenant["roles"]
                    
                    # Check for TenantRolesEnum permissions (like GLOBAL_ADMIN)
                    tenant_role_perms = [
                        perm for perm in required_permissions 
                        if isinstance(perm, TenantRolesEnum)
                    ]
                    for perm in tenant_role_perms:
                        if perm.value in user_tenant_permissions:
                            return await func(*args, **kwargs)
                
                # Check IS_CREATOR permission
                if UserPermissionEnum.IS_CREATOR in required_permissions:
                    user_id = user.identity.get_id()
                    db_client = get_db_client()
                    
                    with db_client.get_session() as session:
                        tag = session.execute(
                            select(Tag).where(
                                Tag.id == tag_id,
                                Tag.tenant_id == tenant_id
                            )
                        ).scalar_one_or_none()
                        
                        if tag and tag.created_by == user_id:
                            return await func(*args, **kwargs)
                
                # No permission matched
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: User does not have required permissions on this tag (ID: {tag_id})"
                )
            
            elif entity == "user_favorite":
                # Special handling for user favorites - only the user themselves can manage their favorites
                tenant_id = request.path_params.get("tenant_id")
                target_user_id = request.path_params.get("user_id")
                
                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="tenant_id not found in path parameters"
                    )
                if not target_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="user_id not found in path parameters"
                    )
                
                # Check if requesting user is the target user (IS_CREATOR check for favorites)
                if UserPermissionEnum.IS_CREATOR in required_permissions:
                    current_user_id = user.identity.get_id()
                    if current_user_id == target_user_id:
                        return await func(*args, **kwargs)
                
                # No permission matched
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: User can only manage their own favorites"
                )
            
            else:
                # Handle resource entities (application, credential, autonomous_agent, custom_group, conversation)
                # Now role is directly in member table - no need for JOIN
                
                # Map entity type to member model and ID parameter name
                entity_config = {
                    "application": (ApplicationMember, "application_id"),
                    "credential": (CredentialMember, "credential_id"),
                    "autonomous_agent": (AutonomousAgentMember, "autonomous_agent_id"),
                    "custom_group": (CustomGroupMember, "custom_group_id"),
                    "conversation": (ConversationMember, "conversation_id"),
                    "development_platform": (DevelopmentPlatformMember, "development_platform_id"),
                    "chat_widget": (ChatWidgetMember, "chat_widget_id")
                }
                
                if entity not in entity_config:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Unsupported entity type: {entity}"
                    )
                
                member_model, entity_id_param = entity_config[entity]
                
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
                    # matching_tenant["roles"] is already a list of permission strings
                    user_tenant_permissions = matching_tenant["roles"]
                    
                    # GLOBAL_ADMIN grants access to all resources
                    if TenantRolesEnum.GLOBAL_ADMIN.value in user_tenant_permissions:
                        return await func(*args, **kwargs)
                    
                    # Entity-specific admin permissions
                    entity_admin_map = {
                        "application": TenantRolesEnum.APPLICATIONS_ADMIN.value,
                        "credential": TenantRolesEnum.CREDENTIALS_ADMIN.value,
                        "autonomous_agent": TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN.value,
                        "custom_group": TenantRolesEnum.CUSTOM_GROUPS_ADMIN.value,
                        "conversation": TenantRolesEnum.CONVERSATIONS_ADMIN.value,
                        "development_platform": TenantRolesEnum.DEVELOPMENT_PLATFORMS_ADMIN.value,
                        "chat_widget": TenantRolesEnum.CHAT_WIDGETS_ADMIN.value,
                    }
                    
                    entity_admin = entity_admin_map.get(entity)
                    if entity_admin and entity_admin in user_tenant_permissions:
                        return await func(*args, **kwargs)
                
                # Get user's principal IDs (user + all groups from groups property)
                user_id = user.identity.get_id()
                user_groups = user.groups  # Contains both IDENTITY_GROUPs and CUSTOM_GROUPs
                
                # Extract group IDs (groups property now contains both types)
                identity_group_ids = [
                    g.id for g in user_groups 
                    if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
                ]
                custom_group_ids = [
                    g.id for g in user_groups 
                    if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value
                ]
                all_principal_ids = [user_id] + identity_group_ids + custom_group_ids
                
                # Query member with role directly - NO JOIN needed anymore
                db_client = get_db_client()
                required_perms_str = [perm.value if hasattr(perm, 'value') else perm for perm in required_permissions]
                
                # Build role hierarchy: ADMIN >= WRITE >= READ
                # If user requires READ, accept ADMIN, WRITE, or READ
                # If user requires WRITE, accept ADMIN or WRITE
                # If user requires ADMIN, accept only ADMIN
                allowed_roles = set()
                if any(perm in [PermissionActionEnum.READ.value, PermissionActionEnum.READ] for perm in required_permissions):
                    # READ required -> allow ADMIN, WRITE, READ
                    allowed_roles.update([PermissionActionEnum.READ.value, PermissionActionEnum.WRITE.value, PermissionActionEnum.ADMIN.value])
                elif any(perm in [PermissionActionEnum.WRITE.value, PermissionActionEnum.WRITE] for perm in required_permissions):
                    # WRITE required -> allow ADMIN, WRITE
                    allowed_roles.update([PermissionActionEnum.WRITE.value, PermissionActionEnum.ADMIN.value])
                elif any(perm in [PermissionActionEnum.ADMIN.value, PermissionActionEnum.ADMIN] for perm in required_permissions):
                    # ADMIN required -> allow only ADMIN
                    allowed_roles.add(PermissionActionEnum.ADMIN.value)
                
                with db_client.get_session() as session:
                    # Single query: Check member table directly for role
                    query = (
                        select(member_model)
                        .where(
                            getattr(member_model, entity_id_param) == entity_id,
                            member_model.tenant_id == tenant_id,
                            member_model.principal_id.in_(all_principal_ids),
                            member_model.role.in_(list(allowed_roles))
                        )
                    )
                    
                    result = session.execute(query).scalars().first()
                    
                    if not result:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied: User does not have required permissions on this {entity} (ID: {entity_id}). Required one of: {required_perms_str}, Allowed roles: {list(allowed_roles)}"
                        )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
