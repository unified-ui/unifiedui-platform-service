"""Central handler for resource permission operations.

This handler provides a unified interface for managing permissions on all
resource types that follow the standard *_member pattern (READ, WRITE, ADMIN roles).

Supported resource types:
- chat_agent
- autonomous_agent
- chat_widget
- conversation
- credential
- custom_group

This handler consolidates duplicate permission logic from individual resource handlers.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, TenantRolesEnum
from unifiedui.core.database.models import (
    AutonomousAgent,
    AutonomousAgentMember,
    ChatAgent,
    ChatAgentMember,
    ChatWidget,
    ChatWidgetMember,
    Conversation,
    ConversationMember,
    Credential,
    CredentialMember,
    CustomGroupMember,
    Principal,
    Tool,
    ToolMember,
)
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)


# Configuration mapping for each resource type
RESOURCE_PERMISSION_CONFIG: dict[str, dict[str, Any]] = {
    "chat_agent": {
        "resource_model": ChatAgent,
        "member_model": ChatAgentMember,
        "id_field": "chat_agent_id",
        "cache_prefix": "chat_agents",
        "tenant_admin_role": TenantRolesEnum.CHAT_AGENTS_ADMIN,
    },
    "autonomous_agent": {
        "resource_model": AutonomousAgent,
        "member_model": AutonomousAgentMember,
        "id_field": "autonomous_agent_id",
        "cache_prefix": "autonomous_agents",
        "tenant_admin_role": TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
    },
    "chat_widget": {
        "resource_model": ChatWidget,
        "member_model": ChatWidgetMember,
        "id_field": "chat_widget_id",
        "cache_prefix": "chat_widgets",
        "tenant_admin_role": TenantRolesEnum.CHAT_WIDGETS_ADMIN,
    },
    "conversation": {
        "resource_model": Conversation,
        "member_model": ConversationMember,
        "id_field": "conversation_id",
        "cache_prefix": "conversations",
        "tenant_admin_role": TenantRolesEnum.CONVERSATIONS_ADMIN,
    },
    "credential": {
        "resource_model": Credential,
        "member_model": CredentialMember,
        "id_field": "credential_id",
        "cache_prefix": "credentials",
        "tenant_admin_role": TenantRolesEnum.CREDENTIALS_ADMIN,
    },
    "custom_group": {
        "resource_model": Principal,  # Custom groups are stored in principals table
        "member_model": CustomGroupMember,
        "id_field": "custom_group_id",
        "cache_prefix": "custom_groups",
        "tenant_admin_role": TenantRolesEnum.CUSTOM_GROUPS_ADMIN,
    },
    "tool": {
        "resource_model": Tool,
        "member_model": ToolMember,
        "id_field": "tool_id",
        "cache_prefix": "tools",
        "tenant_admin_role": TenantRolesEnum.REACT_AGENT_ADMIN,
    },
}


class ResourcePermissionsHandler:
    """
    Central handler for resource permission operations.

    This handler provides a unified interface for managing permissions across
    all resource types that follow the standard *_member pattern with READ,
    WRITE, ADMIN roles.

    Usage:
        handler = ResourcePermissionsHandler(db_client, cache_client)

        # List all permissions for a resource
        principals = handler.list_permissions(
            resource_type="chat_agent",
            tenant_id="...",
            resource_id="..."
        )

        # Check if user has permission
        has_access = handler.check_user_permission(
            resource_type="chat_agent",
            tenant_id="...",
            resource_id="...",
            user=user,
            required_permission=PermissionActionEnum.WRITE
        )
    """

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        """
        Initialize the resource permissions handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def _get_config(self, resource_type: str) -> dict[str, Any]:
        """Get configuration for a resource type."""
        if resource_type not in RESOURCE_PERMISSION_CONFIG:
            raise ValueError(
                f"Unknown resource type: {resource_type}. Supported types: {list(RESOURCE_PERMISSION_CONFIG.keys())}"
            )
        return RESOURCE_PERMISSION_CONFIG[resource_type]

    def _verify_resource_exists(self, session: Session, resource_type: str, tenant_id: str, resource_id: str) -> bool:
        """
        Verify that a resource exists.

        Args:
            session: SQLAlchemy session
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID

        Returns:
            True if resource exists

        Raises:
            ValueError: If resource not found
        """
        config = self._get_config(resource_type)
        model = config["resource_model"]

        if resource_type == "custom_group":
            # Custom groups are stored in principals table with type CUSTOM_GROUP
            result = session.execute(
                select(Principal).where(
                    Principal.tenant_id == tenant_id,
                    Principal.principal_id == resource_id,
                    Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
                )
            ).scalar_one_or_none()
        else:
            result = session.execute(
                select(model).where(model.id == resource_id, model.tenant_id == tenant_id)
            ).scalar_one_or_none()

        if not result:
            raise ValueError(f"{resource_type} with id {resource_id} not found")
        return True

    def list_permissions(
        self,
        resource_type: str,
        tenant_id: str,
        resource_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        List all permissions for a resource, grouped by principal.

        Returns enriched principal data including mail, display_name, principal_name, description.

        Args:
            resource_type: Type of resource (chat_agent, credential, etc.)
            tenant_id: Tenant ID
            resource_id: Resource ID
            skip: Number of principals to skip (for pagination)
            limit: Maximum number of principals to return
            search: Search term to filter by display_name, principal_name, or mail (case-insensitive)
            roles: List of roles to filter by (OR logic)
            is_active: Filter by principal is_active status
            order_by: Column to order by (only 'display_name' supported)
            order_direction: Sort direction ('asc' or 'desc')
            use_cache: Whether to use caching (disabled when filters are applied)

        Returns:
            Dict with resource_id, resource_type, tenant_id, and principals list
            Each principal includes: principal_id, principal_type, roles, mail, display_name, principal_name, description
        """
        logger.info(
            "Listing permissions",
            extra={
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "skip": skip,
                "limit": limit,
                "search": search,
                "roles": roles,
                "is_active": is_active,
                "order_by": order_by,
                "order_direction": order_direction,
            },
        )

        config = self._get_config(resource_type)
        member_model = config["member_model"]
        id_field = config["id_field"]
        cache_prefix = config["cache_prefix"]

        # Disable caching when filters are applied
        has_filters = any([search, roles, is_active is not None, skip > 0, limit != 100, order_by, order_direction])
        use_cache = use_cache and not has_filters

        # Build cache key (only used when no filters)
        cache_key = f"{cache_prefix}:permissions:tenant:{tenant_id}:res:{resource_id}:list"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached permissions list for %s", resource_type)
                    return cached_data
            except Exception as e:
                logger.warning("Failed to get cached permissions: %s", e)

        with self.db_client.get_session() as session:
            from sqlalchemy import func, or_

            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Build base query - get all members with joined principal data
            query = (
                select(member_model, Principal)
                .outerjoin(
                    Principal,
                    (member_model.tenant_id == Principal.tenant_id)
                    & (member_model.principal_id == Principal.principal_id),
                )
                .where(getattr(member_model, id_field) == resource_id, member_model.tenant_id == tenant_id)
            )

            # Apply role filter (filter members by role)
            if roles:
                query = query.where(member_model.role.in_(roles))

            # Apply search filter on principal fields
            if search:
                search_term = f"%{search}%"
                query = query.where(
                    or_(
                        func.lower(Principal.display_name).like(func.lower(search_term)),
                        func.lower(Principal.principal_name).like(func.lower(search_term)),
                        func.lower(Principal.mail).like(func.lower(search_term)),
                    )
                )

            # Apply is_active filter
            if is_active is not None:
                query = query.where(Principal.is_active == is_active)

            results = session.execute(query).all()

            # Group by principal
            principals_dict: dict[str, dict[str, Any]] = {}
            for member, principal in results:
                key = member.principal_id
                if key not in principals_dict:
                    principals_dict[key] = {
                        "principal_id": member.principal_id,
                        "principal_type": principal.principal_type if principal else None,
                        "roles": [],
                        "mail": principal.mail if principal else None,
                        "display_name": principal.display_name if principal else None,
                        "principal_name": principal.principal_name if principal else None,
                        "description": principal.description if principal else None,
                        "is_active": principal.is_active if principal else True,
                    }

                role_value = member.role.value if hasattr(member.role, "value") else member.role
                if role_value not in principals_dict[key]["roles"]:
                    principals_dict[key]["roles"].append(role_value)

            # Convert to list for sorting and pagination
            principals_list = list(principals_dict.values())

            # Apply sorting
            if order_by == "display_name":
                reverse = order_direction == "desc"
                principals_list.sort(key=lambda x: (x.get("display_name") or "").lower(), reverse=reverse)

            # Apply pagination
            len(principals_list)
            principals_list = principals_list[skip : skip + limit]

            result = {
                "resource_id": resource_id,
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "principals": principals_list,
            }

            # Cache the result (only when no filters)
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result, ttl=300)
                    logger.debug("Cached permissions list for %s", resource_type)
                except Exception as e:
                    logger.warning("Failed to cache permissions: %s", e)

            return result

    def get_permission(self, resource_type: str, tenant_id: str, resource_id: str, principal_id: str) -> dict[str, Any]:
        """
        Get all permissions for a specific principal on a resource.

        Returns enriched principal data including mail, display_name, principal_name, description.

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            principal_id: Principal ID

        Returns:
            Dict with principal info, roles, and enriched data from principals table

        Raises:
            ValueError: If resource or permission not found
        """
        logger.info(
            "Getting permission",
            extra={
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "principal_id": principal_id,
            },
        )

        config = self._get_config(resource_type)
        member_model = config["member_model"]
        id_field = config["id_field"]

        with self.db_client.get_session() as session:
            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Get members for this principal with joined principal data
            query = (
                select(member_model, Principal)
                .outerjoin(
                    Principal,
                    (member_model.tenant_id == Principal.tenant_id)
                    & (member_model.principal_id == Principal.principal_id),
                )
                .where(
                    getattr(member_model, id_field) == resource_id,
                    member_model.tenant_id == tenant_id,
                    member_model.principal_id == principal_id,
                )
            )
            results = session.execute(query).all()

            if not results:
                raise ValueError(f"No permissions found for principal {principal_id} on {resource_type} {resource_id}")

            # Extract roles and principal info
            roles = []
            principal_data = None
            for member, principal in results:
                role_value = member.role.value if hasattr(member.role, "value") else member.role
                if role_value not in roles:
                    roles.append(role_value)
                if principal and principal_data is None:
                    principal_data = principal

            return {
                "resource_id": resource_id,
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_data.principal_type if principal_data else None,
                "roles": roles,
                "mail": principal_data.mail if principal_data else None,
                "display_name": principal_data.display_name if principal_data else None,
                "principal_name": principal_data.principal_name if principal_data else None,
                "description": principal_data.description if principal_data else None,
            }

    def set_permission(
        self,
        resource_type: str,
        tenant_id: str,
        resource_id: str,
        principal_id: str,
        principal_type: str,
        role: PermissionActionEnum,
        user_id: str,
        user: ContextIdentityUser,
    ) -> dict[str, Any]:
        """
        Set or update a permission for a principal on a resource.

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            principal_id: Principal to grant permission to
            principal_type: Type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            role: Permission role to grant
            user_id: User performing the operation
            user: User context for IDP access

        Returns:
            Dict with created/updated permission info
        """
        logger.info(
            "Setting permission",
            extra={
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "principal_id": principal_id,
                "role": role.value if hasattr(role, "value") else role,
            },
        )

        config = self._get_config(resource_type)
        member_model = config["member_model"]
        id_field = config["id_field"]

        with self.db_client.get_session() as session:
            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Ensure principal exists
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                user=user,
            )

            # Check if member already exists
            query = select(member_model).where(
                getattr(member_model, id_field) == resource_id,
                member_model.tenant_id == tenant_id,
                member_model.principal_id == principal_id,
            )
            member = session.execute(query).scalar_one_or_none()

            role_value = role.value if hasattr(role, "value") else role

            if not member:
                # Create new member
                member_id = str(uuid.uuid4())
                member_kwargs = {
                    "id": member_id,
                    "tenant_id": tenant_id,
                    id_field: resource_id,
                    "principal_id": principal_id,
                    "role": role_value,
                    "created_by": user_id,
                    "updated_by": user_id,
                }
                member = member_model(**member_kwargs)
                session.add(member)
                session.commit()
                session.refresh(member)
                logger.info("Created member for %s", resource_type, extra={"member_id": member_id})
            elif member.role != role_value:
                # Update existing member's role
                member.role = role_value
                member.updated_by = user_id
                session.commit()
                session.refresh(member)
                logger.info("Updated member role for %s", resource_type, extra={"member_id": member.id})
            else:
                logger.info("Member already has role for %s", resource_type, extra={"member_id": member.id})

            # Invalidate caches
            self._invalidate_permissions_cache(resource_type, tenant_id, resource_id)
            self._invalidate_user_cache(principal_id, principal_type)

            return {
                "id": member.id,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "role": role_value,
                "created_at": member.created_at,
                "updated_at": member.updated_at,
            }

    def delete_permission(
        self, resource_type: str, tenant_id: str, resource_id: str, principal_id: str, principal_type: str, role: str
    ) -> None:
        """
        Delete a specific permission for a principal on a resource.

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            principal_id: Principal ID
            principal_type: Principal type
            role: Permission to delete

        Raises:
            ValueError: If permission not found
        """
        logger.info(
            "Deleting permission",
            extra={
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "principal_id": principal_id,
                "role": role,
            },
        )

        config = self._get_config(resource_type)
        member_model = config["member_model"]
        id_field = config["id_field"]

        with self.db_client.get_session() as session:
            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Find member with specific role
            query = select(member_model).where(
                getattr(member_model, id_field) == resource_id,
                member_model.tenant_id == tenant_id,
                member_model.principal_id == principal_id,
                member_model.role == role,
            )
            member = session.execute(query).scalar_one_or_none()

            if not member:
                raise ValueError(
                    f"Member with role {role} not found for principal {principal_id} on {resource_type} {resource_id}"
                )

            session.delete(member)
            session.commit()
            logger.info("Deleted member with role for %s", resource_type)

            # Invalidate caches
            self._invalidate_permissions_cache(resource_type, tenant_id, resource_id)
            self._invalidate_user_cache(principal_id, principal_type)

    def check_user_permission(
        self,
        resource_type: str,
        tenant_id: str,
        resource_id: str,
        user: ContextIdentityUser,
        required_permission: PermissionActionEnum,
    ) -> bool:
        """
        Check if a user has the required permission on a resource.

        This method checks:
        1. Tenant-level admin permissions (TENANT_GLOBAL_ADMIN, resource-specific admin)
        2. Direct user permissions
        3. Identity group permissions
        4. Custom group permissions

        Role hierarchy: ADMIN >= WRITE >= READ

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            user: User context
            required_permission: Required permission level

        Returns:
            True if user has permission, False otherwise
        """
        config = self._get_config(resource_type)
        member_model = config["member_model"]
        id_field = config["id_field"]
        tenant_admin_role = config["tenant_admin_role"]

        # Check tenant-level permissions first
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        if matching_tenant:
            user_roles = matching_tenant["roles"]

            # TENANT_GLOBAL_ADMIN grants access to all resources
            if TenantRolesEnum.TENANT_GLOBAL_ADMIN.value in user_roles:
                return True

            # Resource-specific admin grants access
            if tenant_admin_role.value in user_roles:
                return True

        # Get all principal IDs for the user
        user_id = user.identity.get_id()
        identity_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value]
        custom_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]
        all_principal_ids = [user_id, *identity_group_ids, *custom_group_ids]

        # Build role hierarchy
        allowed_roles = self._get_allowed_roles(required_permission)

        with self.db_client.get_session() as session:
            query = select(member_model).where(
                getattr(member_model, id_field) == resource_id,
                member_model.tenant_id == tenant_id,
                member_model.principal_id.in_(all_principal_ids),
                member_model.role.in_(list(allowed_roles)),
            )
            result = session.execute(query).scalars().first()
            return result is not None

    def is_user_admin(self, resource_type: str, tenant_id: str, user: ContextIdentityUser) -> bool:
        """
        Check if user is an admin for a resource type (tenant-level check).

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            user: User context

        Returns:
            True if user is admin
        """
        config = self._get_config(resource_type)
        tenant_admin_role = config["tenant_admin_role"]

        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        if not matching_tenant:
            return False

        user_roles = matching_tenant["roles"]
        admin_roles = [TenantRolesEnum.TENANT_GLOBAL_ADMIN.value, tenant_admin_role.value]
        return any(role in user_roles for role in admin_roles)

    def get_user_principal_ids(self, user: ContextIdentityUser) -> list[str]:
        """
        Get all principal IDs for a user (user ID + group IDs).

        Args:
            user: User context

        Returns:
            List of principal IDs
        """
        user_id = user.identity.get_id()
        identity_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value]
        custom_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]
        return [user_id, *identity_group_ids, *custom_group_ids]

    @staticmethod
    def _get_allowed_roles(required_permission: PermissionActionEnum) -> set:
        """
        Get the set of roles that satisfy a required permission.

        Role hierarchy: ADMIN >= WRITE >= READ

        Args:
            required_permission: Required permission level

        Returns:
            Set of allowed role values
        """
        perm_value = required_permission.value if hasattr(required_permission, "value") else required_permission

        if perm_value == PermissionActionEnum.READ.value:
            return {PermissionActionEnum.READ.value, PermissionActionEnum.WRITE.value, PermissionActionEnum.ADMIN.value}
        elif perm_value == PermissionActionEnum.WRITE.value:
            return {PermissionActionEnum.WRITE.value, PermissionActionEnum.ADMIN.value}
        elif perm_value == PermissionActionEnum.ADMIN.value:
            return {PermissionActionEnum.ADMIN.value}
        else:
            return {perm_value}

    def _invalidate_permissions_cache(self, resource_type: str, tenant_id: str, resource_id: str) -> None:
        """Invalidate permissions cache for a resource."""
        if self.cache_client:
            config = self._get_config(resource_type)
            cache_prefix = config["cache_prefix"]
            pattern = f"{cache_prefix}:permissions:tenant:{tenant_id}:res:{resource_id}:*"
            self.cache_client.client.delete_pattern(pattern)

            # Also invalidate list caches
            list_pattern = f"{cache_prefix}:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(list_pattern)

    def _invalidate_user_cache(self, principal_id: str, principal_type: str) -> None:
        """Invalidate cache for a user after permission changes."""
        if self.cache_client and principal_type == PrincipalTypeEnum.IDENTITY_USER.value:
            try:
                self.cache_client.clear_cache_for_user(principal_id)
                logger.debug("Cleared cache for user %s", principal_id)
            except Exception as e:
                logger.warning("Failed to clear user cache: %s", e)

    def add_creator_permission(
        self,
        session: Session,
        resource_type: str,
        tenant_id: str,
        resource_id: str,
        user_id: str,
        user: ContextIdentityUser,
    ) -> None:
        """
        Add creator (ADMIN) permission for a newly created resource.

        This should be called during resource creation to grant the creator
        ADMIN access to the resource.

        Args:
            session: SQLAlchemy session (should be part of the creation transaction)
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            user_id: User ID of the creator
            user: User context for IDP access
        """
        config = self._get_config(resource_type)
        member_model = config["member_model"]
        id_field = config["id_field"]

        # Ensure principal exists
        ensure_principal_exists(
            session=session,
            tenant_id=tenant_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            user=user,
        )

        # Create member with ADMIN role
        member_id = str(uuid.uuid4())
        member_kwargs = {
            "id": member_id,
            "tenant_id": tenant_id,
            id_field: resource_id,
            "principal_id": user_id,
            "role": PermissionActionEnum.ADMIN.value,
            "created_by": user_id,
            "updated_by": user_id,
        }
        member = member_model(**member_kwargs)
        session.add(member)
        logger.info("Added creator permission for %s", resource_type, extra={"member_id": member_id})
