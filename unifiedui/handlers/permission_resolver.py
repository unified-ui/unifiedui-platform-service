"""Utility for resolving user permissions on resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from unifiedui.core.database.enums import PermissionActionEnum, TenantRolesEnum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.core.database.models import Base
    from unifiedui.core.identity.users import ContextIdentityUser

PERMISSION_HIERARCHY = {
    PermissionActionEnum.ADMIN.value: 3,
    PermissionActionEnum.WRITE.value: 2,
    PermissionActionEnum.READ.value: 1,
}


def get_principal_ids(user: ContextIdentityUser) -> list[str]:
    """Collect all principal IDs for a user (user ID + group IDs).

    Args:
        user: The authenticated user context

    Returns:
        List of principal IDs
    """
    user_id = user.identity.get_id()
    principal_ids = [user_id]
    if user.groups:
        principal_ids.extend(g.id for g in user.groups)
    if user.custom_groups:
        principal_ids.extend(g.id for g in user.custom_groups)
    return principal_ids


def check_is_admin(user: ContextIdentityUser, tenant_id: str, admin_roles: list[TenantRolesEnum]) -> bool:
    """Check if the user has admin-level tenant roles.

    Args:
        user: The authenticated user context
        tenant_id: The tenant ID to check roles for
        admin_roles: List of admin roles to check

    Returns:
        True if user has any of the admin roles
    """
    matching_tenant = next((t for t in user.tenants if t["tenant"]["id"] == tenant_id), None)
    if not matching_tenant:
        return False
    user_roles = matching_tenant["roles"]
    admin_values = [r.value for r in admin_roles]
    return any(role in user_roles for role in admin_values)


def resolve_my_permission(
    session: Session,
    member_model: type[Base],
    id_field: str,
    tenant_id: str,
    resource_id: str,
    principal_ids: list[str],
) -> str | None:
    """Resolve the highest permission a user has on a single resource.

    Args:
        session: SQLAlchemy session
        member_model: The member model class (e.g., ChatAgentMember)
        id_field: The resource ID field name on the member model
        tenant_id: Tenant ID
        resource_id: The resource ID
        principal_ids: All principal IDs for the user

    Returns:
        The highest permission action string or None
    """
    query = select(member_model.role).where(
        getattr(member_model, id_field) == resource_id,
        member_model.tenant_id == tenant_id,
        member_model.principal_id.in_(principal_ids),
    )
    roles = session.execute(query).scalars().all()
    if not roles:
        return None
    return max(roles, key=lambda r: PERMISSION_HIERARCHY.get(r, 0))


def resolve_my_permissions_bulk(
    session: Session,
    member_model: type[Base],
    id_field: str,
    tenant_id: str,
    resource_ids: list[str],
    principal_ids: list[str],
) -> dict[str, str]:
    """Resolve the highest permission a user has on multiple resources.

    Args:
        session: SQLAlchemy session
        member_model: The member model class
        id_field: The resource ID field name on the member model
        tenant_id: Tenant ID
        resource_ids: List of resource IDs
        principal_ids: All principal IDs for the user

    Returns:
        Dict mapping resource_id to highest permission action string
    """
    if not resource_ids:
        return {}

    resource_id_col = getattr(member_model, id_field)
    query = select(resource_id_col, member_model.role).where(
        resource_id_col.in_(resource_ids),
        member_model.tenant_id == tenant_id,
        member_model.principal_id.in_(principal_ids),
    )
    rows = session.execute(query).all()

    result: dict[str, str] = {}
    for rid, role in rows:
        current = result.get(rid)
        if current is None or PERMISSION_HIERARCHY.get(role, 0) > PERMISSION_HIERARCHY.get(current, 0):
            result[rid] = role

    return result
