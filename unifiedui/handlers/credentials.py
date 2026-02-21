"""Business logic handlers for credential operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import PermissionActionEnum
from unifiedui.core.database.models import Credential, CredentialMember, CredentialTag
from unifiedui.handlers.permission_resolver import (
    check_is_admin,
    get_principal_ids,
    resolve_my_permission,
    resolve_my_permissions_bulk,
)

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.core.vault.client import BaseVaultClient
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler
    from unifiedui.schema.requests.credential_permissions import SetCredentialPermissionRequest
    from unifiedui.schema.requests.credentials import CreateCredentialRequest, UpdateCredentialRequest

from unifiedui.exc.credentials import CredentialNotFoundError
from unifiedui.handlers.validators.credential_validator import (
    validate_credential_secret,
)
from unifiedui.logger import get_logger
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.credentials import CredentialResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.tags import TagSummary

logger = get_logger(__name__)


class CredentialHandler:
    """Handler class for credential business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        vault_client: BaseVaultClient,
        cache_client: CacheClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
    ):
        """
        Initialize the credential handler.

        Args:
            db_client: SQLAlchemy database client instance
            vault_client: Vault client for secret management
            cache_client: Optional cache client for Redis caching
            permissions_handler: Optional central permissions handler
            tags_handler: Optional central tags handler
        """
        self.db_client = db_client
        self.vault_client = vault_client
        self.cache_client = cache_client
        self._permissions_handler = permissions_handler
        self._tags_handler = tags_handler

    @property
    def permissions_handler(self) -> ResourcePermissionsHandler:
        """Get the permissions handler, creating one if needed."""
        if self._permissions_handler is None:
            from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler

            self._permissions_handler = ResourcePermissionsHandler(self.db_client, self.cache_client)
        return self._permissions_handler

    @property
    def tags_handler(self) -> ResourceTagsHandler:
        """Get the tags handler, creating one if needed."""
        if self._tags_handler is None:
            from unifiedui.handlers.resource_tags import ResourceTagsHandler

            self._tags_handler = ResourceTagsHandler(self.db_client, self.cache_client)
        return self._tags_handler

    def list_credentials(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        is_active: int | None = None,
        tag_ids: list[int] | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        view: str | None = None,
        use_cache: bool = True,
    ) -> list[CredentialResponse] | list[QuickListItemResponse]:
        """
        Get a list of credentials for a tenant (filtered by permissions).

        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by credential name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (credentials must have AT LEAST ONE of the tags - OR logic)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching

        Returns:
            List of credential responses (without secret values)
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing credentials", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        # Check if user is admin (has GLOBAL_ADMIN or CREDENTIALS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]  # Changed from "permissions" to "roles"
            admin_permissions = [TenantRolesEnum.GLOBAL_ADMIN.value, TenantRolesEnum.CREDENTIALS_ADMIN.value]
            is_admin = any(perm in user_roles for perm in admin_permissions)

        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]

        # Build cache key with order and is_active parameters
        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"credentials:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"

        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None

        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached credential list")
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [CredentialResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached credential list: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(Credential)
                .options(selectinload(Credential.tags).selectinload(CredentialTag.tag))
                .where(Credential.tenant_id == tenant_id)
            )

            # Filter by permissions if not admin
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)

                # Subquery for credentials where user is a member
                member_subquery = (
                    select(CredentialMember.credential_id)
                    .where(CredentialMember.tenant_id == tenant_id, CredentialMember.principal_id.in_(principal_ids))
                    .distinct()
                )

                query = query.where(Credential.id.in_(member_subquery))

            if name_filter:
                query = query.where(Credential.name.ilike(f"%{name_filter}%"))

            # Filter by is_active status
            if is_active is not None:
                query = query.where(Credential.is_active == bool(is_active))

            # Filter by tags (credentials must have AT LEAST ONE of the specified tags - OR logic)
            if tag_ids:
                tag_subquery = (
                    select(CredentialTag.credential_id)
                    .where(CredentialTag.tenant_id == tenant_id, CredentialTag.tag_id.in_(tag_ids))
                    .distinct()
                )
                query = query.where(Credential.id.in_(tag_subquery))

            # Apply ordering if specified
            if order_by and hasattr(Credential, order_by):
                column = getattr(Credential, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            credentials = session.execute(query).scalars().all()

            logger.info("Retrieved credentials", extra={"count": len(credentials)})

            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=cred.id, name=cred.name) for cred in credentials]

            result = [self._model_to_response(cred) for cred in credentials]

            if is_admin:
                for r in result:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in result]
                if resource_ids:
                    permissions = resolve_my_permissions_bulk(
                        session, CredentialMember, "credential_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in result:
                        r.my_permission = permissions.get(r.id)

            # Cache the result (only when no filters are applied)
            if self.cache_client and not has_filters:
                try:
                    cache_data = [item.model_dump() for item in result]
                    self.cache_client.client.set(cache_key, cache_data, ttl=30)  # 30 seconds
                    logger.debug("Cached credential list (TTL: 30s)")
                except Exception as e:
                    logger.warning(f"Failed to cache credential list: {e}")

            return result

    def get_credential(
        self, tenant_id: str, credential_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> CredentialResponse:
        """
        Get a specific credential by ID (without secret value).

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            user: Optional user context for permission resolution
            use_cache: Whether to use caching

        Returns:
            Credential response (without secret value)

        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Fetching credential", extra={"tenant_id": tenant_id, "credential_id": credential_id})

        # Build cache key
        cache_key = f"credentials:detail:tenant:{tenant_id}:cred:{credential_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached credential {credential_id}")
                    result = CredentialResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(
                                session, tenant_id, credential_id, user
                            )
                    return result
            except Exception as e:
                logger.warning(f"Failed to get cached credential: {e}")

        with self.db_client.get_session() as session:
            query = (
                select(Credential)
                .options(selectinload(Credential.tags).selectinload(CredentialTag.tag))
                .where(Credential.id == credential_id, Credential.tenant_id == tenant_id)
            )
            credential = session.execute(query).scalar_one_or_none()

            if not credential:
                logger.warning("Credential not found", extra={"credential_id": credential_id})
                raise CredentialNotFoundError(credential_id)

            logger.info("Credential retrieved", extra={"credential_id": credential_id})
            result = self._model_to_response(credential)

            # Cache the result
            if self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=60)  # 1 minute
                    logger.debug(f"Cached credential {credential_id} (TTL: 60s)")
                except Exception as e:
                    logger.warning(f"Failed to cache credential: {e}")

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, credential_id, user)

            return result

    def get_credential_secret(self, tenant_id: str, credential_id: str, use_cache: bool = False) -> str | None:
        """
        Get the actual secret value from vault (for internal use only).
        This method should NOT be exposed to end users via API.

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            use_cache: Whether to use caching (default: False)

        Returns:
            Secret value or None

        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Fetching credential secret", extra={"tenant_id": tenant_id, "credential_id": credential_id})

        with self.db_client.get_session() as session:
            query = select(Credential).where(Credential.id == credential_id, Credential.tenant_id == tenant_id)
            credential = session.execute(query).scalar_one_or_none()

            if not credential:
                raise CredentialNotFoundError(credential_id)

            # Fetch secret from vault
            secret = self.vault_client.get_secret(credential.credential_uri, use_cache=use_cache)
            logger.debug(f"Retrieved secret for credential {credential_id}")
            return secret

    def create_credential(
        self, tenant_id: str, request: CreateCredentialRequest, user_id: str, user: ContextIdentityUser
    ) -> CredentialResponse:
        """
        Create a new credential and store secret in vault.

        Args:
            tenant_id: The ID of the tenant
            request: Credential creation data
            user_id: ID of the user creating the credential
            user: The authenticated user context (for IDP access)

        Returns:
            Created credential response

        Raises:
            CredentialValidationError: If credential validation fails
            UnsupportedCredentialTypeError: If credential type is not supported
        """
        logger.info(
            "Creating credential", extra={"tenant_id": tenant_id, "credential_name": request.name, "user_id": user_id}
        )

        # Validate secret value based on credential type
        validated_secret = validate_credential_secret(
            credential_type=request.credential_type, secret_value=request.secret_value
        )

        credential_id = str(uuid.uuid4())

        # Store secret in vault first
        try:
            vault_uri = self.vault_client.store_secret(
                key=f"{tenant_id}/{credential_id}", value=validated_secret, metadata=request.metadata
            )
            logger.info(f"Stored secret in vault for credential {credential_id}")
        except Exception as e:
            logger.error(f"Failed to store secret in vault: {e}")
            raise

        with self.db_client.get_session() as session:
            # Create credential (without secret)
            credential = Credential(
                id=credential_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.credential_type,
                source=request.source or "manual",  # Default to "manual" if not provided
                credential_uri=vault_uri,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(credential)
            session.flush()  # Flush to get auto-generated timestamps

            # Add creator as admin member using central handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="credential",
                tenant_id=tenant_id,
                resource_id=credential_id,
                user_id=user_id,
                user=user,
            )

            # Invalidate caches BEFORE flush to ensure consistency
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    self._invalidate_permissions_cache(tenant_id, credential_id)
                    logger.debug("Invalidated credential list and permissions cache")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            session.flush()
            session.commit()  # Explicit commit to ensure data is visible

            logger.info("Added creator as admin member", extra={"user_id": user_id, "credential_id": credential_id})
            logger.info("Credential created", extra={"credential_id": credential_id})
            return self._model_to_response(credential)

    def update_credential(
        self, tenant_id: str, credential_id: str, request: UpdateCredentialRequest, user_id: str
    ) -> CredentialResponse:
        """
        Update an existing credential.

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            request: Credential update data
            user_id: ID of the user updating the credential

        Returns:
            Updated credential response

        Raises:
            CredentialNotFoundError: If credential not found
            CredentialValidationError: If credential validation fails
            UnsupportedCredentialTypeError: If credential type is not supported
        """
        logger.info("Updating credential", extra={"tenant_id": tenant_id, "credential_id": credential_id})

        with self.db_client.get_session() as session:
            query = (
                select(Credential)
                .options(selectinload(Credential.tags).selectinload(CredentialTag.tag))
                .where(Credential.id == credential_id, Credential.tenant_id == tenant_id)
            )
            credential = session.execute(query).scalar_one_or_none()

            if not credential:
                raise CredentialNotFoundError(credential_id)

            # Determine the credential type for validation
            cred_type = request.credential_type if request.credential_type is not None else credential.type

            # Update secret in vault if provided
            if request.secret_value is not None:
                # Validate secret value based on credential type
                validated_secret = validate_credential_secret(
                    credential_type=cred_type, secret_value=request.secret_value
                )

                try:
                    self.vault_client.update_secret(
                        uri=credential.credential_uri, value=validated_secret, metadata=request.metadata
                    )
                    logger.info(f"Updated secret in vault for credential {credential_id}")
                except Exception as e:
                    logger.error(f"Failed to update secret in vault: {e}")
                    raise

            # Update credential metadata
            if request.name is not None:
                credential.name = request.name
            if request.description is not None:
                credential.description = request.description
            if request.credential_type is not None:
                credential.type = request.credential_type
            if request.is_active is not None:
                credential.is_active = request.is_active
            if request.metadata is not None:
                # Metadata is stored as part of the vault secret, not in DB
                pass

            credential.updated_by = user_id

            # Invalidate caches BEFORE commit to ensure consistency
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    self._invalidate_detail_cache(tenant_id, credential_id)
                    logger.debug(f"Invalidated caches for credential {credential_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            session.flush()

            # Re-fetch with tags to ensure they are loaded
            query = (
                select(Credential)
                .options(selectinload(Credential.tags).selectinload(CredentialTag.tag))
                .where(Credential.id == credential_id, Credential.tenant_id == tenant_id)
            )
            credential = session.execute(query).scalar_one_or_none()

            logger.info("Credential updated", extra={"credential_id": credential_id})
            return self._model_to_response(credential)

    def delete_credential(self, tenant_id: str, credential_id: str) -> None:
        """
        Delete a credential and its secret from vault.

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential

        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Deleting credential", extra={"tenant_id": tenant_id, "credential_id": credential_id})

        with self.db_client.get_session() as session:
            query = select(Credential).where(Credential.id == credential_id, Credential.tenant_id == tenant_id)
            credential = session.execute(query).scalar_one_or_none()

            if not credential:
                raise CredentialNotFoundError(credential_id)

            vault_uri = credential.credential_uri

            # Invalidate caches BEFORE delete to ensure consistency
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    self._invalidate_detail_cache(tenant_id, credential_id)
                    self._invalidate_permissions_cache(tenant_id, credential_id)
                    logger.debug(f"Invalidated caches for credential {credential_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            # Delete from database
            session.delete(credential)
            session.flush()

            # Delete from vault
            try:
                self.vault_client.delete_secret(vault_uri)
                logger.info(f"Deleted secret from vault for credential {credential_id}")
            except Exception as e:
                logger.warning(f"Failed to delete secret from vault: {e}")
                # Continue even if vault deletion fails

            logger.info("Credential deleted", extra={"credential_id": credential_id})

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate all list caches for a tenant."""
        if self.cache_client:
            pattern = f"credentials:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, credential_id: str) -> None:
        """Invalidate detail cache for a specific credential."""
        if self.cache_client:
            cache_key = f"credentials:detail:tenant:{tenant_id}:cred:{credential_id}"
            self.cache_client.client.delete(cache_key)

    def _invalidate_permissions_cache(self, tenant_id: str, credential_id: str) -> None:
        """Invalidate permissions cache for a specific credential."""
        if self.cache_client:
            cache_key = f"credentials:permissions:tenant:{tenant_id}:cred:{credential_id}"
            self.cache_client.client.delete(cache_key)

    # ========== Permission Management Methods ==========

    def list_credential_permissions(
        self,
        tenant_id: str,
        credential_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> ResourcePrincipalsResponse:
        """
        List all permissions for a credential.

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            skip: Number of principals to skip
            limit: Maximum number of principals to return
            search: Search term for display_name, principal_name, or mail
            roles: Filter by roles (OR logic)
            is_active: Filter by is_active status
            order_by: Column to order by
            order_direction: Sort direction
            use_cache: Whether to use caching

        Returns:
            Grouped permissions by principal

        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Listing credential permissions", extra={"tenant_id": tenant_id, "credential_id": credential_id})

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="credential",
                tenant_id=tenant_id,
                resource_id=credential_id,
                skip=skip,
                limit=limit,
                search=search,
                roles=roles,
                is_active=is_active,
                order_by=order_by,
                order_direction=order_direction,
                use_cache=use_cache,
            )
        except ValueError as e:
            raise CredentialNotFoundError(credential_id) from e

        # Convert to response schema
        principals = [
            PrincipalWithRolesResponse(
                principal_id=p["principal_id"],
                principal_type=p["principal_type"],
                roles=p["roles"],
                mail=p.get("mail"),
                display_name=p.get("display_name"),
                principal_name=p.get("principal_name"),
                description=p.get("description"),
                is_active=p.get("is_active", True),
            )
            for p in result["principals"]
        ]

        return ResourcePrincipalsResponse(
            resource_id=credential_id, resource_type="credential", tenant_id=tenant_id, principals=principals
        )

    def get_credential_permission(
        self, tenant_id: str, credential_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """
        Get all permissions for a specific principal on a credential.

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            principal_id: The ID of the principal

        Returns:
            Principal with all their permissions

        Raises:
            CredentialNotFoundError: If credential or principal not found
        """
        logger.info(
            "Getting credential permissions for principal",
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "principal_id": principal_id},
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="credential", tenant_id=tenant_id, resource_id=credential_id, principal_id=principal_id
            )
        except ValueError as e:
            raise CredentialNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_credential_permission(
        self,
        tenant_id: str,
        credential_id: str,
        request: SetCredentialPermissionRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """
        Set or update a credential permission.

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            request: Permission data
            user_id: ID of the user performing the operation

        Returns:
            Created or updated permission

        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info(
            "Setting credential permission",
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "principal_id": request.principal_id},
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="credential",
                tenant_id=tenant_id,
                resource_id=credential_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )
        except ValueError as e:
            raise CredentialNotFoundError(str(e)) from e

        # Fetch and return the enriched principal data
        return self.get_credential_permission(
            tenant_id=tenant_id, credential_id=credential_id, principal_id=request.principal_id
        )

    def delete_credential_permission(
        self, tenant_id: str, credential_id: str, principal_id: str, principal_type: str, permission: str
    ) -> None:
        """
        Delete a specific credential permission.

        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            principal_id: The ID of the principal
            principal_type: The type of the principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            permission: The specific permission to delete (READ, WRITE, ADMIN)

        Raises:
            CredentialNotFoundError: If credential, member, or permission not found
        """
        logger.info(
            "Deleting credential permission",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "principal_id": principal_id,
                "principal_type": principal_type,
                "permission": permission,
            },
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="credential",
                tenant_id=tenant_id,
                resource_id=credential_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=permission,
            )
        except ValueError as e:
            raise CredentialNotFoundError(str(e)) from e

    def _resolve_user_permission(
        self, session: object, tenant_id: str, credential_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific credential.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            credential_id: Credential ID
            user: The authenticated user context

        Returns:
            Permission action string or None
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(user, tenant_id, [TenantRolesEnum.GLOBAL_ADMIN, TenantRolesEnum.CREDENTIALS_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(
            session, CredentialMember, "credential_id", tenant_id, credential_id, principal_ids
        )

    @staticmethod
    def _model_to_response(credential: Credential) -> CredentialResponse:
        """Convert Credential model to response."""
        # Extract tags from the credential's tags relationship
        tags = []
        if hasattr(credential, "tags") and credential.tags:
            for cred_tag in credential.tags:
                if cred_tag.tag:
                    tags.append(TagSummary(id=cred_tag.tag.id, name=cred_tag.tag.name))

        return CredentialResponse(
            id=credential.id,
            tenant_id=credential.tenant_id,
            name=credential.name,
            description=credential.description,
            is_active=credential.is_active,
            type=credential.type,
            source=credential.source,
            credential_uri=credential.credential_uri,
            tags=tags,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
            created_by=credential.created_by,
            updated_by=credential.updated_by,
        )
