"""Helper functions for principal management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from unifiedui.core.database.enums import PrincipalTypeEnum
from unifiedui.core.database.models import Principal
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)


def ensure_principal_exists(
    session: Session, tenant_id: str, principal_id: str, principal_type: str, user: ContextIdentityUser
) -> Principal:
    """
    Ensure a principal exists in the principals table.

    For IDENTITY_USER and IDENTITY_GROUP, fetches from IDP if not exists.
    For CUSTOM_GROUP, raises an error if not exists (must be created separately).

    Args:
        session: SQLAlchemy session
        tenant_id: The tenant ID
        principal_id: The principal ID to check/create
        principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
        user: The authenticated user context (for IDP access)

    Returns:
        The existing or newly created Principal

    Raises:
        ValueError: If CUSTOM_GROUP doesn't exist or IDP fetch fails
    """
    # Check if principal already exists
    existing = session.execute(
        select(Principal).where(Principal.tenant_id == tenant_id, Principal.principal_id == principal_id)
    ).scalar_one_or_none()

    if existing:
        logger.debug("Principal %s already exists in tenant %s", principal_id, tenant_id)
        return existing

    # For CUSTOM_GROUP, it must already exist
    if principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value:
        raise ValueError(
            f"Custom group {principal_id} does not exist. Custom groups must be created before being used as members."
        )

    # Fetch from IDP for IDENTITY_USER or IDENTITY_GROUP
    try:
        if principal_type == PrincipalTypeEnum.IDENTITY_USER.value:
            idp_data = user.idp.get_user_by_id(principal_id)
            principal = Principal(
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                display_name=idp_data.display_name,
                principal_name=idp_data.principal_name or idp_data.mail or principal_id,
                mail=idp_data.mail,
                description=None,
            )
            logger.info("Fetched and created IDENTITY_USER principal %s from IDP", principal_id)

        elif principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value:
            idp_data = user.idp.get_group_by_id(principal_id)  # type: ignore[assignment]
            principal = Principal(
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                display_name=idp_data.display_name,
                principal_name=idp_data.principal_name or idp_data.display_name,
                mail=None,
                description=None,
            )
            logger.info("Fetched and created IDENTITY_GROUP principal %s from IDP", principal_id)

        else:
            raise ValueError(f"Unknown principal type: {principal_type}")

        session.add(principal)
        session.flush()
        return principal

    except Exception as e:
        logger.error("Failed to fetch principal %s from IDP: %s", principal_id, e)
        raise ValueError(f"Failed to fetch principal {principal_id} from identity provider: {e!s}")


def get_or_create_principal(
    session: Session,
    tenant_id: str,
    principal_id: str,
    principal_type: str,
    display_name: str,
    principal_name: str,
    mail: str | None = None,
    description: str | None = None,
) -> Principal:
    """
    Get an existing principal or create a new one with provided data.

    This is useful when you already have the principal data (e.g., from creation flows).

    Args:
        session: SQLAlchemy session
        tenant_id: The tenant ID
        principal_id: The principal ID
        principal_type: The type of principal
        display_name: Display name for the principal
        principal_name: Principal name (UPN for users, display name for groups)
        mail: Optional email address
        description: Optional description

    Returns:
        The existing or newly created Principal
    """
    existing = session.execute(
        select(Principal).where(Principal.tenant_id == tenant_id, Principal.principal_id == principal_id)
    ).scalar_one_or_none()

    if existing:
        return existing

    principal = Principal(
        tenant_id=tenant_id,
        principal_id=principal_id,
        principal_type=principal_type,
        display_name=display_name,
        principal_name=principal_name,
        mail=mail,
        description=description,
    )
    session.add(principal)
    session.flush()

    logger.info("Created principal %s of type %s in tenant %s", principal_id, principal_type, tenant_id)
    return principal
