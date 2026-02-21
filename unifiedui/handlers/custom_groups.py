"""Business logic handlers for custom group operations using SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, or_, select

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import CustomGroupMember, Principal
from unifiedui.exc.custom_groups import CustomGroupNotFoundError
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger
from unifiedui.schema.responses.custom_groups import CustomGroupResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.schema.requests.custom_groups import (
        CreateCustomGroupRequest,
        UpdateCustomGroupRequest,
    )

logger = get_logger(__name__)


class CustomGroupHandler:
    """Handler class for custom group business logic using SQLAlchemy.

    Custom groups are stored as Principal entries with principal_type=CUSTOM_GROUP.
    Custom group membership is tracked via CustomGroupMember table.
    """

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        """
        Initialize the custom group handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_custom_groups(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> list[CustomGroupResponse]:
        """
        Get a list of custom groups in a tenant.
        Custom groups are Principals with principal_type=CUSTOM_GROUP.

        Args:
            tenant_id: The ID of the tenant
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by group name (case-insensitive partial match)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching (default: True)

        Returns:
            List of custom group responses
        """
        logger.info("Listing custom groups", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        # Build cache key (without filters - caching only for unfiltered results)
        cache_key = f"custom_groups:list:tenant:{tenant_id}:skip:{skip}:limit:{limit}"

        # Check if any filters are applied
        has_filters = name_filter is not None or order_by is not None

        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached custom group list (tenant={tenant_id}, skip={skip}, limit={limit})")
                    return [CustomGroupResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached custom group list: {e}")

        with self.db_client.get_session() as session:
            query = select(Principal).where(
                Principal.tenant_id == tenant_id, Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value
            )

            if name_filter:
                query = query.where(Principal.display_name.ilike(f"%{name_filter}%"))

            # Apply ordering if specified - map custom group field names to Principal fields
            field_mapping = {
                "name": "display_name",
                "display_name": "display_name",
                "created_at": "created_at",
                "updated_at": "updated_at",
            }
            if order_by and order_by in field_mapping:
                column = getattr(Principal, field_mapping[order_by])
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            groups = session.execute(query).scalars().all()

            logger.info("Retrieved custom groups", extra={"count": len(groups)})
            result = [self._principal_to_response(group) for group in groups]

            # Cache the result (only when no filters are applied)
            if self.cache_client and not has_filters:
                try:
                    cache_data = [item.model_dump() for item in result]
                    self.cache_client.client.set(cache_key, cache_data, ttl=300)  # Cache for 5 minutes
                    logger.debug("Cached custom group list (TTL: 300s)")
                except Exception as e:
                    logger.warning(f"Failed to cache custom group list: {e}")

            return result

    def get_custom_group(self, tenant_id: str, custom_group_id: str, use_cache: bool = True) -> CustomGroupResponse:
        """
        Get a specific custom group by ID.
        Custom group is a Principal with principal_type=CUSTOM_GROUP.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group (principal_id)
            use_cache: Whether to use caching (default: True)

        Returns:
            Custom group response

        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info("Fetching custom group", extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id})

        # Build cache key
        cache_key = f"custom_groups:detail:tenant:{tenant_id}:group:{custom_group_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached custom group {custom_group_id}")
                    return CustomGroupResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached custom group: {e}")

        with self.db_client.get_session() as session:
            query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(query).scalar_one_or_none()

            if not group:
                logger.warning("Custom group not found", extra={"custom_group_id": custom_group_id})
                raise CustomGroupNotFoundError(custom_group_id)

            logger.info("Custom group retrieved", extra={"custom_group_id": custom_group_id})
            result = self._principal_to_response(group)

            # Cache the result
            if self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=600)  # Cache for 10 minutes
                    logger.debug(f"Cached custom group {custom_group_id} (TTL: 600s)")
                except Exception as e:
                    logger.warning(f"Failed to cache custom group: {e}")

            return result

    def create_custom_group(
        self, tenant_id: str, request: CreateCustomGroupRequest, user_id: str, user: ContextIdentityUser
    ) -> CustomGroupResponse:
        """
        Create a new custom group and assign the creator as ADMIN member.
        Custom group is created as a Principal with principal_type=CUSTOM_GROUP.

        Args:
            tenant_id: The ID of the tenant
            request: Custom group creation data
            user_id: ID of the user creating the group (principal_id)
            user: The authenticated user context (for IDP access)

        Returns:
            Created custom group response
        """
        logger.info(
            "Creating custom group", extra={"tenant_id": tenant_id, "group_name": request.name, "user_id": user_id}
        )

        group_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            # Create custom group as Principal
            group = Principal(
                tenant_id=tenant_id,
                principal_id=group_id,
                principal_type=PrincipalTypeEnum.CUSTOM_GROUP.value,
                display_name=request.name,
                principal_name=request.name,  # For custom groups, name and principal_name are the same
                description=request.description,
                mail=None,  # Custom groups don't have email
            )
            session.add(group)
            session.flush()

            # Ensure creator principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                user=user,
            )

            # Create membership for the creator with ADMIN role
            member_id = str(uuid.uuid4())
            group_member = CustomGroupMember(
                id=member_id,
                tenant_id=tenant_id,
                custom_group_id=group_id,
                principal_id=user_id,
                role=PermissionActionEnum.ADMIN.value,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(group_member)
            session.flush()

            session.commit()
            session.refresh(group)

            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches for this tenant
                    self.cache_client.invalidate_custom_group_list_cache(tenant_id)
                    # Clear user cache since user got ADMIN permission
                    self.cache_client.clear_cache_for_user(user_id)
                    logger.debug(f"Invalidated custom group list cache and user cache for {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            logger.info("Custom group created", extra={"custom_group_id": group_id})
            return self._principal_to_response(group)

    def update_custom_group(
        self, tenant_id: str, custom_group_id: str, request: UpdateCustomGroupRequest, user_id: str
    ) -> CustomGroupResponse:
        """
        Update an existing custom group.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group to update
            request: Custom group update data
            user_id: ID of the user updating the group

        Returns:
            Updated custom group response

        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Updating custom group",
            extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "user_id": user_id},
        )

        with self.db_client.get_session() as session:
            query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(query).scalar_one_or_none()

            if not group:
                logger.warning("Custom group not found", extra={"custom_group_id": custom_group_id})
                raise CustomGroupNotFoundError(custom_group_id)

            if request.name is not None:
                group.display_name = request.name
                group.principal_name = request.name
            if request.description is not None:
                group.description = request.description

            group.updated_at = datetime.now(UTC)

            session.commit()
            session.refresh(group)

            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_custom_group_list_cache(tenant_id)
                    # Invalidate specific custom group cache
                    self.cache_client.invalidate_custom_group_cache(tenant_id, custom_group_id)
                    logger.debug(f"Invalidated caches for custom group {custom_group_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            logger.info("Custom group updated", extra={"custom_group_id": custom_group_id})
            return self._principal_to_response(group)

    def delete_custom_group(self, tenant_id: str, custom_group_id: str) -> None:
        """
        Delete a custom group by ID.
        This also deletes all CustomGroupMember entries via cascade.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group to delete

        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info("Deleting custom group", extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id})

        with self.db_client.get_session() as session:
            query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(query).scalar_one_or_none()

            if not group:
                logger.warning("Custom group not found", extra={"custom_group_id": custom_group_id})
                raise CustomGroupNotFoundError(custom_group_id)

            session.delete(group)
            session.commit()

            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_custom_group_list_cache(tenant_id)
                    # Invalidate specific custom group cache
                    self.cache_client.invalidate_custom_group_cache(tenant_id, custom_group_id)
                    # Clear all user caches (all users who had access to this group)
                    pattern = "*user:*:*"
                    self.cache_client.client.delete_pattern(pattern)
                    logger.debug(f"Invalidated caches for deleted custom group {custom_group_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            logger.info("Custom group deleted", extra={"custom_group_id": custom_group_id})

    def list_custom_group_members(
        self,
        tenant_id: str,
        custom_group_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
    ) -> dict:
        """
        Get all members and their roles for a specific custom group.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            skip: Number of members to skip
            limit: Maximum number of members to return
            search: Search term for display_name, principal_name, or mail
            roles: Filter by roles (OR logic)
            is_active: Filter by is_active status
            order_by: Column to order by
            order_direction: Sort direction

        Returns:
            Dict with custom_group_id and list of members with their roles

        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Listing members for custom group", extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id}
        )

        with self.db_client.get_session() as session:
            # Verify group exists
            group_query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(group_query).scalar_one_or_none()
            if not group:
                raise CustomGroupNotFoundError(custom_group_id)

            # Get all members with their info from Principal table
            query = (
                select(CustomGroupMember, Principal)
                .join(
                    Principal,
                    and_(
                        CustomGroupMember.tenant_id == Principal.tenant_id,
                        CustomGroupMember.principal_id == Principal.principal_id,
                    ),
                )
                .where(CustomGroupMember.tenant_id == tenant_id, CustomGroupMember.custom_group_id == custom_group_id)
            )

            # Apply role filter
            if roles:
                query = query.where(CustomGroupMember.role.in_(roles))

            # Apply is_active filter
            if is_active is not None:
                query = query.where(Principal.is_active == is_active)

            # Apply search filter
            if search:
                search_pattern = f"%{search.lower()}%"
                query = query.where(
                    or_(
                        func.lower(Principal.display_name).like(search_pattern),
                        func.lower(Principal.principal_name).like(search_pattern),
                        func.lower(Principal.mail).like(search_pattern),
                    )
                )

            results = session.execute(query).all()

            members = []
            for member, principal in results:
                members.append(
                    {
                        "principal_id": member.principal_id,
                        "principal_type": principal.principal_type,
                        "display_name": principal.display_name,
                        "principal_name": principal.principal_name,
                        "mail": principal.mail,
                        "description": principal.description,
                        "is_active": principal.is_active,
                        "role": member.role,
                        "created_at": member.created_at.isoformat() if member.created_at else None,
                        "updated_at": member.updated_at.isoformat() if member.updated_at else None,
                    }
                )

            # Sort members
            if order_by == "display_name":
                reverse = order_direction == "desc"
                members.sort(key=lambda x: (x.get("display_name") or "").lower(), reverse=reverse)
            else:
                # Default sort by display_name ascending
                members.sort(key=lambda x: (x.get("display_name") or "").lower())

            # Apply pagination
            members = members[skip : skip + limit]

            logger.info(
                "Retrieved custom group members",
                extra={"custom_group_id": custom_group_id, "member_count": len(members)},
            )

            return {"custom_group_id": custom_group_id, "tenant_id": tenant_id, "members": members}

    def get_member_role(self, tenant_id: str, custom_group_id: str, principal_id: str) -> dict:
        """
        Get the role for a specific member in a custom group.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            principal_id: The ID of the member principal

        Returns:
            Dict with custom_group_id, principal_id, and role

        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Getting member role",
            extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "principal_id": principal_id},
        )

        with self.db_client.get_session() as session:
            # Verify group exists
            group_query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(group_query).scalar_one_or_none()
            if not group:
                raise CustomGroupNotFoundError(custom_group_id)

            # Get member
            query = select(CustomGroupMember).where(
                CustomGroupMember.tenant_id == tenant_id,
                CustomGroupMember.custom_group_id == custom_group_id,
                CustomGroupMember.principal_id == principal_id,
            )

            member = session.execute(query).scalar_one_or_none()

            if not member:
                # Member not found in this group
                return {
                    "custom_group_id": custom_group_id,
                    "tenant_id": tenant_id,
                    "principal_id": principal_id,
                    "role": None,
                }

            return {
                "custom_group_id": custom_group_id,
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "role": member.role,
            }

    def set_member_role(
        self,
        tenant_id: str,
        custom_group_id: str,
        principal_id: str,
        principal_type: str,
        role: str,
        user_id: str,
        user: ContextIdentityUser,
    ) -> dict:
        """
        Add or update a member's role in a custom group.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            principal_id: The ID of the principal to add/update
            principal_type: The type of principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            role: The role to assign (READ, WRITE, ADMIN)
            user_id: The ID of the user making the change
            user: The authenticated user context (for IDP access)

        Returns:
            Dict with custom_group_id, principal_id, and updated role

        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Setting member role",
            extra={
                "tenant_id": tenant_id,
                "custom_group_id": custom_group_id,
                "principal_id": principal_id,
                "role": role,
            },
        )

        with self.db_client.get_session() as session:
            # Verify group exists
            group_query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(group_query).scalar_one_or_none()
            if not group:
                raise CustomGroupNotFoundError(custom_group_id)

            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_type=principal_type,
                user=user,
            )

            # Find or create membership
            query = select(CustomGroupMember).where(
                CustomGroupMember.tenant_id == tenant_id,
                CustomGroupMember.custom_group_id == custom_group_id,
                CustomGroupMember.principal_id == principal_id,
            )
            member = session.execute(query).scalar_one_or_none()

            if not member:
                # Create new membership
                member_id = str(uuid.uuid4())
                member = CustomGroupMember(
                    id=member_id,
                    tenant_id=tenant_id,
                    custom_group_id=custom_group_id,
                    principal_id=principal_id,
                    role=role,
                    created_by=user_id,
                    updated_by=user_id,
                )
                session.add(member)
                logger.info(f"Created new membership with role {role} for {principal_id}")
            elif member.role != role:
                # Update existing membership role
                member.role = role
                member.updated_by = user_id
                logger.info(f"Updated membership role from {member.role} to {role} for {principal_id}")
            else:
                logger.info(f"Membership with role {role} already exists for {principal_id}")

            session.commit()

            # Invalidate user cache
            if self.cache_client:
                try:
                    self.cache_client.clear_cache_for_user(principal_id)
                    self.cache_client.clear_cache_for_user(user_id)
                    logger.debug(f"Cleared cache for user {principal_id} after membership change")
                except Exception as e:
                    logger.warning(f"Failed to clear user cache: {e}")

            logger.info(f"Set {role} role for {principal_id} in custom group {custom_group_id}")

            return self.get_member_role(tenant_id, custom_group_id, principal_id)

    def delete_member(self, tenant_id: str, custom_group_id: str, principal_id: str) -> None:
        """
        Remove a member from a custom group.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            principal_id: The ID of the principal to remove

        Raises:
            CustomGroupNotFoundError: If custom group not found
        """
        logger.info(
            "Deleting member",
            extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "principal_id": principal_id},
        )

        with self.db_client.get_session() as session:
            # Verify group exists
            group_query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(group_query).scalar_one_or_none()
            if not group:
                raise CustomGroupNotFoundError(custom_group_id)

            # Find and delete membership
            query = select(CustomGroupMember).where(
                CustomGroupMember.tenant_id == tenant_id,
                CustomGroupMember.custom_group_id == custom_group_id,
                CustomGroupMember.principal_id == principal_id,
            )
            member = session.execute(query).scalar_one_or_none()

            if member:
                session.delete(member)
                session.commit()

                # Invalidate user cache
                if self.cache_client:
                    try:
                        self.cache_client.clear_cache_for_user(principal_id)
                        logger.debug(f"Cleared cache for user {principal_id} after membership removal")
                    except Exception as e:
                        logger.warning(f"Failed to clear user cache: {e}")

                logger.info(f"Deleted membership for {principal_id} in custom group {custom_group_id}")
            else:
                logger.info(f"No membership found for {principal_id} in custom group {custom_group_id}")

    # Legacy method names for backwards compatibility with routes
    def list_custom_group_principals(
        self,
        tenant_id: str,
        custom_group_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> ResourcePrincipalsResponse:
        """List all principals with their roles on a custom group.

        Args:
            tenant_id: The ID of the tenant
            custom_group_id: The ID of the custom group
            skip: Number of principals to skip
            limit: Maximum number of principals to return
            search: Search term for display_name, principal_name, or mail
            roles: Filter by roles (OR logic)
            is_active: Filter by is_active status
            order_by: Column to order by
            order_direction: Sort direction
            use_cache: Whether to use caching

        Returns unified ResourcePrincipalsResponse with enriched principal data.
        """
        result = self.list_custom_group_members(
            tenant_id=tenant_id,
            custom_group_id=custom_group_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction,
        )
        # Convert 'members' to 'principals' format with enriched data
        principals = []
        for member in result.get("members", []):
            principals.append(
                PrincipalWithRolesResponse(
                    principal_id=member["principal_id"],
                    principal_type=member.get("principal_type"),
                    roles=[member["role"]] if member.get("role") else [],
                    mail=member.get("mail"),
                    display_name=member.get("display_name"),
                    principal_name=member.get("principal_name"),
                    description=member.get("description"),
                    is_active=member.get("is_active", True),
                )
            )
        return ResourcePrincipalsResponse(
            resource_id=result["custom_group_id"],
            resource_type="custom_group",
            tenant_id=result["tenant_id"],
            principals=principals,
        )

    def get_principal_permissions(
        self, tenant_id: str, custom_group_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """Get permissions for a specific principal on a custom group.

        Returns unified PrincipalWithRolesResponse with enriched principal data.
        Raises PrincipalNotFoundError if principal is not a member of this group.
        """
        logger.info(
            "Getting principal permissions",
            extra={"tenant_id": tenant_id, "custom_group_id": custom_group_id, "principal_id": principal_id},
        )

        with self.db_client.get_session() as session:
            # Verify group exists
            group_query = select(Principal).where(
                Principal.tenant_id == tenant_id,
                Principal.principal_id == custom_group_id,
                Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
            )
            group = session.execute(group_query).scalar_one_or_none()
            if not group:
                raise CustomGroupNotFoundError(custom_group_id)

            # Get member with principal info using outer join
            query = (
                select(CustomGroupMember, Principal)
                .outerjoin(
                    Principal,
                    and_(
                        CustomGroupMember.tenant_id == Principal.tenant_id,
                        CustomGroupMember.principal_id == Principal.principal_id,
                    ),
                )
                .where(
                    CustomGroupMember.tenant_id == tenant_id,
                    CustomGroupMember.custom_group_id == custom_group_id,
                    CustomGroupMember.principal_id == principal_id,
                )
            )

            result = session.execute(query).first()

            if not result:
                # Member not found in this group - raise error
                from unifiedui.exc.principal import PrincipalNotFoundError

                raise PrincipalNotFoundError(principal_id)

            member, principal = result
            # Use member's principal_type if Principal record doesn't exist (outer join)
            p_type = principal.principal_type if principal else member.principal_type
            return PrincipalWithRolesResponse(
                principal_id=principal_id,
                principal_type=p_type,
                roles=[member.role] if member.role else [],
                mail=principal.mail if principal else None,
                display_name=principal.display_name if principal else None,
                principal_name=principal.principal_name if principal else None,
                description=principal.description,
            )

    def set_principal_permission(
        self,
        tenant_id: str,
        custom_group_id: str,
        principal_id: str,
        principal_type: str,
        role: str,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """Set a principal's permission on a custom group.

        Returns unified PrincipalWithRolesResponse with enriched principal data.
        """
        self.set_member_role(tenant_id, custom_group_id, principal_id, principal_type, role, user_id, user)
        return self.get_principal_permissions(tenant_id, custom_group_id, principal_id)

    def delete_principal_permission(
        self, tenant_id: str, custom_group_id: str, principal_id: str, principal_type: str, role: str
    ) -> PrincipalWithRolesResponse:
        """Delete a principal's permission from a custom group.

        Returns unified PrincipalWithRolesResponse with remaining permissions (empty list after deletion).
        """
        # Get principal info before deletion to ensure we have the type for response
        principal_info = None
        with self.db_client.get_session() as session:
            # Try to get principal info from Principal table
            principal_query = select(Principal).where(
                Principal.tenant_id == tenant_id, Principal.principal_id == principal_id
            )
            principal = session.execute(principal_query).scalar_one_or_none()
            # Extract values while in session to avoid DetachedInstanceError
            if principal:
                principal_info = {
                    "principal_type": principal.principal_type,
                    "mail": principal.mail,
                    "display_name": principal.display_name,
                    "principal_name": principal.principal_name,
                    "description": principal.description,
                }

        # Perform deletion
        self.delete_member(tenant_id, custom_group_id, principal_id)

        # Return response - use principal info if available, otherwise use passed principal_type
        if principal_info:
            return PrincipalWithRolesResponse(
                principal_id=principal_id,
                principal_type=principal_info["principal_type"],
                roles=[],  # Empty after deletion
                mail=principal_info["mail"],
                display_name=principal_info["display_name"],
                principal_name=principal_info["principal_name"],
                description=principal_info["description"],
            )
        else:
            # Principal not in table (e.g., unsynced external user)
            return PrincipalWithRolesResponse(
                principal_id=principal_id,
                principal_type=principal_type,  # Use passed type
                roles=[],  # Empty after deletion
                mail=None,
                display_name=None,
                principal_name=None,
                description=None,
            )

    @staticmethod
    def _principal_to_response(principal: Principal) -> CustomGroupResponse:
        """Convert Principal model (CUSTOM_GROUP type) to CustomGroupResponse."""
        return CustomGroupResponse(
            id=principal.principal_id,
            tenant_id=principal.tenant_id,
            name=principal.display_name,
            description=principal.description,
            created_at=principal.created_at,
            updated_at=principal.updated_at,
            created_by=None,  # Principal doesn't track created_by
            updated_by=None,  # Principal doesn't track updated_by
        )
