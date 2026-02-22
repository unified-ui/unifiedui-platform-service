"""Handler for principal operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, or_, select

from unifiedui.core.database.enums import PrincipalTypeEnum
from unifiedui.core.database.models import CustomGroupMember, Principal, Tenant, TenantMember
from unifiedui.exc.tenants import TenantNotFoundError
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger
from unifiedui.schema.responses.principals import PrincipalResponse
from unifiedui.schema.responses.tenants import (
    TenantPrincipalResponse,
    TenantPrincipalsResponse,
    TenantRoleDetailResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)


class PrincipalHandler:
    """Handler for principal operations."""

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        """
        Initialize the principal handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def refresh_principal(
        self, tenant_id: str, principal_id: str, principal_type: str, user: ContextIdentityUser
    ) -> PrincipalResponse:
        """
        Refresh a principal from the identity provider.

        Fetches the user/group from the identity provider and updates or creates
        the principal record in the database.

        Args:
            tenant_id: The tenant ID where the principal should be stored
            principal_id: The ID of the principal to refresh
            principal_type: The type of principal (IDENTITY_USER or IDENTITY_GROUP)
            user: ContextIdentityUser object for identity provider access

        Returns:
            PrincipalResponse with the refreshed principal data

        Raises:
            ValueError: If principal_type is invalid or CUSTOM_GROUP
        """
        logger.info(
            "Refreshing principal from identity provider",
            extra={"tenant_id": tenant_id, "principal_id": principal_id, "principal_type": principal_type},
        )

        # Validate principal type
        if principal_type not in [PrincipalTypeEnum.IDENTITY_USER.value, PrincipalTypeEnum.IDENTITY_GROUP.value]:
            raise ValueError(f"Invalid principal type: {principal_type}. Must be IDENTITY_USER or IDENTITY_GROUP.")

        # Fetch from identity provider
        if principal_type == PrincipalTypeEnum.IDENTITY_USER.value:
            identity_data = user.idp.get_user_by_id(principal_id)
            display_name = identity_data.display_name
            mail = identity_data.mail
            description = None
            # For users, principal_name is their email/principal_name from identity data
            principal_name = identity_data.principal_name or identity_data.mail or display_name
        else:  # IDENTITY_GROUP
            identity_data = user.idp.get_group_by_id(principal_id)
            display_name = identity_data.display_name
            mail = None
            description = None
            # For groups, principal_name equals display_name
            principal_name = display_name

        with self.db_client.get_session() as session:
            # Try to find existing principal
            existing_principal = session.execute(
                select(Principal).where(Principal.tenant_id == tenant_id, Principal.principal_id == principal_id)
            ).scalar_one_or_none()

            if existing_principal:
                # Update existing principal
                existing_principal.principal_type = principal_type
                existing_principal.mail = mail
                existing_principal.display_name = display_name
                existing_principal.principal_name = principal_name
                # Note: description is not updated from identity provider

                logger.info("Updated existing principal", extra={"tenant_id": tenant_id, "principal_id": principal_id})

                session.flush()
                result = self._model_to_response(existing_principal)
            else:
                # Create new principal
                new_principal = Principal(
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    principal_type=principal_type,
                    mail=mail,
                    display_name=display_name,
                    principal_name=principal_name,
                    description=description,
                )
                session.add(new_principal)
                session.flush()

                logger.info("Created new principal", extra={"tenant_id": tenant_id, "principal_id": principal_id})

                result = self._model_to_response(new_principal)

            # Invalidate related caches
            self._invalidate_principal_caches(tenant_id, principal_id)

            return result

    def get_principal(self, tenant_id: str, principal_id: str, use_cache: bool = True) -> PrincipalResponse | None:
        """
        Get a principal by tenant and principal ID.

        Args:
            tenant_id: The tenant ID
            principal_id: The principal ID
            use_cache: Whether to use caching

        Returns:
            PrincipalResponse or None if not found
        """
        cache_key = f"principals:detail:tenant:{tenant_id}:principal:{principal_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached principal")
                    return PrincipalResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached principal: {e}")

        with self.db_client.get_session() as session:
            principal = session.execute(
                select(Principal).where(Principal.tenant_id == tenant_id, Principal.principal_id == principal_id)
            ).scalar_one_or_none()

            if not principal:
                return None

            result = self._model_to_response(principal)

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached principal detail")
                except Exception as e:
                    logger.warning(f"Failed to cache principal: {e}")

            return result

    def _model_to_response(self, principal: Principal) -> PrincipalResponse:
        """Convert a Principal model to a PrincipalResponse."""
        return PrincipalResponse(
            tenant_id=principal.tenant_id,
            principal_id=principal.principal_id,
            principal_type=principal.principal_type,
            mail=principal.mail,
            display_name=principal.display_name,
            principal_name=principal.principal_name,
            description=principal.description,
            is_active=principal.is_active,
            created_at=principal.created_at,
            updated_at=principal.updated_at,
        )

    def update_principal_status(self, tenant_id: str, principal_id: str, is_active: bool) -> PrincipalResponse:
        """
        Update the is_active status of a principal.

        Args:
            tenant_id: The tenant ID
            principal_id: The principal ID
            is_active: The new status

        Returns:
            PrincipalResponse with the updated principal data

        Raises:
            ValueError: If principal is not found
        """
        logger.info(
            "Updating principal status",
            extra={"tenant_id": tenant_id, "principal_id": principal_id, "is_active": is_active},
        )

        with self.db_client.get_session() as session:
            principal = session.execute(
                select(Principal).where(Principal.tenant_id == tenant_id, Principal.principal_id == principal_id)
            ).scalar_one_or_none()

            if not principal:
                raise ValueError(f"Principal not found: {principal_id}")

            principal.is_active = is_active
            session.flush()

            result = self._model_to_response(principal)

            # Invalidate related caches
            self._invalidate_principal_caches(tenant_id, principal_id)

            logger.info(
                "Updated principal status",
                extra={"tenant_id": tenant_id, "principal_id": principal_id, "is_active": is_active},
            )

            return result

    def list_tenant_principals(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = "asc",
    ) -> TenantPrincipalsResponse:
        """
        Get all principals and their roles for a specific tenant.

        Args:
            tenant_id: The ID of the tenant
            skip: Number of principals to skip (for pagination)
            limit: Maximum number of principals to return
            search: Search term for display_name, principal_name, or mail
            roles: List of roles to filter by (OR logic)
            is_active: Filter by principal's active status
            order_by: Column to order by (currently only 'display_name')
            order_direction: Sort direction ('asc' or 'desc')

        Returns:
            TenantPrincipalsResponse with tenant_id and list of principals with their roles

        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Listing all principals for tenant", extra={"tenant_id": tenant_id})

        with self.db_client.get_session() as session:
            # Check if tenant exists
            self._validate_tenant_exists(session, tenant_id)

            # Build base query joining TenantMember with Principal
            query = (
                select(TenantMember, Principal)
                .join(
                    Principal,
                    and_(
                        TenantMember.tenant_id == Principal.tenant_id,
                        TenantMember.principal_id == Principal.principal_id,
                    ),
                )
                .where(TenantMember.tenant_id == tenant_id)
            )

            # Apply role filter (filter members with matching roles)
            if roles:
                query = query.where(TenantMember.role.in_(roles))

            # Apply is_active filter
            if is_active is not None:
                query = query.where(Principal.is_active == is_active)

            # Apply search filter (case-insensitive)
            if search:
                search_term = f"%{search.lower()}%"
                query = query.where(
                    or_(
                        func.lower(Principal.display_name).like(search_term),
                        func.lower(Principal.principal_name).like(search_term),
                        func.lower(Principal.mail).like(search_term),
                    )
                )

            # Execute query
            results = session.execute(query).all()

            # Group roles by principal_id
            principals_dict: dict = {}
            for member, principal in results:
                if member.principal_id not in principals_dict:
                    principals_dict[member.principal_id] = {
                        "principal_id": member.principal_id,
                        "principal_type": principal.principal_type,
                        "display_name": principal.display_name,
                        "principal_name": principal.principal_name,
                        "mail": principal.mail,
                        "description": principal.description,
                        "is_active": principal.is_active,
                        "roles": [],
                    }
                # Append role with details
                principals_dict[member.principal_id]["roles"].append(
                    TenantRoleDetailResponse(
                        role=member.role,
                        display_name=self._get_role_display_name(member.role),
                        created_at=member.created_at,
                    )
                )

            # Convert to list of TenantPrincipalResponse
            principals = [TenantPrincipalResponse(**data) for data in principals_dict.values()]

            # Apply sorting
            if order_by == "display_name":
                reverse = order_direction == "desc"
                principals.sort(key=lambda p: (p.display_name or "").lower(), reverse=reverse)
            else:
                # Default: sort by display_name ascending
                principals.sort(key=lambda p: (p.display_name or "").lower())

            # Apply pagination after grouping
            paginated_principals = principals[skip : skip + limit]

            logger.info(
                "Retrieved tenant principals",
                extra={"tenant_id": tenant_id, "principal_count": len(paginated_principals), "total": len(principals)},
            )

            return TenantPrincipalsResponse(tenant_id=tenant_id, principals=paginated_principals)

    def get_principal_permissions(self, tenant_id: str, principal_id: str) -> dict:
        """
        Get all permissions for a specific principal on a tenant.

        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal

        Returns:
            Dict with tenant_id, principal_id, and roles list

        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Getting principal roles", extra={"tenant_id": tenant_id, "principal_id": principal_id})

        with self.db_client.get_session() as session:
            # Check if tenant exists
            self._validate_tenant_exists(session, tenant_id)

            # Query member roles, joining with Principal to get principal_type
            query = (
                select(TenantMember, Principal)
                .join(
                    Principal,
                    and_(
                        TenantMember.tenant_id == Principal.tenant_id,
                        TenantMember.principal_id == Principal.principal_id,
                    ),
                )
                .where(TenantMember.tenant_id == tenant_id, TenantMember.principal_id == principal_id)
            )

            results = session.execute(query).all()

            # Extract principal_type and is_active from first result's Principal (all should have same type)
            principal_type = results[0][1].principal_type if results else None
            is_active = results[0][1].is_active if results else True
            # Extract just the role strings
            roles = [role.role for role, principal in results]

            logger.info(
                "Retrieved principal permissions",
                extra={"tenant_id": tenant_id, "principal_id": principal_id, "permission_count": len(roles)},
            )

            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "is_active": is_active,
                "roles": roles,
            }

    def set_principal_permission(
        self,
        tenant_id: str,
        principal_id: str,
        principal_type: str,
        permission: str,
        user_id: str,
        user: ContextIdentityUser,
    ) -> dict:
        """
        Add or update a permission for a principal on a tenant.

        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            permission: The permission to assign
            user_id: The ID of the user making the change
            user: The authenticated user context (for IDP access)

        Returns:
            Dict with tenant_id, principal_id, and updated roles list

        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info(
            "Setting principal permission",
            extra={
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "permission": permission,
                "user_id": user_id,
            },
        )

        with self.db_client.get_session() as session:
            # Check if tenant exists
            self._validate_tenant_exists(session, tenant_id)

            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                user=user,
            )

            # Check if role already exists for this principal
            role_query = select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.principal_id == principal_id,
                TenantMember.role == permission,
            )
            existing_role = session.execute(role_query).scalar_one_or_none()

            if not existing_role:
                # Create new role
                role_id = str(uuid.uuid4())
                role = TenantMember(
                    id=role_id,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    role=permission,
                    created_by=user_id,
                    updated_by=user_id,
                )
                session.add(role)
                session.flush()
                logger.info(
                    "Created new tenant member role",
                    extra={
                        "tenant_id": tenant_id,
                        "principal_id": principal_id,
                        "role_id": role_id,
                        "role": permission,
                    },
                )
            else:
                logger.info(
                    "Role already exists for this principal",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id, "role": permission},
                )

            # Commit the changes before invalidating cache
            session.commit()

            # Invalidate cache for affected users
            self._invalidate_cache_for_principal(session, principal_id, principal_type, user_id)

            # Get all roles for this principal
            query = (
                select(TenantMember)
                .where(TenantMember.tenant_id == tenant_id, TenantMember.principal_id == principal_id)
                .order_by(TenantMember.role)
            )
            results = session.execute(query).all()

            # Extract just the role strings
            roles = [role[0].role for role in results]

            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "roles": roles,
            }

    def delete_principal_permission(
        self, tenant_id: str, principal_id: str, principal_type: str, permission: str
    ) -> dict:
        """
        Remove a specific permission from a principal on a tenant.

        Args:
            tenant_id: The ID of the tenant
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            permission: The permission to remove

        Returns:
            Dict with tenant_id, principal_id, and remaining roles list

        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info(
            "Deleting principal permission",
            extra={
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "permission": permission,
            },
        )

        with self.db_client.get_session() as session:
            # Check if tenant exists
            self._validate_tenant_exists(session, tenant_id)

            # Find and delete the specific role
            role_query = select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.principal_id == principal_id,
                TenantMember.role == permission,
            )
            role = session.execute(role_query).scalar_one_or_none()

            if role:
                session.delete(role)
                logger.info(
                    "Deleted principal role",
                    extra={
                        "tenant_id": tenant_id,
                        "principal_id": principal_id,
                        "principal_type": principal_type,
                        "role": permission,
                    },
                )
            else:
                logger.info(
                    "Role not found, nothing to delete",
                    extra={
                        "tenant_id": tenant_id,
                        "principal_id": principal_id,
                        "principal_type": principal_type,
                        "role": permission,
                    },
                )

            session.flush()

            # Invalidate cache for affected users (uses admin user_id=None for tracking)
            self._invalidate_cache_for_principal(session, principal_id, principal_type, "")

            # Get remaining roles for this principal
            query = (
                select(TenantMember)
                .where(TenantMember.tenant_id == tenant_id, TenantMember.principal_id == principal_id)
                .order_by(TenantMember.role)
            )
            remaining_results = session.execute(query).all()

            # Extract just the role strings
            roles = [role[0].role for role in remaining_results]

            return {
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "roles": roles,
            }

    def _get_role_display_name(self, role: str) -> str:
        """Get a human-readable display name for a role."""
        role_display_names = {
            "TENANT_GLOBAL_ADMIN": "Global Administrator",
            "READER": "Reader",
            "CUSTOM_GROUPS_ADMIN": "Custom Groups Administrator",
            "CUSTOM_GROUP_CREATOR": "Custom Group Creator",
            "CHAT_AGENTS_ADMIN": "Chat Agents Administrator",
            "CHAT_AGENTS_CREATOR": "Chat Agent Creator",
            "CREDENTIALS_ADMIN": "Credentials Administrator",
            "CREDENTIALS_CREATOR": "Credential Creator",
            "CONVERSATIONS_ADMIN": "Conversations Administrator",
            "CONVERSATIONS_CREATOR": "Conversation Creator",
            "AUTONOMOUS_AGENTS_ADMIN": "Autonomous Agents Administrator",
            "AUTONOMOUS_AGENTS_CREATOR": "Autonomous Agent Creator",
            "CHAT_WIDGETS_ADMIN": "Chat Widgets Administrator",
            "CHAT_WIDGETS_CREATOR": "Chat Widget Creator",
        }
        return role_display_names.get(role, role.replace("_", " ").title())

    def _validate_tenant_exists(self, session: Session, tenant_id: str) -> Tenant:
        """
        Validate that a tenant exists.

        Args:
            session: Database session
            tenant_id: ID of the tenant

        Returns:
            Tenant model

        Raises:
            TenantNotFoundError: If tenant not found
        """
        tenant = session.get(Tenant, tenant_id)
        if not tenant:
            logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
            raise TenantNotFoundError(tenant_id)
        return tenant

    def _invalidate_cache_for_principal(self, session: Session, principal_id: str, principal_type: str, user_id: str):
        """
        Invalidate cache for affected users based on principal type.

        Args:
            session: Database session
            principal_id: ID of the principal
            principal_type: Type of principal (IDENTITY_USER, CUSTOM_GROUP, IDENTITY_GROUP)
            user_id: ID of the user making the change
        """
        if not self.cache_client:
            return

        try:
            users_to_invalidate = []

            if principal_type == "IDENTITY_USER":
                # Direct user - invalidate their cache
                users_to_invalidate.append(principal_id)
            elif principal_type == "CUSTOM_GROUP":
                # Custom group - invalidate cache for all group members who are users
                member_query = (
                    select(CustomGroupMember.principal_id)
                    .join(
                        Principal,
                        and_(
                            CustomGroupMember.tenant_id == Principal.tenant_id,
                            CustomGroupMember.principal_id == Principal.principal_id,
                        ),
                    )
                    .where(
                        CustomGroupMember.custom_group_id == principal_id, Principal.principal_type == "IDENTITY_USER"
                    )
                )
                members = session.execute(member_query).scalars().all()
                users_to_invalidate.extend(members)
                logger.debug(f"Found {len(members)} users in custom group {principal_id} to invalidate")
            elif principal_type == "IDENTITY_GROUP":
                # Identity group - invalidate all group and permission caches
                pattern = "identity:groups:user:*"
                self.cache_client.client.delete_pattern(pattern)
                pattern = "tenants:user:*:with_permissions"
                self.cache_client.client.delete_pattern(pattern)
                logger.debug(f"Cleared identity group cache patterns for group {principal_id}")

            # Invalidate cache for each affected user
            for user_id_to_clear in users_to_invalidate:
                deleted_count = self.cache_client.clear_cache_for_user(user_id_to_clear)
                logger.debug(f"Cleared {deleted_count} cache entries for user {user_id_to_clear}")

            # Also clear cache for the user making the change
            if user_id:
                self.cache_client.clear_cache_for_user(user_id)

            # Invalidate tenant list caches
            self.cache_client.invalidate_tenant_list_cache()
        except Exception as e:
            logger.warning(f"Failed to clear user cache: {e}")

    def _invalidate_principal_caches(self, tenant_id: str, principal_id: str) -> None:
        """Invalidate caches related to a principal."""
        if not self.cache_client:
            return

        try:
            # Invalidate principal detail cache
            cache_key = f"principals:detail:tenant:{tenant_id}:principal:{principal_id}"
            self.cache_client.client.delete(cache_key)

            # Invalidate user identity caches
            self.cache_client.client.delete(f"identity:groups:user:{principal_id}")
            self.cache_client.client.delete(f"identity:custom_groups:user:{principal_id}")

            logger.debug("Invalidated principal caches", extra={"tenant_id": tenant_id, "principal_id": principal_id})
        except Exception as e:
            logger.warning(f"Failed to invalidate principal caches: {e}")
