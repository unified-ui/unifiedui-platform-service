"""Business logic handlers for tenant operations using SQLAlchemy."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from unifiedui.core.database.models import Principal, Tenant, TenantMember
from unifiedui.exc.organizations import TenantCannotBeDeletedError
from unifiedui.exc.tenants import TenantNotFoundError
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger
from unifiedui.schema.responses.tenants import TenantResponse

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest

logger = get_logger(__name__)


class TenantHandler:
    """Handler class for tenant business logic using SQLAlchemy."""

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        """
        Initialize the tenant handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_tenants(
        self,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> list[TenantResponse]:
        """
        Get a list of tenants.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by tenant name (case-insensitive partial match)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching (default: True)

        Returns:
            List of tenant responses
        """
        logger.info("Listing tenants", extra={"skip": skip, "limit": limit, "name_filter": name_filter})

        # Build cache key (without filters - caching only for unfiltered results)
        cache_key = f"tenants:list:skip:{skip}:limit:{limit}"

        # Check if any filters are applied
        has_filters = name_filter is not None or order_by is not None

        # Check cache (disable caching when any filters are applied)
        cached_data = self._get_from_cache(cache_key, use_cache and not has_filters)
        if cached_data is not None:
            return [TenantResponse(**item) for item in cached_data]

        with self.db_client.get_session() as session:
            query = select(Tenant)

            # Apply name filter if provided
            if name_filter:
                query = query.where(Tenant.name.ilike(f"%{name_filter}%"))

            # Apply ordering if specified
            if order_by and hasattr(Tenant, order_by):
                column = getattr(Tenant, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            # Apply pagination
            query = query.offset(skip).limit(limit)

            tenants = session.execute(query).scalars().all()

            logger.info("Retrieved tenants", extra={"count": len(tenants)})
            result = [self._model_to_response(tenant) for tenant in tenants]

            # Cache the result (only when no filters are applied)
            if not has_filters:
                cache_data = [item.model_dump() for item in result]
                self._set_to_cache(cache_key, cache_data, ttl=300)

            return result

    def get_tenant(self, tenant_id: str, use_cache: bool = True) -> TenantResponse:
        """
        Get a specific tenant by ID.

        Args:
            tenant_id: The ID of the tenant
            use_cache: Whether to use caching (default: True)

        Returns:
            Tenant response

        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Fetching tenant", extra={"tenant_id": tenant_id})

        # Build cache key
        cache_key = f"tenants:detail:{tenant_id}"

        # Check cache
        cached_data = self._get_from_cache(cache_key, use_cache)
        if cached_data is not None:
            return TenantResponse(**cached_data)

        with self.db_client.get_session() as session:
            tenant = self._validate_tenant_exists(session, tenant_id)

            logger.info("Tenant retrieved", extra={"tenant_id": tenant_id})
            result = self._model_to_response(tenant)

            # Cache the result
            self._set_to_cache(cache_key, result.model_dump(), ttl=600)

            return result

    def create_tenant(self, request: CreateTenantRequest, user_id: str, user: ContextIdentityUser) -> TenantResponse:
        """
        Create a new tenant and assign the creator as GLOBAL_ADMIN.

        Resolves the organization from the user's identity context.
        The tenant is created within the user's organization.

        Args:
            request: Tenant creation data
            user_id: ID of the user creating the tenant (principal_id)
            user: The authenticated user context (for IDP access)

        Returns:
            Created tenant response

        Raises:
            TenantNotFoundError: If no organization found for the user's IDP tenant.
        """
        logger.info("Creating tenant", extra={"tenant_name": request.name, "user_id": user_id})

        organization_id = self._resolve_user_organization_id(user)

        tenant_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            tenant = Tenant(
                id=tenant_id,
                name=request.name,
                description=request.description,
                organization_id=organization_id,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(tenant)
            session.flush()

            # Ensure principal exists (fetches from IDP if needed)
            ensure_principal_exists(
                session=session, tenant_id=tenant_id, principal_id=user_id, principal_type="IDENTITY_USER", user=user
            )

            # Create GLOBAL_ADMIN role for the creator
            role_id = str(uuid.uuid4())
            tenant_role = TenantMember(
                id=role_id,
                tenant_id=tenant_id,
                principal_id=user_id,
                role="GLOBAL_ADMIN",
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(tenant_role)
            session.flush()

            # Commit happens automatically in context manager
            logger.info(
                "Tenant created with GLOBAL_ADMIN role",
                extra={"tenant_id": tenant_id, "user_id": user_id, "role_id": role_id},
            )

            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_tenant_list_cache()
                    # Clear user cache since permissions changed
                    self.cache_client.clear_cache_for_user(user_id)
                    logger.debug(f"Invalidated tenant list cache and user cache for {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            return self._model_to_response(tenant)

    def update_tenant(self, tenant_id: str, request: UpdateTenantRequest, user_id: str) -> TenantResponse:
        """
        Update an existing tenant.

        Args:
            tenant_id: The ID of the tenant to update
            request: Tenant update data
            user_id: ID of the user updating the tenant

        Returns:
            Updated tenant response

        Raises:
            TenantNotFoundError: If tenant not found
        """
        logger.info("Updating tenant", extra={"tenant_id": tenant_id, "user_id": user_id})

        with self.db_client.get_session() as session:
            tenant = session.get(Tenant, tenant_id)

            if not tenant:
                logger.warning("Tenant not found for update", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)

            # Update fields if provided
            if request.name is not None:
                tenant.name = request.name
            if request.description is not None:
                tenant.description = request.description

            # Set updated_by
            tenant.updated_by = user_id

            # Commit happens automatically in context manager
            logger.info("Tenant updated", extra={"tenant_id": tenant_id, "user_id": user_id})

            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_tenant_list_cache()
                    # Invalidate specific tenant cache
                    self.cache_client.invalidate_tenant_cache(tenant_id)
                    logger.debug(f"Invalidated caches for tenant {tenant_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            return self._model_to_response(tenant)

    def delete_tenant(self, tenant_id: str) -> None:
        """
        Delete a tenant by ID.

        Args:
            tenant_id: The ID of the tenant to delete

        Raises:
            TenantNotFoundError: If tenant not found
            TenantCannotBeDeletedError: If tenant has can_be_deleted=False
        """
        logger.info("Deleting tenant", extra={"tenant_id": tenant_id})

        with self.db_client.get_session() as session:
            tenant = session.get(Tenant, tenant_id)

            if not tenant:
                logger.warning("Tenant not found for deletion", extra={"tenant_id": tenant_id})
                raise TenantNotFoundError(tenant_id)

            if not tenant.can_be_deleted:
                logger.warning("Tenant cannot be deleted", extra={"tenant_id": tenant_id})
                raise TenantCannotBeDeletedError(tenant_id)

            session.delete(tenant)
            # Commit happens automatically in context manager

            # Invalidate caches
            if self.cache_client:
                try:
                    # Invalidate list caches
                    self.cache_client.invalidate_tenant_list_cache()
                    # Invalidate specific tenant cache
                    self.cache_client.invalidate_tenant_cache(tenant_id)
                    # Clear all user caches (all users who had access to this tenant)
                    pattern = "tenants:user:*:with_permissions"
                    self.cache_client.client.delete_pattern(pattern)
                    logger.debug(f"Invalidated caches for deleted tenant {tenant_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            logger.info("Tenant deleted", extra={"tenant_id": tenant_id})

    def get_user_tenants_with_permissions(
        self, user_id: str, identity_group_ids: list[str], custom_group_ids: list[str], use_cache: bool = True
    ) -> list[dict]:
        """
        Get all tenants and permissions for a user based on their user ID, identity groups, and custom groups.

        Args:
            user_id: The identity user ID
            identity_group_ids: List of identity group IDs the user belongs to
            custom_group_ids: List of custom group IDs the user belongs to
            use_cache: Whether to use caching (default: True)

        Returns:
            List of dicts with 'tenant' and 'permissions' keys, where permissions are deduplicated
        """
        logger.info(
            "Getting user tenants with permissions",
            extra={
                "user_id": user_id,
                "identity_groups_count": len(identity_group_ids),
                "custom_groups_count": len(custom_group_ids),
            },
        )

        cache_key = f"tenants:user:{user_id}:with_permissions"

        # Check cache
        cached_data = self._get_from_cache(cache_key, use_cache)
        if cached_data is not None:
            return cached_data

        with self.db_client.get_session() as session:
            # Build conditions for all principal IDs
            # We now use the Principal table via JOIN to filter by principal_type
            all_principal_ids = [user_id, *identity_group_ids, *custom_group_ids]

            if not all_principal_ids:
                return []

            # Query to get all tenant member roles
            # TenantMember now directly references tenant and principal
            query = (
                select(Tenant, TenantMember)
                .join(TenantMember, Tenant.id == TenantMember.tenant_id)
                .where(TenantMember.principal_id.in_(all_principal_ids))
                .order_by(Tenant.name, TenantMember.role)
            )

            results = session.execute(query).all()

            # Group by tenant and deduplicate roles
            tenants_dict = {}
            for tenant, role in results:
                if tenant.id not in tenants_dict:
                    tenants_dict[tenant.id] = {
                        "tenant": tenant,
                        "roles": set(),  # Use set for deduplication
                    }
                # Add role to set (automatically deduplicates)
                tenants_dict[tenant.id]["roles"].add(role.role)

            # Convert to response format
            response = []
            for tenant_data in tenants_dict.values():
                tenant_response = self._model_to_response(tenant_data["tenant"])
                # Convert set of permissions to sorted list
                roles_list = sorted(list(tenant_data["roles"]))
                response.append({"tenant": tenant_response.model_dump(), "roles": roles_list})

            logger.info(
                "Retrieved user tenants with permissions", extra={"user_id": user_id, "tenant_count": len(response)}
            )

            # Cache the result
            self._set_to_cache(cache_key, response, ttl=300)

            return response

    @staticmethod
    def _model_to_response(tenant: Tenant) -> TenantResponse:
        """
        Convert a tenant model to a response object.

        Args:
            tenant: Tenant SQLAlchemy model

        Returns:
            Tenant response
        """
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            organization_id=tenant.organization_id,
            environment_type=tenant.environment_type,
            is_default=tenant.is_default,
            can_be_deleted=tenant.can_be_deleted,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            created_by=tenant.created_by,
            updated_by=tenant.updated_by,
        )

    def _resolve_user_organization_id(self, user: ContextIdentityUser) -> str:
        """Resolve the organization ID for the authenticated user.

        Args:
            user: The authenticated user context.

        Returns:
            The organization ID.

        Raises:
            TenantNotFoundError: If no organization exists for the user's IDP tenant.
        """
        org_context = user.organization_context
        if org_context is None:
            raise TenantNotFoundError("No organization found for user")
        return org_context.id

    def _get_from_cache(self, cache_key: str, use_cache: bool = True):
        """
        Get data from cache if available.

        Args:
            cache_key: Cache key to retrieve
            use_cache: Whether to use cache

        Returns:
            Cached data or None
        """
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Failed to get from cache {cache_key}: {e}")
        return None

    def _set_to_cache(self, cache_key: str, data, ttl: int = 300):
        """
        Set data to cache.

        Args:
            cache_key: Cache key to set
            data: Data to cache
            ttl: Time to live in seconds
        """
        if self.cache_client:
            try:
                self.cache_client.client.set(cache_key, data, ttl=ttl)
                logger.debug(f"Cached: {cache_key} (TTL: {ttl}s)")
            except Exception as e:
                logger.warning(f"Failed to cache {cache_key}: {e}")

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

    @staticmethod
    def _role_to_response(role: TenantMember, principal: Principal):
        """
        Convert a tenant member role to a role response object.

        Args:
            role: TenantMember SQLAlchemy model
            principal: Principal SQLAlchemy model

        Returns:
            TenantRoleResponse
        """
        from unifiedui.schema.responses.tenants import TenantRoleResponse

        # Generate a human-readable name from the role value
        role_name = role.role.replace("_", " ").title() if role.role else None
        return TenantRoleResponse(
            id=role.id,
            principal_type=principal.principal_type,
            role=role.role,
            name=role_name,
            description=None,
            created_at=role.created_at,
        )
