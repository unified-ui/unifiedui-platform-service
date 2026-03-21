from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from unifiedui.caching.dependencies import get_cache_client
from unifiedui.core.config import settings
from unifiedui.core.database.enums import (
    OrganizationRoleEnum,
    PermissionActionEnum,
    PrincipalTypeEnum,
    TenantRolesEnum,
    UserPermissionEnum,
)
from unifiedui.core.database.models import (
    AutonomousAgentMember,
    ChatAgentMember,
    ChatWidgetMember,
    ConversationMember,
    CredentialMember,
    CustomGroupMember,
    ExternalAppMember,
    Tag,
    ToolMember,
)
from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.logger import get_logger

logger = get_logger(__name__)


def _validate_service_key(request: Request, required_service_auth_config: str) -> bool:
    """
    Validate X-Service-Key header against the app vault or settings fallback.

    Args:
        request: FastAPI request object
        required_service_auth_config: Config name mapping (e.g., "X_AGENT_SERVICE_KEY")

    Returns:
        True if service key is valid

    Raises:
        HTTPException: If service key is missing, invalid, or not configured
    """

    service_header = request.headers.get("X-Service-Key")

    if not service_header:
        logger.warning("X-Service-Key header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Service-Key header missing for service authentication"
        )

    expected = _resolve_service_credential(required_service_auth_config)

    if not expected:
        logger.error("Service auth config %s not configured", required_service_auth_config)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service authentication not configured: {required_service_auth_config}",
        )

    if service_header != expected:
        logger.warning("Invalid service credential provided for %s", required_service_auth_config)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid service key")

    return True


_SERVICE_KEY_VAULT_MAP = {
    "x_agent_service_key": "app_vault_agent_to_platform_key",
}


def _resolve_service_credential(required_service_auth_config: str) -> str | None:
    """
    Resolve service credential from app vault, falling back to settings.

    Args:
        required_service_auth_config: Config name (e.g., "X_AGENT_SERVICE_KEY")

    Returns:
        The resolved service credential value or None
    """
    from unifiedui.handlers.dependencies.vault import get_app_service_vault

    config_name = required_service_auth_config.lower()
    vault_config_attr = _SERVICE_KEY_VAULT_MAP.get(config_name)

    if vault_config_attr:
        app_vault = get_app_service_vault()
        if app_vault:
            vault_secret_name = getattr(settings, vault_config_attr, None)
            if vault_secret_name:
                try:
                    uri = app_vault.build_secret_uri(vault_secret_name)
                    result = app_vault.get_secret(uri, use_cache=False)
                    if result:
                        return result
                except Exception:
                    logger.warning("Failed to retrieve service credential from vault for config %s", config_name)

    return getattr(settings, config_name, None)


def authenticate_autonomous_agent_api_key() -> Callable:
    """
    Decorator factory to authenticate requests via X-Unified-UI-Autonomous-Agent-API-Key header.

    This validates the API key against the autonomous agent's primary or secondary key
    stored in the vault. No Bearer token is required.

    The decorated function must have:
    - request: Request - FastAPI request object
    - tenant_id: str - Path parameter
    - autonomous_agent_id: str - Path parameter

    Stores validated data in request.state:
    - request.state.autonomous_agent: The autonomous agent model
    - request.state.authenticated_via_api_key: True

    Usage:
        @authenticate_autonomous_agent_api_key()
        async def get_config(request: Request, tenant_id: str, autonomous_agent_id: str): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from unifiedui.core.database.models import AutonomousAgent
            from unifiedui.handlers.dependencies.database import get_db_client
            from unifiedui.handlers.dependencies.vault import get_secrets_vault

            # Extract request from args or kwargs
            request: Request | None = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Request object not found"
                )

            # Extract API key from header
            api_key_header = request.headers.get("X-Unified-UI-Autonomous-Agent-API-Key")
            if not api_key_header:
                logger.warning("X-Unified-UI-Autonomous-Agent-API-Key header missing")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="X-Unified-UI-Autonomous-Agent-API-Key header missing",
                )

            # Extract tenant_id and autonomous_agent_id from path params
            tenant_id = request.path_params.get("tenant_id")
            autonomous_agent_id = request.path_params.get("autonomous_agent_id")

            if not tenant_id or not autonomous_agent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Missing tenant_id or autonomous_agent_id in path"
                )

            # Get vault client and db client
            vault_client = get_secrets_vault()
            db_client = get_db_client()

            if not vault_client:
                logger.error("Vault client not configured")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error: vault not available",
                )

            # Fetch the autonomous agent to get vault URIs
            with db_client.get_session() as session:
                query = select(AutonomousAgent).where(
                    AutonomousAgent.id == autonomous_agent_id, AutonomousAgent.tenant_id == tenant_id
                )
                autonomous_agent = session.execute(query).scalar_one_or_none()

                if not autonomous_agent:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Autonomous agent not found: {autonomous_agent_id}",
                    )

                # Check if autonomous agent is active
                if not autonomous_agent.is_active:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Autonomous agent is not active")

                # Check if API key authentication is allowed
                if not autonomous_agent.allow_api_keys:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="API key authentication is not allowed for this autonomous agent. Use Bearer token with a service principal instead.",
                    )

                # Retrieve keys from vault and compare (always fresh, no cache)
                is_valid = False

                if autonomous_agent.primary_key_vault_uri:
                    try:
                        primary_key = vault_client.get_secret(
                            autonomous_agent.primary_key_vault_uri,
                            use_cache=False,  # Critical: no caching for key rotation
                        )
                        if primary_key and primary_key == api_key_header:
                            is_valid = True
                    except Exception as e:
                        logger.warning("Failed to retrieve primary key from vault: %s", e)

                if not is_valid and autonomous_agent.secondary_key_vault_uri:
                    try:
                        secondary_key = vault_client.get_secret(
                            autonomous_agent.secondary_key_vault_uri,
                            use_cache=False,  # Critical: no caching for key rotation
                        )
                        if secondary_key and secondary_key == api_key_header:
                            is_valid = True
                    except Exception as e:
                        logger.warning("Failed to retrieve secondary key from vault: %s", e)

                if not is_valid:
                    logger.warning("Invalid API key for autonomous agent %s", autonomous_agent_id)
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

                # Store autonomous agent in request state for handler use
                # Need to expunge from session to use outside
                session.expunge(autonomous_agent)
                request.state.autonomous_agent = autonomous_agent
                request.state.authenticated_via_api_key = True

                logger.info(
                    f"API key authentication successful for autonomous agent {autonomous_agent_id}",
                    extra={"tenant_id": tenant_id, "autonomous_agent_id": autonomous_agent_id},
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def authenticate_service_key(required_service_auth_key: str) -> Callable:
    """Decorator factory for service-to-service authentication via X-Service-Key header only.

    Unlike authenticate(), this does NOT require a Bearer token.
    Use for internal S2S endpoints where only machine-to-machine auth is needed.

    Args:
        required_service_auth_key: Key name in settings/vault (e.g., "X_AGENT_SERVICE_KEY").

    Usage:
        @authenticate_service_key("X_AGENT_SERVICE_KEY")
        async def internal_handler(request: Request): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request: Request | None = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Request object not found"
                )

            _validate_service_key(request, required_service_auth_key)
            request.state.service_authenticated = True
            request.state.service_key_name = required_service_auth_key

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def authenticate(required_service_auth_key: str | None = None) -> Callable:
    """
    Decorator factory to authenticate users via Bearer token from Authorization header.
    Creates a User object and injects it into the decorated function.
    Optionally uses cache based on X-Use-Cache header.

    If required_service_auth_key is provided, the decorator ALSO validates the
    X-Service-Key header against the key stored in settings/environment.
    Both service key AND Bearer token must be valid.

    Args:
        required_service_auth_key: Optional key name in settings (e.g., "X_AGENT_SERVICE_KEY").
                                   If provided, X-Service-Key header must match the settings value.

    Usage:
        @authenticate()  # Standard auth, no service key required
        async def handler(request: Request): ...

        @authenticate(required_service_auth_key="X_AGENT_SERVICE_KEY")  # Service key + Bearer
        async def internal_handler(request: Request): ...
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

            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Request object not found"
                )

            # If service auth key is required, validate X-Service-Key header first
            if required_service_auth_key:
                _validate_service_key(request, required_service_auth_key)
                request.state.service_authenticated = True
                request.state.service_key_name = required_service_auth_key

            # Extract Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authorization header missing",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Extract Bearer token
            if not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization scheme. Expected 'Bearer'",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            token = auth_header[7:]  # Remove "Bearer " prefix
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is empty",
                    headers={"WWW-Authenticate": "Bearer"},
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
                    token=token, database_client=db_client, cache_client=cache_client, use_cache=use_cache
                )
                if not user.identity.get_id():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token: unable to retrieve user identity id.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: {e!s}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Authentication error: {e!s}"
                )

            # Attach user to request state (FastAPI best practice)
            request.state.user = user
            request.state.use_cache = use_cache

            # Load organization context via JOIN (identity_provider + identity_tenant_id)
            try:
                identity_provider = user.identity.get_identity_provider()
                identity_tenant_id = user.identity.get_identity_tenant_id()
                user_id = user.identity.get_id()

                if identity_provider and identity_tenant_id:
                    from unifiedui.core.database.models import Organization, OrganizationMember

                    db = get_db_client()
                    with db.get_session() as session:
                        org = session.execute(
                            select(Organization).where(
                                Organization.identity_provider == identity_provider,
                                Organization.identity_tenant_id == identity_tenant_id,
                            )
                        ).scalar_one_or_none()

                        if org:
                            # Get user's org roles (direct + via groups)
                            identity_group_ids = [g.id for g in user.groups if g.principal_type == "IDENTITY_GROUP"]
                            all_principal_ids = [user_id, *identity_group_ids]

                            org_members = (
                                session.execute(
                                    select(OrganizationMember).where(
                                        OrganizationMember.organization_id == org.id,
                                        OrganizationMember.principal_id.in_(all_principal_ids),
                                    )
                                )
                                .scalars()
                                .all()
                            )

                            org_roles = sorted({m.role for m in org_members})

                            request.state.organization_context = {
                                "id": org.id,
                                "name": org.name,
                                "slug": org.slug,
                                "roles": org_roles,
                            }
                        else:
                            request.state.organization_context = None
                else:
                    request.state.organization_context = None
            except Exception as e:
                logger.warning("Failed to load organization context: %s", e)
                request.state.organization_context = None

            # Check tenant access if tenant_id is in path parameters
            # Skip when organization_id is also present (org routes handle their own auth)
            tenant_id = request.path_params.get("tenant_id")
            organization_id = request.path_params.get("organization_id")
            if tenant_id and not organization_id:
                user_tenants = user.tenants
                has_tenant_access = any(t["tenant"]["id"] == tenant_id for t in user_tenants)

                if not has_tenant_access:
                    org_context = getattr(request.state, "organization_context", None)
                    org_roles = org_context.get("roles", []) if org_context else []
                    org_bypass_roles = {
                        OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value,
                        OrganizationRoleEnum.ORGANISATION_TENANT_ADMIN.value,
                    }
                    has_org_bypass = bool(set(org_roles) & org_bypass_roles)

                    if not has_org_bypass:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied: User does not have access to tenant {tenant_id}",
                        )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def check_permissions(
    entity: str = "tenant",
    required_permissions: list[TenantRolesEnum | PermissionActionEnum | UserPermissionEnum] | None = None,
    required_org_roles: list[str] | None = None,
) -> Callable:
    """
    Decorator factory to check if the authenticated user has the required permissions.

    Args:
        entity: The entity type to check permissions for
               Options: "tenant", "organization", "chat_agent", "credential", "autonomous_agent",
                        "custom_group", "conversation", "tag", "chat_widget", "tool", "external_app"
        required_permissions: List of required permission enums
                            - For tenant: [TenantPermissionEnum.TENANT_GLOBAL_ADMIN, TenantPermissionEnum.READER, etc.]
                            - For resources: [PermissionActionEnum.READ, PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN]
                            - Special: [UserPermissions.IS_CREATOR] - allows access if user is the creator
                            If None or empty, no permission check is performed
        required_org_roles: List of required organization role strings (from OrganizationRoleEnum).
                           If provided, user must have one of these org roles.

    Raises:
        HTTPException: 401 if user not authenticated, 403 if permissions not met

    Example:
        @check_permissions(entity="tenant", required_permissions=[TenantPermissionEnum.TENANT_GLOBAL_ADMIN])
        async def update_tenant(...):
            ...

        @check_permissions(entity="organization", required_org_roles=["ORGANISATION_GLOBAL_ADMIN"])
        async def update_organization(...):
            ...

        @check_permissions(entity="chat_agent", required_permissions=[PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN])
        async def update_chat_agent(...):
            ...

        @check_permissions(entity="tag", required_permissions=[TenantRolesEnum.TENANT_GLOBAL_ADMIN, UserPermissions.IS_CREATOR])
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
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user: ContextIdentityUser = request.state.user

            # If no permissions required, allow access
            if not required_permissions and not required_org_roles:
                return await func(*args, **kwargs)

            # Check organization-level roles if required
            if required_org_roles:
                organization_id = request.path_params.get("organization_id")
                org_context = getattr(request.state, "organization_context", None)

                # Fast path: use pre-computed org context if it matches the target org
                if org_context and organization_id and org_context.get("id") == organization_id:
                    user_org_roles = org_context.get("roles", [])
                    if any(role in user_org_roles for role in required_org_roles):
                        return await func(*args, **kwargs)

                # Fallback: direct DB lookup for the specific organization_id
                if organization_id:
                    from unifiedui.core.database.models import OrganizationMember

                    user_id = user.identity.get_id()
                    identity_group_ids = [
                        g.id for g in user.groups if getattr(g, "principal_type", None) == "IDENTITY_GROUP"
                    ]
                    all_principal_ids = [user_id, *identity_group_ids]

                    db = get_db_client()
                    with db.get_session() as session:
                        org_members = (
                            session.execute(
                                select(OrganizationMember).where(
                                    OrganizationMember.organization_id == organization_id,
                                    OrganizationMember.principal_id.in_(all_principal_ids),
                                )
                            )
                            .scalars()
                            .all()
                        )

                        org_roles = sorted({m.role for m in org_members})
                        if any(role in org_roles for role in required_org_roles):
                            return await func(*args, **kwargs)

                # If org roles were required but not met, deny
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: User does not have required organization roles. Required one of: {required_org_roles}",
                )

            # Check permissions based on entity type
            # First: org role bypass for tenant-scoped entities
            # ORGANISATION_GLOBAL_ADMIN and ORGANISATION_TENANT_ADMIN bypass all tenant checks
            if entity != "organization" and required_org_roles is None:
                org_context = getattr(request.state, "organization_context", None)
                if org_context:
                    org_role_set = set(org_context.get("roles", []))
                    org_bypass_roles = {
                        OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value,
                        OrganizationRoleEnum.ORGANISATION_TENANT_ADMIN.value,
                    }
                    if org_role_set & org_bypass_roles:
                        return await func(*args, **kwargs)

            if entity == "tenant":
                tenant_id = request.path_params.get("tenant_id")
                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id not found in path parameters"
                    )

                # Get user's tenants and find the matching tenant
                user_tenants = user.tenants
                matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

                if not matching_tenant:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: User does not have access to tenant {tenant_id}",
                    )

                # Check if user has any of the required permissions
                # matching_tenant["roles"] is already a list of permission strings
                user_roles = matching_tenant["roles"]
                required_perms_str = [
                    perm.value if hasattr(perm, "value") else perm for perm in (required_permissions or [])
                ]
                has_permission = any(perm in user_roles for perm in required_perms_str)

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: User does not have required permissions. Required: {required_perms_str}, Has: {user_roles}",
                    )

            elif entity == "tag":
                # Special handling for tags - check TENANT_GLOBAL_ADMIN first, then IS_CREATOR
                tenant_id = request.path_params.get("tenant_id")
                tag_id = request.path_params.get("tag_id")

                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id not found in path parameters"
                    )
                if not tag_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="tag_id not found in path parameters"
                    )

                # Check tenant-level permissions first (TENANT_GLOBAL_ADMIN)
                user_tenants = user.tenants
                matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

                if matching_tenant:
                    user_tenant_permissions = matching_tenant["roles"]

                    # Check for TenantRolesEnum permissions (like TENANT_GLOBAL_ADMIN)
                    tenant_role_perms = [
                        perm for perm in (required_permissions or []) if isinstance(perm, TenantRolesEnum)
                    ]
                    for perm in tenant_role_perms:
                        if perm.value in user_tenant_permissions:
                            return await func(*args, **kwargs)

                # Check IS_CREATOR permission
                if required_permissions and UserPermissionEnum.IS_CREATOR in required_permissions:
                    user_id = user.identity.get_id()
                    db_client = get_db_client()

                    with db_client.get_session() as session:
                        tag = session.execute(
                            select(Tag).where(Tag.id == tag_id, Tag.tenant_id == tenant_id)
                        ).scalar_one_or_none()

                        if tag and tag.created_by == user_id:
                            return await func(*args, **kwargs)

                # No permission matched
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: User does not have required permissions on this tag (ID: {tag_id})",
                )

            elif entity == "user_favorite":
                # Special handling for user favorites - only the user themselves can manage their favorites
                tenant_id = request.path_params.get("tenant_id")
                target_user_id = request.path_params.get("user_id")

                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id not found in path parameters"
                    )
                if not target_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="user_id not found in path parameters"
                    )

                # Check if requesting user is the target user (IS_CREATOR check for favorites)
                if required_permissions and UserPermissionEnum.IS_CREATOR in required_permissions:
                    current_user_id = user.identity.get_id()
                    if current_user_id == target_user_id:
                        return await func(*args, **kwargs)

                # No permission matched
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: User can only manage their own favorites",
                )

            else:
                # Handle resource entities (chat_agent, credential, autonomous_agent, custom_group, conversation)
                # Now role is directly in member table - no need for JOIN

                # Map entity type to member model and ID parameter name
                entity_config = {
                    "chat_agent": (ChatAgentMember, "chat_agent_id"),
                    "credential": (CredentialMember, "credential_id"),
                    "autonomous_agent": (AutonomousAgentMember, "autonomous_agent_id"),
                    "custom_group": (CustomGroupMember, "custom_group_id"),
                    "conversation": (ConversationMember, "conversation_id"),
                    "chat_widget": (ChatWidgetMember, "chat_widget_id"),
                    "tool": (ToolMember, "tool_id"),
                    "external_app": (ExternalAppMember, "external_app_id"),
                }

                if entity not in entity_config:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unsupported entity type: {entity}"
                    )

                member_model_tuple: tuple[type[Any], str] = entity_config[entity]
                member_model, entity_id_param = member_model_tuple

                # Get entity_id from path parameters
                entity_id = request.path_params.get(entity_id_param)
                if not entity_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{entity_id_param} not found in path parameters",
                    )

                # Get tenant_id from path parameters (all resources are tenant-scoped)
                tenant_id = request.path_params.get("tenant_id")
                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id not found in path parameters"
                    )

                # Check tenant-level permissions first
                user_tenants = user.tenants
                matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

                if matching_tenant:
                    # matching_tenant["roles"] is already a list of permission strings
                    user_tenant_permissions = matching_tenant["roles"]

                    # TENANT_GLOBAL_ADMIN grants access to all resources
                    if TenantRolesEnum.TENANT_GLOBAL_ADMIN.value in user_tenant_permissions:
                        return await func(*args, **kwargs)

                    # Entity-specific admin permissions
                    entity_admin_map = {
                        "chat_agent": TenantRolesEnum.CHAT_AGENTS_ADMIN.value,
                        "credential": TenantRolesEnum.CREDENTIALS_ADMIN.value,
                        "autonomous_agent": TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN.value,
                        "custom_group": TenantRolesEnum.CUSTOM_GROUPS_ADMIN.value,
                        "conversation": TenantRolesEnum.CONVERSATIONS_ADMIN.value,
                        "chat_widget": TenantRolesEnum.CHAT_WIDGETS_ADMIN.value,
                        "tool": TenantRolesEnum.REACT_AGENT_ADMIN.value,
                        "external_app": TenantRolesEnum.EXTERNAL_APPS_ADMIN.value,
                    }

                    entity_admin = entity_admin_map.get(entity)
                    if entity_admin and entity_admin in user_tenant_permissions:
                        return await func(*args, **kwargs)

                # Get user's principal IDs (user + all groups from groups property)
                user_id = user.identity.get_id()
                user_groups = user.groups  # Contains both IDENTITY_GROUPs and CUSTOM_GROUPs

                # Extract group IDs (groups property now contains both types)
                identity_group_ids = [
                    g.id for g in user_groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
                ]
                custom_group_ids = [
                    g.id for g in user_groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value
                ]
                all_principal_ids = [user_id, *identity_group_ids, *custom_group_ids]

                # Query member with role directly - NO JOIN needed anymore
                db_client = get_db_client()
                required_perms_str = [
                    perm.value if hasattr(perm, "value") else perm for perm in (required_permissions or [])
                ]

                # Build role hierarchy: ADMIN >= WRITE >= READ
                # If user requires READ, accept ADMIN, WRITE, or READ
                # If user requires WRITE, accept ADMIN or WRITE
                # If user requires ADMIN, accept only ADMIN
                allowed_roles = set()
                if any(
                    perm in [PermissionActionEnum.READ.value, PermissionActionEnum.READ]
                    for perm in (required_permissions or [])
                ):
                    # READ required -> allow ADMIN, WRITE, READ
                    allowed_roles.update(
                        [
                            PermissionActionEnum.READ.value,
                            PermissionActionEnum.WRITE.value,
                            PermissionActionEnum.ADMIN.value,
                        ]
                    )
                elif any(
                    perm in [PermissionActionEnum.WRITE.value, PermissionActionEnum.WRITE]
                    for perm in (required_permissions or [])
                ):
                    # WRITE required -> allow ADMIN, WRITE
                    allowed_roles.update([PermissionActionEnum.WRITE.value, PermissionActionEnum.ADMIN.value])
                elif any(
                    perm in [PermissionActionEnum.ADMIN.value, PermissionActionEnum.ADMIN]
                    for perm in (required_permissions or [])
                ):
                    # ADMIN required -> allow only ADMIN
                    allowed_roles.add(PermissionActionEnum.ADMIN.value)

                with db_client.get_session() as session:
                    # Single query: Check member table directly for role
                    query = select(member_model).where(
                        getattr(member_model, entity_id_param) == entity_id,
                        member_model.tenant_id == tenant_id,
                        member_model.principal_id.in_(all_principal_ids),
                        member_model.role.in_(list(allowed_roles)),
                    )

                    result = session.execute(query).scalars().first()

                    if not result:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied: User does not have required permissions on this {entity} (ID: {entity_id}). Required one of: {required_perms_str}, Allowed roles: {list(allowed_roles)}",
                        )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
